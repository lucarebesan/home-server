"""Stima della bolletta elettrica da kWh *prelevati dalla rete*.

Le condizioni economiche del fornitore non includono le componenti regolate
variabili: per quelle si usa l'ultima fattura come riferimento, indicando la
stima come tale. Nessun dato anagrafico o identificativo di fornitura è salvato.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange


CENT = Decimal("0.01")


def D(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value))


def euro(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Tariff:
    name: str
    valid_from: date
    valid_until: date  # exclusive
    energy_f1_incl_losses: Decimal
    energy_f23_incl_losses: Decimal
    direct_debit_discount: Decimal
    dispatch_per_kwh_reference: Decimal
    regulated_per_kwh_reference: Decimal
    sale_fixed_per_month: Decimal
    dispatch_fixed_per_month_reference: Decimal
    network_fixed_per_month_reference: Decimal
    power_per_kw_month_reference: Decimal
    excise_per_kwh_reference: Decimal
    vat: Decimal


# Importi regolati (dispacciamento, trasporto/oneri, quota potenza e accisa)
# osservati in agosto-settembre 2026: NON sono prezzi bloccati dal rinnovo.
_COMMON = dict(
    direct_debit_discount=D("0.05"),
    dispatch_per_kwh_reference=D("0.02556"),
    regulated_per_kwh_reference=D("6.42") / D("134"),
    sale_fixed_per_month=D("12"),
    dispatch_fixed_per_month_reference=D("0.09225"),
    network_fixed_per_month_reference=D("1.92"),
    power_per_kw_month_reference=D("1.97656667"),
    excise_per_kwh_reference=D("0.0227"),
    vat=D("0.10"),
)

CURRENT = Tariff(
    name="Fixa Time Luce Base (fatture osservate)",
    valid_from=date(2025, 12, 1), valid_until=date(2026, 12, 1),
    energy_f1_incl_losses=D("0.09449"),
    energy_f23_incl_losses=D("0.08866"),
    **_COMMON,
)

RENEWAL_PROPOSAL = Tariff(
    name="Fixa Simple Luce Ren Star (proposta, da verificare)",
    valid_from=date(2026, 12, 1), valid_until=date(2027, 12, 1),
    energy_f1_incl_losses=D("0.1333") * D("1.1"),
    energy_f23_incl_losses=D("0.1281") * D("1.1"),
    **_COMMON,
)


def month_equivalents(start: date, end: date) -> Decimal:
    """Quota di mesi nel periodo inclusivo; quota fissa maturata a giorno X."""
    if end < start:
        raise ValueError("periodo invertito")
    total = D(0)
    day = start
    while day <= end:
        last = date(day.year, day.month, monthrange(day.year, day.month)[1])
        stop = min(last, end)
        total += D((stop - day).days + 1) / D(last.day)
        day = stop + timedelta(days=1)
    return total


def estimate(
    tariff: Tariff, start: date, end: date, f1_kwh: Decimal,
    f23_kwh: Decimal, *, power_kw: Decimal = D(10),
    canone_eur: Decimal = D(0), adjustments_eur: Decimal = D(0),
) -> dict[str, Decimal]:
    """Stima dal prelievo di rete per fascia, non dal consumo totale domestico.

    Le componenti regolate e gli arrotondamenti della fattura futura possono
    differire; `adjustments_eur` è imponibile, `canone_eur` è fuori IVA.
    """
    if start < tariff.valid_from or end >= tariff.valid_until:
        raise ValueError("la finestra esce dalla validità della tariffa")
    f1_kwh, f23_kwh = D(f1_kwh), D(f23_kwh)
    if min(f1_kwh, f23_kwh, power_kw) < 0:
        raise ValueError("kWh e potenza non possono essere negativi")
    kwh = f1_kwh + f23_kwh
    months = month_equivalents(start, end)
    sale = (
        f1_kwh * tariff.energy_f1_incl_losses
        + f23_kwh * tariff.energy_f23_incl_losses
    ) * (D(1) - tariff.direct_debit_discount)
    consumption = euro(sale + kwh * (
        tariff.dispatch_per_kwh_reference + tariff.regulated_per_kwh_reference
    ))
    fixed = euro(months * (
        tariff.sale_fixed_per_month
        + tariff.dispatch_fixed_per_month_reference
        + tariff.network_fixed_per_month_reference
    ))
    # In fattura la quota potenza viene arrotondata per mese, non solo sul
    # totale bimestrale (10 kW: 19,77 + 19,77 = 39,54 euro).
    power = euro(months * euro(power_kw * tariff.power_per_kw_month_reference))
    excise = euro(kwh * tariff.excise_per_kwh_reference)
    taxable = consumption + fixed + power + excise + D(adjustments_eur)
    vat = euro(taxable * tariff.vat)
    return {
        "kwh": kwh, "consumption": consumption, "fixed": fixed,
        "power": power, "excise": excise, "vat": vat,
        "canone": D(canone_eur), "adjustments": D(adjustments_eur),
        "total": euro(taxable + vat + D(canone_eur)),
    }


def reconcile_invoice(row: dict) -> Decimal:
    """Verifica lo scontrino storico, con i totali già arrotondati in fattura."""
    taxable = sum((D(row[k]) for k in ("consumption", "fixed", "power", "excise", "taxable_adjustments")), D(0))
    reconstructed = euro(taxable + euro(taxable * D("0.10")) + D(row["canone"]) + D(row["non_taxable_adjustments"]))
    if reconstructed != D(row["total"]):
        raise ValueError(f"fattura {row['period']} non riconciliata")
    return reconstructed

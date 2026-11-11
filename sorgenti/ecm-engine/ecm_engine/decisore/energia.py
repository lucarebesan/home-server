"""Giudizio energetico di un candidato e profilo orario del carico della casa."""
from datetime import datetime
from statistics import median

from .parametri import BATTERIA_WH, DUTY_NOTTE, IMPORT_MAX_W, RISERVA_SOC, SCARICA_MAX_W
from .tipi import Contesto


def giudica(c: Contesto, vel: int, w: float, accumulo_attivo: bool) -> tuple[bool, str]:
    """(ammesso, motivo) per un candidato acceso con consumo w."""
    if vel == 0:
        return True, ""
    if c.notte:
        if c.soc is None or c.carico_notte_wh is None:
            return False, "dati energia notturni mancanti"
        wh = c.carico_notte_wh + w * c.ore_al_mattino * DUTY_NOTTE
        soc_prev = c.soc - wh / BATTERIA_WH * 100
        if soc_prev < RISERVA_SOC:
            return False, f"SOC previsto al mattino {soc_prev:.0f}% sotto riserva {RISERVA_SOC:.0f}%"
        return True, f"SOC previsto al mattino {soc_prev:.0f}%"
    if not accumulo_attivo:
        if c.consenso_fv is None:
            if c.pv is None or c.load is None:
                return False, "dati energia mancanti"
            ok = c.pv - c.load >= w
            return ok, "eccedenza FV sufficiente" if ok else "eccedenza FV insufficiente"
        return (True, "consenso FV/batteria") if c.consenso_fv else (False, "nessun consenso FV/batteria")
    if c.imp is None or c.discharge is None:
        return False, "dati energia mancanti"
    if c.imp > IMPORT_MAX_W:
        return False, f"prelievo da rete {c.imp:.0f} W"
    if c.discharge > SCARICA_MAX_W and (c.pv or 0) < (c.load or 0):
        return False, f"scarica batteria {c.discharge:.0f} W"
    return True, "bilancio favorevole"


class ProfiloCarico:
    """Mediana del carico della casa per ora del giorno (ora locale)."""

    def __init__(self, dal_ts: int = 0):
        self.dal_ts = dal_ts
        self._per_ora: dict[int, list] = {}

    def feed(self, row: dict) -> None:
        ts, load = row.get("ts"), row.get("load")
        if not isinstance(ts, int) or ts < self.dal_ts or not isinstance(load, (int, float)):
            return
        self._per_ora.setdefault(datetime.fromtimestamp(ts).hour, []).append(load)

    def result(self) -> dict:
        return {h: median(v) for h, v in self._per_ora.items() if v}


def carico_fino_a(profilo: dict, da: datetime, a: datetime) -> float | None:
    """Wh previsti dal profilo fra da e a (None se il profilo non copre tutte le ore)."""
    if a <= da:
        return 0.0
    tot, t = 0.0, da
    while t < a:
        if t.hour not in profilo:
            return None
        prossima = t.replace(minute=0, second=0, microsecond=0).timestamp() + 3600
        fine = min(prossima, a.timestamp())
        tot += profilo[t.hour] * (fine - t.timestamp()) / 3600
        t = datetime.fromtimestamp(fine)
    return tot

"""Frasi semplici per Luca e righe della tabella di dettaglio."""
from .combo import descrizione
from .learner import EFF_MIN, ranking

VERBO = {"HEAT": "scaldare", "COOL": "raffrescare"}


def best_line(stats, tipo, f, stagione) -> str:
    r = [s for s in ranking(stats, tipo, f) if s.costo is not None]
    if not r:
        return f"Per {VERBO[tipo]}: non ho ancora abbastanza dati"
    s = r[0]
    return (f"Per {VERBO[tipo]} adesso conviene: {descrizione(s.code, stagione)} "
            f"(circa {round(s.p_tot)} W)")


def summary_lines(stats, stagione, f, pct) -> list[str]:
    tipo = "HEAT" if stagione == "INVERNO" else "COOL"
    lines = [best_line(stats, tipo, f, stagione)]
    for s in ranking(stats, tipo, f):
        if s.affidabilita >= 0.4 and s.eff < EFF_MIN:
            lines.append(f"{descrizione(s.code, stagione)}: non rende con questo clima esterno")
    lines.append(f"Ho imparato il {pct}% di quello che serve per {VERBO[tipo]}")
    return lines


def detail_rows(stats, f, stagione) -> list[dict]:
    rows = []
    for s in sorted((s for s in stats.values() if s.fascia == f), key=lambda s: s.code):
        rows.append({
            "codice": f"E{s.code}", "descrizione": descrizione(s.code, stagione),
            "W": round(s.p_tot), "duty": round(s.duty_cp, 2),
            "zg": round(s.eff_zg, 2), "zn": round(s.eff_zn, 2),
            "costo": round(s.costo) if s.costo is not None else None,
            "periodi": s.periodi, "affidabilita": round(s.affidabilita, 2),
        })
    return rows

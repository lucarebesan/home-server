"""Frasi semplici per Luca e righe della tabella di dettaglio."""
from .combo import descrizione
from .learner import EFF_MIN, ranking

VERBO = {"HEAT": "scaldare", "COOL": "raffrescare"}
TIPI = {"HEAT": ("HEAT",), "COOL": ("COOL", "DRY")}   # d'estate anche la deumidifica raffresca
SOGLIA = 0.4


def _consigliati(stats, tipo, f):
    """Ranking con costo noto: prima i dati affidabili, poi gli altri (ordine interno invariato)."""
    r = [s for s in ranking(stats, TIPI[tipo], f) if s.costo is not None]
    return [s for s in r if s.affidabilita >= SOGLIA] + [s for s in r if s.affidabilita < SOGLIA]


def best_line(stats, tipo, f, stagione) -> str:
    r = _consigliati(stats, tipo, f)
    if not r:
        return f"Per {VERBO[tipo]}: non ho ancora abbastanza dati"
    s = r[0]
    line = (f"Per {VERBO[tipo]} adesso conviene: {descrizione(s.code, stagione)} "
            f"(circa {round(s.p_tot)} W)")
    return line + " (da confermare)" if s.affidabilita < SOGLIA else line


def summary_lines(stats, stagione, f, pct) -> list[str]:
    tipo = "HEAT" if stagione == "INVERNO" else "COOL"
    lines = [best_line(stats, tipo, f, stagione)]
    for s in ranking(stats, TIPI[tipo], f):
        if s.affidabilita >= SOGLIA and s.eff < EFF_MIN:
            lines.append(f"{descrizione(s.code, stagione)}: non rende con questo clima esterno")
    lines.append(f"Ho imparato il {pct}% di quello che serve per {VERBO[tipo]}")
    return lines


def detail_rows(stats, f, stagione) -> list[dict]:
    rows = []
    for s in sorted((s for s in stats.values() if s.fascia == f), key=lambda s: s.code):
        rows.append({
            "codice": f"E{s.code}", "descrizione": descrizione(s.code, stagione),
            "W": round(s.p_tot),
            "W_cp_on": round(s.p_cp_on) if s.p_cp_on is not None else None, "duty": round(s.duty_cp, 2),
            "zg": round(s.eff_zg, 2), "zn": round(s.eff_zn, 2),
            "costo": round(s.costo) if s.costo is not None else None,
            "periodi": s.periodi, "affidabilita": round(s.affidabilita, 2),
            "fascia": s.fascia, "da_confermare": s.affidabilita < SOGLIA,
        })
    return rows

"""Frasi semplici per Luca e righe della tabella di dettaglio."""
import time as _time
from datetime import datetime

from .combo import descrizione
from .learner import EFF_MIN, ranking
from .rules import AUTO_MAX_PER_DAY, MARGINE, MARGINE_HEAT_START

VERBO = {"HEAT": "scaldare", "COOL": "raffrescare"}
TIPI = {"HEAT": ("HEAT",), "COOL": ("COOL", "DRY")}   # d'estate anche la deumidifica raffresca
SOGLIA = 0.4


def _consigliati(stats, tipo, f):
    """Ranking con costo noto: prima i dati affidabili, poi gli altri (ordine interno invariato)."""
    r = [s for s in ranking(stats, TIPI[tipo], f) if s.costo is not None]
    return [s for s in r if s.affidabilita >= SOGLIA] + [s for s in r if s.affidabilita < SOGLIA]


def best_stat(stats, tipo, f):
    """La combinazione consigliata (stessa preferenza della frase), o None."""
    r = _consigliati(stats, tipo, f)
    return r[0] if r else None


def best_attrs(stats, tipo, f) -> dict:
    s = best_stat(stats, tipo, f)
    if s is None:
        return {}
    return {"codice": f"E{s.code}", "W": round(s.p_tot), "eff_c_h": round(s.eff, 2),
            "affidabilita": round(s.affidabilita, 2), "da_confermare": s.affidabilita < SOGLIA}


def best_line(stats, tipo, f, stagione) -> str:
    s = best_stat(stats, tipo, f)
    if s is None:
        return f"Per {VERBO[tipo]}: non ho ancora abbastanza dati"
    line = (f"Per {VERBO[tipo]} adesso conviene: {descrizione(s.code, stagione)} "
            f"(circa {round(s.p_tot)} W)")
    return line + " (da confermare)" if s.affidabilita < SOGLIA else line


def summary_lines(stats, stagione, f) -> list[str]:
    tipo = "HEAT" if stagione == "INVERNO" else "COOL"
    lines = [best_line(stats, tipo, f, stagione)]
    for s in ranking(stats, TIPI[tipo], f):
        if s.affidabilita >= SOGLIA and s.eff < EFF_MIN:
            lines.append(f"{descrizione(s.code, stagione)}: non rende con questo clima esterno")
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


def _t(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def blocco_testo(code: str, c) -> str:
    """Motivo di blocco interno -> frase per Luca."""
    fissi = {
        "modalità manuale già attiva": "È già attiva una combinazione manuale.",
        "stato manuale sconosciuto": "Stato della modalità manuale non disponibile.",
        "free cooling attivo": "È attivo il Free Cooling.",
        "ciclo ACS in corso": "È in corso il riscaldamento dell'acqua calda.",
        "energia insufficiente": "Batteria sotto il 40% e fotovoltaico inferiore al consumo della casa.",
        "fuori finestra prove automatiche": "Fuori dall'orario delle prove automatiche (10–17).",
        f"già {AUTO_MAX_PER_DAY} prove oggi": f"Fatte già {AUTO_MAX_PER_DAY} prove automatiche oggi.",
        "pausa tra le prove": "Sono passati meno di 60 minuti dall'ultima prova.",
        "prova già in corso": "C'è già una prova in corso.",
        "prova in corso": "C'è già una prova in corso.",
        "dati non aggiornati": "Dati di Home Assistant non aggiornati.",
        "dati non disponibili": "Mancano alcune letture dei sensori.",
        "nessuna combinazione provabile con queste temperature":
            "Con le temperature attuali non c'è nessuna prova possibile.",
    }
    if code in fissi:
        return fissi[code]
    if c is not None:
        if code == "zona troppo calda per scaldare":
            return f"La casa è già calda: una zona supera {_t(c.soglia_estate - MARGINE_HEAT_START)} °C."
        if code in ("zona troppo fredda per raffrescare", "zona troppo fredda"):
            return f"Una zona è sotto {_t(c.lim_inf + MARGINE)} °C."
        if code == "zona troppo calda":
            return f"Una zona supera {_t(c.lim_sup)} °C."
    return code[:1].upper() + code[1:] + "."


ESITI = {
    "completata": "Completata",
    "interrotta dall'utente": "Interrotta a mano",
    "zona oltre il limite superiore": "Interrotta: casa troppo calda",
    "zona vicina al cambio stagione": "Interrotta: casa troppo calda",
    "zona troppo calda": "Interrotta: casa troppo calda",
    "zona sotto il limite inferiore": "Interrotta: casa troppo fredda",
    "batteria sotto 25%": "Interrotta: batteria sotto il 25%",
    "dati mancanti": "Interrotta: mancavano letture dei sensori",
    "durata superata": "Chiusa dal sistema: durata superata",
    "stato manuale sconosciuto": "Interrotta: stato della modalità manuale non disponibile",
    "interrotta dal riavvio del motore": "Interrotta: riavvio del sistema",
    "avvio fallito": "Non partita: errore di comando",
}


def esito_testo(esito: str | None) -> str:
    if esito is None:
        return "In corso"
    if esito in ESITI:
        return ESITI[esito]
    return esito[:1].upper() + esito[1:]


def storico_rows(tests, stagione, now=None) -> list[dict]:
    now = _time.time() if now is None else now
    rows = []
    for t in tests:
        fine = t.get("fine")
        rows.append({
            "quando": datetime.fromtimestamp(t["inizio"]).strftime("%d/%m %H:%M"),
            "combinazione": descrizione(t["code"], stagione),
            "avvio": "A mano" if t["origine"] == "manuale" else "Automatico",
            "durata": f"{round(((fine if fine is not None else now) - t['inizio']) / 60)} di {t['durata_min']} min",
            "esito": esito_testo(t.get("esito")),
        })
    return rows


def da_misurare_rows(proposals, stats, f, stagione) -> list[dict]:
    rows = []
    for p in proposals:
        st = stats.get((p.code, p.tipo, f))
        misure = int(st.affidabilita * 100) if st else 0
        if misure >= 100:
            continue
        rows.append({"ordine": len(rows) + 1, "combinazione": descrizione(p.code, stagione),
                     "misure": misure, "durata": f"{p.durata} min"})
        if len(rows) == 20:
            break
    return rows

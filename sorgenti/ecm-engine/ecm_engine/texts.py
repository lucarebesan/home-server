"""Frasi semplici per Luca e righe della tabella di dettaglio."""
import time as _time
from datetime import datetime

from .combo import U_V1_OFF, descrizione, tipo_of
from .learner import EFF_MIN, ranking
from .power_learner import combo_w
from .rules import AUTO_MAX_PER_DAY, MARGINE, MARGINE_HEAT_START

_BLOCCHI_ZONA = ("zona troppo calda per scaldare", "zona troppo fredda per raffrescare",
                 "zona troppo fredda", "zona troppo calda")

VERBO = {"HEAT": "scaldare", "COOL": "raffrescare"}
TIPI = {"HEAT": ("HEAT",), "COOL": ("COOL", "DRY")}   # d'estate anche la deumidifica raffresca
SOGLIA = 0.4


def _consigliati(stats, tipo, f):
    """Ranking con costo noto: prima i dati affidabili, poi gli altri (ordine interno invariato)."""
    # V1 (u>=7) e' solo osservato: non e' selezionabile su 09, quindi non si consiglia
    r = [s for s in ranking(stats, TIPI[tipo], f) if s.costo is not None and s.code % 10 < U_V1_OFF]
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


TIPI_STAGIONE = {"INVERNO": ("HEAT", "NEUTRO"), "ESTATE": ("COOL", "DRY", "NEUTRO")}
TIPO_TESTO = {"HEAT": "caldo", "COOL": "freddo"}


def _descr_riga(s, stagione) -> str:
    """Solo CP acceso (d=0): lo stesso codice esiste per caldo e freddo, sono modi fisici diversi."""
    d = descrizione(s.code, stagione)
    if s.code // 10 == 0 and s.tipo in TIPO_TESTO:
        d += f" ({TIPO_TESTO[s.tipo]})"
    return d


def detail_rows(stats, f, stagione, power_stats=None) -> list[dict]:
    rows = []
    tipi = TIPI_STAGIONE.get((stagione or "").strip().upper())
    sel = [s for s in stats.values() if s.fascia == f and (tipi is None or s.tipo in tipi)]
    measured = {s.code: s for s in sel}
    if power_stats is None:
        entries = [(s.code, s) for s in sorted(sel, key=lambda s: (s.code, s.tipo))]
    else:
        from .rules import codes_for_season
        entries = [(code, measured.get(code))
                   for code in sorted(set(codes_for_season(stagione, False)) | set(measured))]
    for code, s in entries:
        row = {
            "codice": f"E{code}", "descrizione": _descr_riga(s, stagione) if s else descrizione(code, stagione),
            "W": round(s.p_tot) if s else None,
            "W_cp_on": round(s.p_cp_on) if s and s.p_cp_on is not None else None,
            "duty": round(s.duty_cp, 2) if s else None,
            "zg": round(s.eff_zg, 2) if s else None,
            "zn": round(s.eff_zn, 2) if s else None,
            "costo": round(s.costo) if s and s.costo is not None else None,
            "periodi": s.periodi if s else 0, "affidabilita": round(s.affidabilita, 2) if s else 0.0,
            "fascia": f, "da_confermare": s is None or s.affidabilita < SOGLIA,
        }
        if power_stats is not None:
            estimate, cp, tosh = combo_w(power_stats, code, f, stagione)
            if s is None:
                row["W"] = estimate
            row["origine_W"] = "misura diretta" if s else ("somma CP+SPLIT" if estimate is not None else "dati mancanti")
            row["W_stimati"] = estimate
            row["minuti_cp"] = cp.minuti if cp else 0
            row["minuti_split"] = tosh.minuti if tosh else 0
            row["criterio_affidabilita"] = "W" if (s.tipo if s else tipo_of(code, stagione)) == "NEUTRO" else "temperatura"
        rows.append(row)
    return rows


def _t(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def blocco_testo(code: str, c) -> str:
    """Motivo di blocco interno -> frase per Luca."""
    fissi = {
        "write spenta": "Il comando delle macchine (00-NILAN WRITE) è spento.",
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
    "comando macchine spento": "Interrotta: comando delle macchine spento",
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


SEZ_ORA, SEZ_NON_ORA, SEZ_FATTE = "Provabili adesso", "Non provabili adesso", "Già misurate"


def da_misurare_rows(proposals, esclusi, stats, f, stagione, c=None) -> list[dict]:
    """Tutte le combinazioni della stagione, in tre sezioni: provabili adesso (nell'ordine
    di propose), non provabili adesso (con il motivo), già misurate (100%)."""
    def misure(code, tipo):
        st = stats.get((code, tipo, f))
        return int(st.affidabilita * 100) if st else 0

    ora, non_ora, fatte = [], [], []
    for p in proposals:
        m = misure(p.code, p.tipo)
        row = {"combinazione": descrizione(p.code, stagione), "misure": m, "durata": f"{p.durata} min"}
        if m >= 100:
            fatte.append((p.code, row))
        else:
            ora.append({"sezione": SEZ_ORA, "ordine": len(ora) + 1, **row})
    for code, why in sorted(esclusi):
        m = misure(code, tipo_of(code, stagione))
        row = {"combinazione": descrizione(code, stagione), "misure": m}
        if m >= 100:
            fatte.append((code, row))
        else:
            motivo = blocco_testo(why, c) if why in _BLOCCHI_ZONA else why[:1].upper() + why[1:]
            non_ora.append({"sezione": SEZ_NON_ORA, "motivo": motivo, **row})
    return ora + non_ora + [{"sezione": SEZ_FATTE, **r} for _, r in sorted(fatte, key=lambda x: x[0])]

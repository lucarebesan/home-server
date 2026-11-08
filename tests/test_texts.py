from ecm_engine.texts import best_line, blocco_testo, detail_rows, summary_lines
from ecm_engine.learner import aggregate
from ecm_engine.segmenter import Period

def per(code, tipo="HEAT", p=450.0, s=1.0, t_ext=8.0):
    return Period(code, tipo, 0, 1, 20, p, 0.0, p, 1.0, 0.0, s, s, t_ext, False)

def test_best_line():
    stats = aggregate([per(82)] * 5)
    assert best_line(stats, "HEAT", "5-10", "INVERNO") == \
        "Per scaldare adesso conviene: Nilan solo ventilazione V3 + Toshiba caldo media (circa 450 W)"
    assert best_line({}, "HEAT", "5-10", "INVERNO") == "Per scaldare: non ho ancora abbastanza dati"

def test_summary_mentions_useless_combo():
    stats = aggregate([per(82)] * 5 + [per(6, p=700, s=0.02)] * 5)
    lines = summary_lines(stats, "INVERNO", "5-10")
    assert any("non rende" in l and "Nilan pompa di calore V4" in l for l in lines)
    assert not any("Ho imparato" in l for l in lines)

def test_detail_rows_sorted_and_compact():
    stats = aggregate([per(82)] * 2 + [per(5)])
    rows = detail_rows(stats, "5-10", "INVERNO")
    assert [r["codice"] for r in rows] == ["E5", "E82"]
    assert set(rows[0]) == {"codice", "descrizione", "W", "W_cp_on", "duty", "zg", "zn", "costo", "periodi",
                           "affidabilita", "fascia", "da_confermare"}

def test_best_line_da_confermare():
    stats = aggregate([per(82)] * 1)
    assert best_line(stats, "HEAT", "5-10", "INVERNO").endswith("(circa 450 W) (da confermare)")

def test_best_line_prefers_reliable():
    stats = aggregate([per(82, p=900)] * 5 + [per(84, p=300)] * 1)
    line = best_line(stats, "HEAT", "5-10", "INVERNO")
    assert "900 W" in line and "da confermare" not in line

def test_summer_cool_includes_dry():
    stats = aggregate([per(14, "DRY", p=200, s=-1.0, t_ext=27)] * 5 + [per(45, "COOL", p=600, s=-1.0, t_ext=27)] * 5)
    line = best_line(stats, "COOL", "25-30", "ESTATE")
    assert "deumidifica" in line and "200 W" in line

def test_detail_rows_new_keys():
    p = per(5)
    p.p_cp_on = 700.0
    rows = detail_rows(aggregate([p] * 5 + [per(82)]), "5-10", "INVERNO")
    r5, r82 = rows[0], rows[1]
    assert r5["fascia"] == "5-10" and r5["da_confermare"] is False and r5["W_cp_on"] == 700
    assert r82["da_confermare"] is True and r82["W_cp_on"] is None


def test_best_stat_and_attrs():
    from ecm_engine.texts import best_attrs, best_stat
    stats = aggregate([per(82)] * 5 + [per(6, p=700, s=0.5)] * 2)
    s = best_stat(stats, "HEAT", "5-10")
    assert s.code == 82
    assert best_stat({}, "HEAT", "5-10") is None
    assert best_attrs({}, "HEAT", "5-10") == {}
    a = best_attrs(stats, "HEAT", "5-10")
    assert a == {"codice": "E82", "W": 450, "eff_c_h": 1.0, "affidabilita": 1.0, "da_confermare": False}


def _ctx(**kw):
    from datetime import datetime, time
    from ecm_engine.rules import Ctx
    d = dict(now=datetime(2026, 1, 5, 12), stagione="INVERNO", manuale="AUTO", free_cooling="DISATTIVATO",
             acs_attivo=False, soc=80, pv=0, load=0, t_zg=21, t_zn=21, lim_inf=20.0, lim_sup=21.7,
             mattina=time(7), serale=time(22), t_ext=8.0, soglia_estate=24.5)
    d.update(kw)
    return Ctx(**d)


def test_blocco_testo_fissi():
    assert blocco_testo("modalità manuale già attiva", None) == "È già attiva una combinazione manuale."
    assert blocco_testo("ciclo ACS in corso", None) == "È in corso il riscaldamento dell'acqua calda."
    assert blocco_testo("prova in corso", None) == "C'è già una prova in corso."
    assert blocco_testo("prova già in corso", None) == "C'è già una prova in corso."
    assert blocco_testo("già 3 prove oggi", None) == "Fatte già 3 prove automatiche oggi."
    assert blocco_testo("dati non disponibili", None) == "Mancano alcune letture dei sensori."


def test_blocco_testo_con_numeri():
    c = _ctx()
    assert blocco_testo("zona troppo calda per scaldare", c) == "La casa è già calda: una zona supera 23,5 °C."
    assert blocco_testo("zona troppo fredda", c) == "Una zona è sotto 20,3 °C."
    assert blocco_testo("zona troppo fredda per raffrescare", c) == "Una zona è sotto 20,3 °C."
    assert blocco_testo("zona troppo calda", c) == "Una zona supera 21,7 °C."


def test_blocco_testo_sconosciuto():
    assert blocco_testo("qualcosa di nuovo", None) == "Qualcosa di nuovo."

def test_esito_testo():
    from ecm_engine.texts import esito_testo
    assert esito_testo(None) == "In corso"
    assert esito_testo("interrotta dall'utente") == "Interrotta a mano"
    assert esito_testo("zona troppo calda") == "Interrotta: casa troppo calda"
    assert esito_testo("zona sotto il limite inferiore") == "Interrotta: casa troppo fredda"
    assert esito_testo("batteria sotto 25%") == "Interrotta: batteria sotto il 25%"
    assert esito_testo("avvio fallito") == "Non partita: errore di comando"
    assert esito_testo("boh") == "Boh"

def test_storico_rows():
    from datetime import datetime
    from ecm_engine.texts import storico_rows
    t0 = int(datetime(2026, 11, 7, 11, 5).timestamp())
    tests = [{"code": 82, "durata_min": 20, "origine": "auto", "inizio": t0, "fine": t0 + 600, "esito": "completata"},
             {"code": 5, "durata_min": 30, "origine": "manuale", "inizio": t0, "fine": None, "esito": None}]
    r = storico_rows(tests, "INVERNO", now=t0 + 300)
    assert r[0] == {"quando": "07/11 11:05", "combinazione": "Nilan solo ventilazione V3 + Toshiba caldo media",
                    "avvio": "Automatico", "durata": "10 di 20 min", "esito": "Completata"}
    assert r[1]["avvio"] == "A mano" and r[1]["durata"] == "5 di 30 min" and r[1]["esito"] == "In corso"

def test_da_misurare_rows():
    from ecm_engine.rules import Proposal
    from ecm_engine.texts import da_misurare_rows
    stats = aggregate([per(82)] * 5 + [per(5)] * 2)
    props = [Proposal(6, "HEAT", 30, "x"), Proposal(5, "HEAT", 20, "x"), Proposal(82, "HEAT", 20, "x")]
    rows = da_misurare_rows(props, stats, "5-10", "INVERNO")
    assert [r["ordine"] for r in rows] == [1, 2]
    assert rows[0]["misure"] == 0 and rows[0]["durata"] == "30 min"
    assert 0 < rows[1]["misure"] < 100
    many = [Proposal(6, "HEAT", 30, "x")] * 30
    assert len(da_misurare_rows(many, {}, "5-10", "INVERNO")) == 20


def test_testi_write():
    from ecm_engine.texts import esito_testo
    assert blocco_testo("write spenta", None) == "Il comando delle macchine (00-NILAN WRITE) è spento."
    assert esito_testo("comando macchine spento") == "Interrotta: comando delle macchine spento"


def test_best_stat_ignores_v1_not_commandable():
    from ecm_engine.texts import best_stat
    stats = aggregate([per(88, p=100, s=2.0)] * 5 + [per(82)] * 5)
    assert best_stat(stats, "HEAT", "5-10").code == 82

def test_detail_rows_v1_described():
    rows = detail_rows(aggregate([per(7, "NEUTRO", s=0.0)] * 2 + [per(88)] * 2), "5-10", "INVERNO")
    d = {r["codice"]: r["descrizione"] for r in rows}
    assert d["E7"] == "Nilan solo ventilazione V1 + Toshiba spento"
    assert d["E88"].startswith("Nilan pompa di calore V1")

def test_detail_rows_season_filter():
    stats = aggregate([per(82)] * 2 + [per(0, "NEUTRO")] * 2 + [per(14, "DRY", t_ext=8.0)] * 2
                      + [per(45, "COOL", t_ext=8.0)] * 2)
    inv = [r["codice"] for r in detail_rows(stats, "5-10", "INVERNO")]
    assert inv == ["E0", "E82"]
    est = [r["codice"] for r in detail_rows(stats, "5-10", "ESTATE")]
    assert est == ["E0", "E14", "E45"]

def test_detail_rows_cp_on_without_toshiba_shows_tipo():
    stats = aggregate([per(4, "HEAT")] * 2 + [per(4, "COOL", s=-1.0)] * 2 + [per(0, "NEUTRO")] * 2)
    rows = detail_rows(stats, "5-10", "ALTRO")
    e4 = [r for r in rows if r["codice"] == "E4"]
    assert sorted(r["descrizione"] for r in e4) == ["Nilan pompa di calore V2 + Toshiba spento (caldo)",
                                                    "Nilan pompa di calore V2 + Toshiba spento (freddo)"]
    e0 = [r for r in rows if r["codice"] == "E0"][0]
    assert "(" not in e0["descrizione"]
    inv = [r for r in detail_rows(stats, "5-10", "INVERNO") if r["codice"] == "E4"]
    assert len(inv) == 1 and inv[0]["descrizione"].endswith("(caldo)")

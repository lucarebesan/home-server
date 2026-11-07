from ecm_engine.texts import best_line, detail_rows, summary_lines
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
    lines = summary_lines(stats, "INVERNO", "5-10", 40)
    assert any("non rende" in l and "Nilan pompa di calore V4" in l for l in lines)
    assert any("40%" in l for l in lines)

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

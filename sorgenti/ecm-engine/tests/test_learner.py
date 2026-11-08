import pytest
from ecm_engine.learner import aggregate, fascia, learning_pct, ranking
from ecm_engine.segmenter import Period

def per(code, tipo="HEAT", p=500.0, s=1.0, t_ext=8.0, minutes=20):
    return Period(code, tipo, 0, 1, minutes, p, 0.0, p, 1.0, 0.0, s, s, t_ext, False)

def test_fascia():
    assert fascia(4.9) == "<5" and fascia(5) == "5-10" and fascia(31) == "≥30"

def test_aggregate_heat():
    st = aggregate([per(5, s=1.0), per(5, s=1.2)])[(5, "HEAT", "5-10")]
    assert st.periodi == 2 and abs(st.eff - 1.1) < 1e-9
    assert abs(st.costo - 500 / 1.1) < 1e-6
    assert abs(st.affidabilita - 0.4) < 1e-9

def test_cool_sign_and_wrong_direction():
    st = aggregate([per(45, "COOL", s=-0.5, t_ext=27)])[(45, "COOL", "25-30")]
    assert st.eff == 0.5
    st2 = aggregate([per(84, s=-0.2)])[(84, "HEAT", "5-10")]
    assert st2.costo is None

def test_incoherent_penalty():
    st = aggregate([per(5, s=0.2), per(5, s=2.0)])[(5, "HEAT", "5-10")]
    assert abs(st.affidabilita - 0.4 * 0.6) < 1e-9

def test_ranking_and_fallback():
    stats = aggregate([per(5, p=500, s=1.0), per(84, p=300, s=1.0), per(96, p=900, s=0.05),
                       per(85, p=400, s=1.0, t_ext=12)])
    r = ranking(stats, "HEAT", "5-10")
    assert [x.code for x in r] == [84, 5, 96]
    r2 = ranking(stats, "HEAT", "<5")   # vuota -> fascia vicina
    assert [x.code for x in r2] == [84, 5, 96]

def test_learning_pct():
    stats = aggregate([per(5)] * 5)
    assert learning_pct(stats, [5, 6], "5-10", "INVERNO") == 50

def test_same_code_both_seasons_separate():
    stats = aggregate([per(5, "HEAT", s=1.0), per(5, "COOL", s=-0.5)])
    assert set(stats) == {(5, "HEAT", "5-10"), (5, "COOL", "5-10")}
    assert learning_pct(stats, [5], "5-10", "INVERNO") == round(100 * 0.2)
    assert [s.tipo for s in ranking(stats, "COOL", "5-10")] == ["COOL"]

def test_all_zero_slopes_penalised():
    st = aggregate([per(5, s=0.0), per(5, s=0.0)])[(5, "HEAT", "5-10")]
    assert abs(st.affidabilita - 0.4 * 0.6) < 1e-9

def test_fascia_not_finite():
    for v in (None, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            fascia(v)

def test_p_cp_on_weighted():
    a = per(5, minutes=10); a.p_cp_on = 1000.0; a.duty_cp = 1.0
    b = per(5, minutes=30); b.p_cp_on = 2000.0; b.duty_cp = 0.5
    c = per(5, minutes=10); c.p_cp_on = None; c.duty_cp = 0.0
    st = aggregate([a, b, c])[(5, "HEAT", "5-10")]
    assert abs(st.p_cp_on - (1000 * 10 + 2000 * 15) / 25) < 1e-9
    assert aggregate([c])[(5, "HEAT", "5-10")].p_cp_on is None

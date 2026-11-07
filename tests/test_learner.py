from ecm_engine.learner import aggregate, fascia, learning_pct, ranking
from ecm_engine.segmenter import Period

def per(code, tipo="HEAT", p=500.0, s=1.0, t_ext=8.0, minutes=20):
    return Period(code, tipo, 0, 1, minutes, p, 0.0, p, 1.0, 0.0, s, s, t_ext, False)

def test_fascia():
    assert fascia(4.9) == "<5" and fascia(5) == "5-10" and fascia(31) == "≥30"

def test_aggregate_heat():
    st = aggregate([per(5, s=1.0), per(5, s=1.2)])[(5, "5-10")]
    assert st.periodi == 2 and abs(st.eff - 1.1) < 1e-9
    assert abs(st.costo - 500 / 1.1) < 1e-6
    assert abs(st.affidabilita - 0.4) < 1e-9

def test_cool_sign_and_wrong_direction():
    st = aggregate([per(45, "COOL", s=-0.5, t_ext=27)])[(45, "25-30")]
    assert st.eff == 0.5
    st2 = aggregate([per(84, s=-0.2)])[(84, "5-10")]
    assert st2.costo is None

def test_incoherent_penalty():
    st = aggregate([per(5, s=0.2), per(5, s=2.0)])[(5, "5-10")]
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
    assert learning_pct(stats, [5, 6], "5-10") == 50

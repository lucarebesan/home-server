from ecm_engine.power_learner import PowerLearner, combo_w
from ecm_engine.texts import detail_rows


def sample(minute, code, cp_w, split_w):
    return {"ts": minute * 60, "code": code, "stagione": "INVERNO", "valido": 1,
            "t_ext": 10.5, "p_cp": cp_w, "p_tosh": split_w}


def test_each_machine_keeps_its_own_run_when_the_other_changes():
    learner = PowerLearner()
    for minute in range(80):
        if minute < 20:
            code, cp_w, split_w = 70, 5, 300 if minute < 5 else 1000
        elif minute < 40:
            code, cp_w, split_w = 74, 50 if minute < 25 else 500, 1000
        elif minute < 60:
            code, cp_w, split_w = 75, 530, 1000
        else:
            code, cp_w, split_w = 80, 5, 400 if minute < 65 else 1100
        learner.feed(sample(minute, code, cp_w, split_w))
    result = learner.result()

    # The Toshiba V1 run spans both CP speed changes: 55 useful minutes, one period.
    assert result[("INVERNO", "tosh", 7, "10-15")].minuti == 55
    assert result[("INVERNO", "tosh", 7, "10-15")].periodi == 1
    assert result[("INVERNO", "tosh", 7, "10-15")].W == 1000
    assert result[("INVERNO", "cp", 4, "10-15")].W == 500
    assert result[("INVERNO", "tosh", 8, "10-15")].W == 1100

    # E84 was never observed as a pair, yet both components have measurements.
    assert combo_w(result, 84, "10-15", "INVERNO")[0] == 1600
    rows = detail_rows({}, "10-15", "INVERNO", result)
    e84 = next(r for r in rows if r["codice"] == "E84")
    assert len(rows) == 28
    assert e84["W"] == 1600
    assert e84["origine_W"] == "somma CP+SPLIT"
    assert e84["periodi"] == 0 and e84["zg"] is None


def test_missing_component_does_not_invent_power():
    learner = PowerLearner()
    for minute in range(15):
        learner.feed(sample(minute, 70, 5, 1000))
    result = learner.result()
    assert combo_w(result, 74, "10-15", "INVERNO")[0] is None

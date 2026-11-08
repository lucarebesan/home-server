"""Resistenza ACS: classificazione e correzione del consumo Nilan."""
from ecm_engine.combo import RESISTENZA_ACS, classify
from ecm_engine.engine import build_sample, hold_states
from ecm_engine.segmenter import R_ACS_DEFAULT, correct_acs, fix_acs_episode, segment

BASE = {"cp_stato": "STOP VENTILAZIONE", "cp_resistenza": "OFF", "free_cooling": "DISATTIVATO",
        "cp_vent": "OFF", "cp_compressore": "OFF", "tosh_on": "ACCESO", "tosh_modo": "RISCALDAMENTO",
        "tosh_vent": "ALTA", "stagione": "INVERNO"}


def test_resistenza_non_esclude_la_combinazione():
    c = classify(dict(BASE, cp_resistenza="ON"))
    assert (c.code, c.tipo, c.motivo) == (90, "HEAT", RESISTENZA_ACS)
    assert classify(BASE).motivo is None
    s = build_sample(dict(BASE, cp_resistenza="ON", p_cp=1330.0, p_tosh=900.0, t_zg=21.0, t_zn=21.0,
                          t_ext=14.0), 0, None)
    assert s["valido"] == 1 and s["code"] == 90 and s["motivo"] == RESISTENZA_ACS


def _row(ts, p, acs=False, comp=0, code=90):
    return {"ts": ts, "code": code, "tipo": "HEAT", "valido": 1, "motivo": RESISTENZA_ACS if acs else None,
            "p_cp": p, "cp_compressore": comp, "p_tosh": 900.0, "t_zg": 21.0 + ts / 36000,
            "t_zn": 21.0 + ts / 36000, "t_ext": 14.0, "tosh_rps": 1.0, "test_id": None}


def test_fix_episodio_nilan_ferma_con_ritardo_del_contatore():
    # flag acceso ai minuti 0-9, il contatore sale al minuto 1 (a metà) e scende al minuto 11
    pw = [6, 680, 1330, 1320, 1335, 1310, 1325, 1330, 1315, 1340, 1330, 700]
    target = [_row(60 * i, float(p), acs=i < 10) for i, p in enumerate(pw)]
    ctx = [_row(-60 * i, 6.0) for i in range(1, 6)]
    out = fix_acs_episode(target, ctx)
    assert all(0.0 <= r["p_cp"] <= 30.0 for r in out)
    assert out[0]["p_cp"] == 6.0 and out[1]["p_cp"] == 6.0 and out[-1]["p_cp"] == 6.0
    assert out[0]["p_cp_stimato"] is False and out[1]["p_cp_stimato"] is True


def test_fix_episodio_con_compressore_che_cicla():
    # base 6 W (compressore spento) e 480 W (acceso); resistenza 1370 W
    seq = [(0, 6), (1, 480), (1, 480), (0, 6), (1, 480)]
    target = [_row(60 * i, p + 1370.0, acs=True, comp=c) for i, (c, p) in enumerate(seq)]
    ctx = [_row(-60 * (i + 1), p, comp=c) for i, (c, p) in enumerate(seq)]
    assert [r["p_cp"] for r in fix_acs_episode(target, ctx)] == [float(p) for _, p in seq]


def test_fix_senza_contesto_usa_i_minuti_bassi_dell_episodio():
    target = [_row(0, 5.0, acs=True)] + [_row(60 * i, 1300.0, acs=True) for i in range(1, 5)]
    assert [r["p_cp"] for r in fix_acs_episode(target, [])] == [5.0] * 5


def test_correct_acs_stream_e_segmento_continuo():
    rows = [_row(60 * i, 6.0) for i in range(0, 10)]
    rows += [_row(60 * i, 1330.0, acs=True) for i in range(10, 25)]
    rows += [_row(60 * i, 1330.0 if i < 26 else 6.0) for i in range(25, 50)]
    out = list(correct_acs(rows))
    assert [r["ts"] for r in out] == [r["ts"] for r in rows]
    assert max(r["p_cp"] for r in out) == 6.0
    ps = segment(rows)
    assert len(ps) == 1 and ps[0].code == 90 and ps[0].p_cp == 6.0


def test_correct_acs_due_episodi_vicini():
    rows = [_row(60 * i, 1330.0 if 5 <= i < 10 or 20 <= i < 24 else 6.0, acs=5 <= i < 10 or 20 <= i < 24)
            for i in range(40)]
    out = list(correct_acs(rows))
    assert len(out) == 40 and max(r["p_cp"] for r in out) == 6.0


def test_hold_states():
    last = {}
    a = hold_states({"tosh_modo": "RISCALDAMENTO", "p_cp": 5.0}, last, 0)
    assert a["tosh_modo"] == "RISCALDAMENTO"
    assert hold_states({"tosh_modo": "unavailable"}, last, 120)["tosh_modo"] == "RISCALDAMENTO"
    assert hold_states({"tosh_modo": None}, last, 180)["tosh_modo"] == "RISCALDAMENTO"
    assert hold_states({"tosh_modo": "unavailable"}, last, 181)["tosh_modo"] == "unavailable"
    assert R_ACS_DEFAULT > 1000

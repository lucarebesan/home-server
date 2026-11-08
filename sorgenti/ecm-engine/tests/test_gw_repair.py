from ecm_engine.gw_repair import _dev, is_target, rebuild

ROW = {"ts": 600, "valido": 0, "motivo": "toshiba non classificato", "stagione": "INVERNO", "test_id": None,
       "p_cp": 6.0, "p_tosh": 1270.0, "t_zg": 21.2, "t_zn": 21.0, "t_ext": 15.0, "t10": 21.3, "t2": 25.0,
       "tosh_rps": None, "soc": 50.0, "pv": 0.0, "load": 900.0, "imp": 0.0, "discharge": 0.0, "charge": 0.0}
CP = {"cp_vent": "OFF", "cp_compressore": "OFF", "cp_stato": "STOP VENTILAZIONE", "cp_resistenza": "OFF",
      "cp_modo": "RISCALDAMENTO", "mode_act": 1, "t10": 30.0, "t2": 30.0}
SPLIT = {"tosh_on": "ACCESO", "tosh_modo": "RISCALDAMENTO", "tosh_vent": "ALTA"}


def test_rebuild_tiene_le_misure_e_prende_gli_stati_dal_gateway():
    s = rebuild(ROW, CP, SPLIT, None)
    assert s["valido"] == 1 and s["code"] == 90 and s["p_tosh"] == 1270.0 and s["t10"] == 21.3
    s = rebuild(ROW, dict(CP, cp_resistenza="ON"), SPLIT, None)
    assert s["valido"] == 1 and s["motivo"] == "resistenza ACS"
    assert rebuild(ROW, CP, None, None) is None


def test_is_target():
    assert is_target(ROW, CP)
    assert not is_target(dict(ROW, motivo="dato mancante t_ext"), CP)
    assert not is_target(dict(ROW, valido=1, motivo=None), CP)
    assert is_target(dict(ROW, valido=1, motivo=None), dict(CP, cp_resistenza="ON"))


def test_dev_dal_corpo():
    assert _dev({"dev": 2002144}) == 2002144
    assert _dev({"body": '{"DATI":[{"DATI":{"id":"2001969"}}]}'}) == 2001969
    assert _dev({"body": "x"}) is None

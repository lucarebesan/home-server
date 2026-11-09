from ecm_engine.gw_repair import _dev, energy_power, is_target, rebuild

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


def test_energy_power():
    m = {0: {"Totale energia importata": "100.000"}, 600: {"Totale energia importata": "100.050"},
         1200: {"Totale energia importata": "100.050"}, 4000: {"Totale energia importata": "101.000"},
         4600: {"Totale energia importata": "100.900"}, 5200: {"Totale energia importata": None}}
    assert energy_power(m) == [(0, 600, 300.0), (600, 1200, 0.0)]


def test_rebuild_conserva_bollitore_e_marcatori_acs():
    # Il gateway non ha bollitore né marcatori ACS: la riga riparata deve tenere quelli salvati dal vivo.
    row = dict(ROW, t11=45.0, t12=30.0, acs_heat_test=1, acs_source_ok=1)
    s = rebuild(row, dict(CP, cp_resistenza="ON"), SPLIT, None)
    assert (s["t11"], s["t12"], s["acs_heat_test"], s["acs_source_ok"]) == (45.0, 30.0, 1, 1)


def test_rebuild_conserva_aria_e_termometri():
    # Anche T1/T4, bypass, serranda e termometri (età e validità comprese) arrivano solo dal vivo.
    row = dict(ROW, t1=16.0, t4=19.2, serranda=1, t_leo=20.8, bat_leo=70.0, age_leo=45, ok_leo=1,
               u_bagno=61.0)
    s = rebuild(row, dict(CP, cp_resistenza="ON"), SPLIT, None)
    assert (s["t1"], s["t4"], s["serranda"], s["u_bagno"]) == (16.0, 19.2, 1, 61.0)
    assert (s["t_leo"], s["bat_leo"], s["age_leo"], s["ok_leo"]) == (20.8, 70.0, 45, 1)


def test_repair_su_db_non_azzera_le_colonne_acs(tmp_path, monkeypatch):
    import ecm_engine.gw_repair as gr
    from ecm_engine.store import Store
    st = Store(str(tmp_path / "e.db"))
    st.add_samples([dict(ROW, code=None, tipo=None, t11=45.0, t12=30.0, acs_heat_test=1, acs_source_ok=1)])
    monkeypatch.setattr(gr, "decode_cp", lambda raw: CP)
    monkeypatch.setattr(gr, "decode_split", lambda raw: SPLIT)
    _, _, n = gr.repair(st, {600: {}}, {600: {}}, 0, 10_000, apply=True)
    assert n == 1
    r = st.samples_since(0)[0]
    assert r["valido"] == 1 and (r["t11"], r["t12"], r["acs_heat_test"], r["acs_source_ok"]) == (45.0, 30.0, 1, 1)

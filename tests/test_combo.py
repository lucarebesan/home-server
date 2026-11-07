from ecm_engine.combo import classify, descrizione, label_09, tipo_of, vent_idx

BASE = {"stagione": "INVERNO", "free_cooling": "DISATTIVATO", "cp_stato": "RISCALDAMENTO",
        "cp_resistenza": "OFF", "cp_vent": "STEP 3", "cp_compressore": "OFF",
        "tosh_on": "SPENTO", "tosh_modo": "RISCALDAMENTO", "tosh_vent": "MEDIA"}

def s(**kw):
    d = dict(BASE); d.update(kw); return d

def test_cp_off_v3_toshiba_off():
    c = classify(s())
    assert (c.code, c.tipo, c.motivo) == (2, "NEUTRO", None)

def test_cp_on_v3_inverno_is_heat():
    assert classify(s(cp_compressore="ON")).code == 5
    assert classify(s(cp_compressore="ON")).tipo == "HEAT"

def test_cp_on_estate_is_cool():
    assert classify(s(stagione="ESTATE", cp_compressore="ON")).tipo == "COOL"

def test_cp_v0():
    assert classify(s(cp_vent="OFF")).code == 0

def test_cp_on_with_v0_unclassified():
    c = classify(s(cp_vent="OFF", cp_compressore="ON"))
    assert c.code is None and c.motivo == "cp non classificato"

def test_step1_unclassified():
    assert classify(s(cp_vent="STEP 1")).code is None

def test_toshiba_heat_v2_with_cp_off_v4():
    c = classify(s(cp_vent="STEP 4", tosh_on="ACCESO"))
    assert (c.code, c.tipo) == (83, "HEAT")

def test_toshiba_dry_v1_cool_v3():
    assert classify(s(tosh_on="ACCESO", tosh_modo="DEUMIDIFICATORE", tosh_vent="BASSA")).code == 12
    assert classify(s(tosh_on="ACCESO", tosh_modo="RAFFRESCAMENTO", tosh_vent="ALTA")).code == 62

def test_toshiba_auto_speed_unclassified():
    c = classify(s(tosh_on="ACCESO", tosh_vent="AUTOMATICA"))
    assert c.code is None and c.motivo == "toshiba non classificato"

def test_exclusions():
    assert classify(s(cp_stato="ACS")).motivo == "cp_stato ACS"
    assert classify(s(cp_stato="SBRINAMENTO")).motivo == "cp_stato SBRINAMENTO"
    assert classify(s(cp_resistenza="ON")).motivo == "resistenza ACS"
    assert classify(s(free_cooling="ATTIVATO")).motivo == "free cooling"

def test_tipo_of():
    assert tipo_of(0, "INVERNO") == "NEUTRO"
    assert tipo_of(14, "ESTATE") == "DRY"
    assert tipo_of(45, "ESTATE") == "COOL"
    assert tipo_of(96, "INVERNO") == "HEAT"

def test_vent_idx():
    assert [vent_idx(u) for u in range(7)] == [0, 1, 2, 3, 1, 2, 3]

def test_label_09():
    assert label_09(84) == "E84 - CP ON V2 • HEAT V2"
    assert label_09(0) == "E0 - CP OFF V0 • Split OFF"
    assert label_09(13) == "E13 - CP OFF V4 • DRY V1"

def test_descrizione_semplice():
    assert descrizione(84, "INVERNO") == "Nilan pompa di calore V2 + Toshiba caldo media"
    assert descrizione(2, "INVERNO") == "Nilan solo ventilazione V3 + Toshiba spento"

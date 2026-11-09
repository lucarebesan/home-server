from ecm_engine.ha_api import build_template, parse_snapshot


def test_build_template_contains_all():
    t = build_template({"a": "sensor.x", "b": "input_select.y"})
    assert "states('sensor.x')" in t and "tojson" in t and "'b'" in t


def test_parse_snapshot_numeric():
    raw = {"p_cp": "512", "t_zg": "unavailable", "stagione": "INVERNO", "x": "nan"}
    s = parse_snapshot(raw, numeric=["p_cp", "t_zg", "x"])
    assert s["p_cp"] == 512.0 and s["t_zg"] is None and s["stagione"] == "INVERNO"
    assert s["x"] is None


def test_build_template_last_reported():
    t = build_template({"a": "sensor.x"}, reported={"lr_y": "sensor.y"})
    assert "'lr_y': (expand('sensor.y') | map(attribute='last_reported') | map('as_timestamp') | first | default(none))" in t
    assert "states('sensor.x')" in t

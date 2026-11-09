import json
from datetime import datetime, timezone

import pytest

from ecm_engine import gw_import as g


def _chunk(lbl, rows, dev=None):
    body = {"DATI": [{"ERR": 0, "DATI": {"lbl": [{"name": n} for n in ["utc", "stato"] + lbl],
                                          "dati": rows}}]}
    c = {"s": 0, "e": 0, "body": json.dumps(body)}
    if dev:
        c["dev"] = dev
    return c


# ---------- parsing

@pytest.fixture
def no_tz(monkeypatch):
    monkeypatch.setattr(g, "gw_utc", lambda rows: ((int(r[0]), r) for r in rows))


def test_parse_chunks_selects_columns_aligns_minute_and_dedupes(no_tz):
    chunks = [
        _chunk(["A", "B"], [[120, 0, "1.0", "x"], [181, 0, "2.0", "y"]]),
        {"s": 0, "e": 0, "body": ""},                       # vuoto: saltato
        {"s": 0, "e": 0, "body": "<html>error</html>"},     # non JSON: saltato
        _chunk(["B", "A"], [[180, 0, "z", "9.0"], [240, 0, "w", "3.0"]]),  # sovrapposto, colonne in altro ordine
    ]
    out = g.parse_chunks(chunks, ["A"])
    assert out == {120: {"A": "1.0"}, 180: {"A": "2.0"}, 240: {"A": "3.0"}}


def _wall(y, mo, d, h, mi):
    """Ora locale scritta come se fosse UTC: così il gateway registra il campo utc."""
    import calendar
    return calendar.timegm((y, mo, d, h, mi, 0))


def test_gw_utc_summer_winter_offsets():
    rows = [[_wall(2026, 7, 10, 12, 0), 0], [_wall(2026, 7, 10, 12, 1), 0]]
    assert [u for u, _ in g.gw_utc(rows)] == [_wall(2026, 7, 10, 10, 0), _wall(2026, 7, 10, 10, 1)]
    rows = [[_wall(2026, 11, 2, 7, 0), 0]]
    assert [u for u, _ in g.gw_utc(rows)] == [_wall(2026, 11, 2, 6, 0)]


def test_gw_utc_follows_the_gateway_clock_switch():
    # il 25/10 il gateway è rimasto in ora legale fino alle 07:52 e poi è tornato alle 06:54
    # (il blocco parte prima del cambio, come gli export settimanali)
    raw = [_wall(2026, 10, 24, 23, 0), _wall(2026, 10, 25, 7, 51), _wall(2026, 10, 25, 7, 52),
           _wall(2026, 10, 25, 6, 54), _wall(2026, 10, 25, 6, 55)]
    out = [u for u, _ in g.gw_utc([[t, 0] for t in raw])]
    assert out == [_wall(2026, 10, 24, 21, 0), _wall(2026, 10, 25, 5, 51), _wall(2026, 10, 25, 5, 52),
                   _wall(2026, 10, 25, 5, 54), _wall(2026, 10, 25, 5, 55)]


def test_gw_utc_spring_forward_jump_only_when_dst_starts():
    raw = [_wall(2027, 3, 28, 1, 59), _wall(2027, 3, 28, 3, 0)]   # nessun buco reale: l'ora salta
    assert [u for u, _ in g.gw_utc([[t, 0] for t in raw])] == [_wall(2027, 3, 28, 0, 59), _wall(2027, 3, 28, 1, 0)]
    raw = [_wall(2026, 8, 1, 10, 0), _wall(2026, 8, 1, 12, 0)]     # buco vero d'estate
    assert [u for u, _ in g.gw_utc([[t, 0] for t in raw])] == [_wall(2026, 8, 1, 8, 0), _wall(2026, 8, 1, 10, 0)]


def test_parse_chunks_skips_rows_with_bad_stato(no_tz):
    out = g.parse_chunks([_chunk(["A"], [[60, 2, "5"], [120, 0, "6"]])], ["A"])
    assert out == {120: {"A": "6"}}


def test_num_handles_sentinels_and_garbage():
    assert g.num("21.50") == 21.5
    assert g.num("-3276.8") is None
    assert g.num("") is None and g.num(None) is None and g.num("abc") is None


# ---------- decodifica

def test_decode_cp_strings_match_ha_templates():
    raw = {"vent_sel": "3.000000", "Comp": "1", "Control_state": "7.0", "Hot_water_heater": "0",
           "mode_set": "1.000000", "mode_act": "1", "T10": "21.30", "T2": "30.10"}
    d = g.decode_cp(raw)
    assert d == {"cp_vent": "STEP 3", "cp_compressore": "ON", "cp_stato": "RISCALDAMENTO",
                 "cp_resistenza": "OFF", "cp_modo": "RISCALDAMENTO", "mode_act": 1,
                 "t10": 21.3, "t2": 30.1}


def test_decode_cp_unknown_values_are_none():
    d = g.decode_cp({"vent_sel": "9", "Comp": "", "Control_state": "x", "Hot_water_heater": "1",
                     "mode_set": None, "mode_act": None, "T10": "-3276.8", "T2": None})
    assert d["cp_vent"] is None and d["cp_compressore"] is None and d["cp_stato"] is None
    assert d["cp_resistenza"] == "ON" and d["cp_modo"] is None and d["t10"] is None


def test_decode_split():
    d = g.decode_split({"UnitONOFF": "1.000000", "UnitMode": "4.000000", "UnitFanSpeed": "2.000000"})
    assert d == {"tosh_on": "ACCESO", "tosh_modo": "RAFFRESCAMENTO", "tosh_vent": "MEDIA"}
    d = g.decode_split({"UnitONOFF": "0", "UnitMode": "2", "UnitFanSpeed": "0"})
    assert d == {"tosh_on": "SPENTO", "tosh_modo": "DEUMIDIFICATORE", "tosh_vent": "AUTOMATICA"}


@pytest.mark.parametrize("mode_set,mode_act,cp_stato,prev,exp", [
    ("RISCALDAMENTO", 1, "RAFFRESCAMENTO", None, "INVERNO"),   # selezione esplicita: vince
    ("RAFFRESCAMENTO", 2, "RISCALDAMENTO", "INVERNO", "ESTATE"),
    ("AUTO", 1, "STANDBY", "ESTATE", "INVERNO"),     # AUTO: modo attuale se decisivo
    ("AUTO", 2, None, None, "ESTATE"),
    ("AUTO", 3, "RISCALDAMENTO", "ESTATE", "INVERNO"),   # poi la direzione del controllo CP
    ("AUTO", 3, "RISCALDAMENTO + ACS", None, "INVERNO"),
    ("AUTO", 3, "RAFFRESCAMENTO", "INVERNO", "ESTATE"),
    ("AUTO", 3, "RAFFRESCAMENTO + ACS", None, "ESTATE"),
    ("AUTO", 3, "STANDBY", "ESTATE", "ESTATE"),      # altrimenti resta la precedente
    ("AUTO", 3, "ACS", None, None),
    ("OFF", 0, "OFF", "INVERNO", "INVERNO"),
    (None, None, None, None, None),
])
def test_stagione_of(mode_set, mode_act, cp_stato, prev, exp):
    assert g.stagione_of(mode_set, mode_act, cp_stato, prev) == exp


# ---------- serie

def test_step_lookup_forward_fill_with_max_age():
    lk = g.StepLookup([(600, 10.0), (1200, None), (1800, 30.0)], max_age=900)
    assert lk(599) is None
    assert lk(600) == 10.0 and lk(1199) == 10.0
    assert lk(1200) is None          # valore non valido non viene sostituito dal precedente
    assert lk(1800) == 30.0 and lk(2700) == 30.0 and lk(2701) is None


def test_hourly_interp_midpoints_and_gaps():
    # medie orarie su [start, start+3600): punto al centro dell'ora
    lk = g.HourlyInterp([(0, 20.0), (3600, 22.0), (4 * 3600 + 7200, 25.0)], max_gap=3 * 3600)
    assert lk(1800) == 20.0
    assert lk(1800 + 1800) == pytest.approx(21.0)
    assert lk(5400) == 22.0
    assert lk(1000) == 20.0              # entro mezz'ora dal primo punto: valore del bordo
    assert lk(0) == 20.0
    assert lk(-1) is None
    # buco > 3 h tra due punti: valore del bordo entro mezz'ora, poi None
    assert lk(5400 + 1800) == 22.0
    assert lk(5400 + 1801) is None
    assert lk(23400 - 1801) is None
    assert lk(23400 - 1800) == 25.0
    assert lk(4 * 3600 + 7200 + 1800 + 1800) == 25.0
    assert lk(4 * 3600 + 7200 + 1800 + 1801) is None


# ---------- campioni

def _cp(ts, **over):
    r = {"vent_sel": "2", "Comp": "0", "Control_state": "6", "Hot_water_heater": "0",
         "mode_set": "2", "mode_act": "2", "T10": "24.0", "T2": "20.0"}
    r.update(over)
    return ts, r


def _split(ts, on="0", mode="4", fan="2"):
    return ts, {"UnitONOFF": on, "UnitMode": mode, "UnitFanSpeed": fan}


def test_build_samples_merges_and_classifies():
    cp = dict([_cp(600), _cp(660, Comp="1"), _cp(720, Control_state="9")])
    split = dict([_split(600), _split(660, on="1")])
    io = {600: {"Ing Temp 1": "30.5"}, 660: {"Ing Temp 1": "31.0"}, 720: {"Ing Temp 1": "31.5"}}
    m_cp = [(0, 35.0)]
    m_tosh = [(0, 9.0), (650, 600.0)]
    zones = {"t_zg": g.HourlyInterp([(0, 24.0), (3600, 24.0)]), "t_zn": g.HourlyInterp([(0, 23.0), (3600, 23.0)])}
    out = g.build_samples(cp, split, io, m_cp, m_tosh, zones, end_ts=10_000)
    assert [s["ts"] for s in out] == [600, 660, 720]
    a, b, c = out
    assert a["code"] == 1 and a["valido"] == 1 and a["stagione"] == "ESTATE"
    assert a["t_ext"] == 30.5 and a["p_cp"] == 35.0 and a["p_tosh"] == 9.0 and a["t_zg"] == 24.0
    assert a["t10"] == 24.0 and a["t2"] == 20.0 and a["tosh_rps"] is None and a["test_id"] is None
    # Toshiba acceso in raffrescamento media (decina 5) + CP ON V2 (unità 4)
    assert b["code"] == 54 and b["tipo"] == "COOL" and b["p_tosh"] == 600.0 and b["cp_compressore"] == "ON"
    # stato ACS escluso; Toshiba forward-fill dal minuto prima
    assert c["valido"] == 0 and c["motivo"] == "cp_stato ACS"


def test_build_samples_end_ts_and_missing_data():
    cp = dict([_cp(600), _cp(660), _cp(1200)])
    split = dict([_split(600)])                      # a 1200 è troppo vecchio
    io = {600: {"Ing Temp 1": "30"}}
    zones = {"t_zg": g.HourlyInterp([(0, 24.0)]), "t_zn": g.HourlyInterp([(0, 23.0)])}
    out = g.build_samples(cp, split, io, [(0, 35.0)], [(0, 9.0)], zones, end_ts=1200)
    assert [s["ts"] for s in out] == [600, 660]      # end_ts escluso
    assert out[1]["valido"] == 1 and out[1]["t_ext"] == 30.0   # forward-fill di 60 s
    out = g.build_samples(cp, split, io, [(0, 35.0)], [(0, 9.0)], zones, end_ts=2000)
    assert out[2]["valido"] == 0 and out[2]["motivo"] == "toshiba non classificato"


def test_build_samples_missing_meter_is_invalid():
    cp = dict([_cp(600)])
    out = g.build_samples(cp, dict([_split(600)]), {600: {"Ing Temp 1": "30"}}, [], [(0, 9.0)],
                          {"t_zg": g.HourlyInterp([(0, 24.0)]), "t_zn": g.HourlyInterp([(0, 23.0)])},
                          end_ts=10_000)
    assert out[0]["valido"] == 0 and out[0]["motivo"] == "dato mancante p_cp"


def test_import_dir_only_before_first_sample(tmp_path, capsys, no_tz):
    from ecm_engine.store import Store
    cp_rows = [[t, 0, "2", "0", "6", "0", "2", "2", "24.0", "20.0"] for t in (600, 660, 720, 780)]
    files = {
        "cp": _chunk(g.CP_COLS, cp_rows), "split": _chunk(g.SPLIT_COLS, [[t, 0, "0", "4", "2"] for t in (600, 660, 720)]),
        "io": _chunk([g.IO_COL], [[t, 0, "30"] for t in (600, 660, 720)]),
        "m_cp": _chunk([g.METER_COL], [[0, 0, "35"]]), "m_tosh": _chunk([g.METER_COL], [[0, 0, "9"]]),
    }
    for k, names in g.FILES.items():
        for i, n in enumerate(names):
            (tmp_path / n).write_text(json.dumps([files[k]] if i == 0 else []))
    (tmp_path / g.ZONE_FILE).write_text(json.dumps({g.ZONE_IDS["t_zg"]: [[0, 24.0]], g.ZONE_IDS["t_zn"]: [[0, 23.0]]}))
    db = str(tmp_path / "e.db")
    st = Store(db)
    st.add_sample({"ts": 720, "code": 99, "valido": 1, "tipo": "HEAT"})
    assert g.import_dir(str(tmp_path), db) == 2
    rows = {r["ts"]: r for r in st.samples_since(0)}
    assert sorted(rows) == [600, 660, 720]
    assert rows[720]["code"] == 99 and rows[600]["code"] == 1 and rows[600]["valido"] == 1
    assert "inseriti 2" in capsys.readouterr().out


# ---------- ripiego T10 e sostituzione

def test_t10_fallback_only_before_first_zone_stat():
    cp = dict([_cp(600, T10="22.5"), _cp(7200, T10="22.5")])
    split = dict([_split(600), _split(7200)])
    io = {600: {"Ing Temp 1": "30"}, 7200: {"Ing Temp 1": "30"}}
    # statistiche di zona solo da 6000 s (centro 7800)
    zones = {"t_zg": g.HourlyInterp([(6000, 24.0)]), "t_zn": g.HourlyInterp([(6000, 23.0)])}
    out = g.build_samples(cp, split, io, [(0, 35.0)], [(0, 9.0)], zones, end_ts=10_000)
    a, b = out
    assert a["t_zg"] == a["t_zn"] == 22.5 and a["valido"] == 1
    assert b["t_zg"] == 24.0 and b["t_zn"] == 23.0          # zone vere, niente T10


def test_no_t10_fallback_after_zone_stats_end():
    cp = dict([_cp(20_000, T10="22.5")])
    zones = {"t_zg": g.HourlyInterp([(0, 24.0)]), "t_zn": g.HourlyInterp([(0, 23.0)])}
    out = g.build_samples(cp, dict([_split(20_000)]), {20_000: {"Ing Temp 1": "30"}}, [(19_900, 35.0)],
                          [(19_900, 9.0)], zones, end_ts=30_000)
    assert out[0]["t_zg"] is None and out[0]["motivo"] == "dato mancante t_zg"


def test_parse_ts():
    assert g.parse_ts("1700000000") == 1700000000
    assert g.parse_ts("2026-08-27T14:00") == int(datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc).timestamp())


def test_replace_invalid_only_touches_listed_motivi(tmp_path):
    from ecm_engine.store import Store
    st = Store(str(tmp_path / "e.db"))
    base = {"valido": 0, "tipo": None, "code": None}
    st.add_samples([
        dict(base, ts=600, motivo="dato mancante t_zg"), dict(base, ts=660, motivo="cp non classificato"),
        dict(base, ts=720, motivo="cp_stato ACS"), dict(base, ts=780, motivo="dato mancante t_zg"),
        {"ts": 840, "valido": 1, "code": 99, "tipo": "HEAT", "motivo": None}])
    new = lambda ts, v=1: {"ts": ts, "valido": v, "code": 7, "tipo": "NEUTRO", "motivo": None if v else "x",
                          "cp_compressore": "OFF"}
    done, written = g.replace_invalid(st, [new(600), new(660), new(720), new(780), new(840), new(900)], 780)
    rows = {r["ts"]: r for r in st.samples_since(0)}
    assert sorted(rows) == [600, 660, 720, 780, 840]      # 900 assente: non inserito
    assert rows[600]["valido"] == 1 and rows[660]["code"] == 7
    assert rows[720]["valido"] == 0 and rows[720]["motivo"] == "cp_stato ACS"   # altro motivo: intatto
    assert rows[780]["valido"] == 0                                              # ts >= before: intatto
    assert rows[840]["code"] == 99
    assert done == {("dato mancante t_zg", "valido"): 1, ("cp non classificato", "valido"): 1}
    assert len(written) == 2


def test_replace_invalid_conserva_bollitore_e_marcatori_acs(tmp_path):
    from ecm_engine.store import Store
    st = Store(str(tmp_path / "e.db"))
    st.add_samples([{"ts": 600, "valido": 0, "code": None, "tipo": None, "motivo": "cp non classificato",
                     "t11": 45.0, "t12": 30.0, "acs_heat_test": 1, "acs_source_ok": 0}])
    new = {"ts": 600, "valido": 1, "code": 7, "tipo": "NEUTRO", "motivo": None, "cp_compressore": "OFF"}
    g.replace_invalid(st, [new], 1000)
    r = st.samples_since(0)[0]
    assert r["code"] == 7 and (r["t11"], r["t12"], r["acs_heat_test"], r["acs_source_ok"]) == (45.0, 30.0, 1, 0)

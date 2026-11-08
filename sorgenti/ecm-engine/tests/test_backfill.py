import json

from ecm_engine import backfill
from ecm_engine.backfill import rebuild_samples
from ecm_engine.store import Store

BASE = {"stagione": "ESTATE", "free_cooling": "DISATTIVATO", "cp_compressore": "OFF",
        "cp_vent": "STEP 2", "cp_stato": "VENTILAZIONE", "cp_resistenza": "OFF",
        "tosh_on": "SPENTO", "tosh_modo": "RAFFRESCAMENTO", "tosh_vent": "MEDIA",
        "p_cp": "30.5", "p_tosh": "9", "t_zg": "24.1", "t_zn": "23.9", "t_ext": "28"}


def _changes(t0=1000.0, **over):
    ch = {k: [(t0, v)] for k, v in BASE.items()}
    ch.update(over)
    return ch


def test_rebuild_forward_fill_and_numeric():
    ch = _changes(t0=500.0, p_cp=[(500.0, "30.5"), (1150.5, "1200")])
    out = rebuild_samples(ch, 1020, 1260)
    assert [s["ts"] for s in out] == [1020, 1080, 1140, 1200]
    assert out[0]["p_cp"] == 30.5 and out[2]["p_cp"] == 30.5 and out[3]["p_cp"] == 1200.0
    assert out[0]["code"] == 1 and out[0]["valido"] == 1 and out[0]["stagione"] == "ESTATE"
    assert out[0]["test_id"] is None


def test_rebuild_minutes_aligned_to_step():
    out = rebuild_samples(_changes(t0=0.0), 1001, 1200)
    assert [s["ts"] for s in out] == [1020, 1080, 1140]


def test_rebuild_skips_until_required_seen():
    ch = _changes(t0=1000.0, t_ext=[(1130.0, "27.5")])
    out = rebuild_samples(ch, 1020, 1260)
    assert [s["ts"] for s in out] == [1140, 1200]


def test_rebuild_unavailable_is_none():
    ch = _changes(t0=1000.0, p_tosh=[(1000.0, "9"), (1100.0, "unavailable")],
                  tosh_on=[(1000.0, "SPENTO"), (1100.0, "unknown")])
    out = rebuild_samples(ch, 1020, 1200)
    assert out[0]["valido"] == 1
    assert out[2]["p_tosh"] is None and out[2]["valido"] == 0
    assert out[2]["motivo"] == "toshiba non classificato"


def test_rebuild_unsorted_input_and_stagione_switch():
    ch = _changes(t0=900.0, stagione=[(1100.0, "INVERNO"), (900.0, "ESTATE")],
                  tosh_on=[(900.0, "ACCESO")], tosh_modo=[(900.0, "RISCALDAMENTO")])
    out = rebuild_samples(ch, 1020, 1200)
    assert out[1]["stagione"] == "ESTATE" and out[2]["stagione"] == "INVERNO"
    assert out[2]["code"] == 81 and out[2]["tipo"] == "HEAT"


def test_import_fills_only_before_first_sample(tmp_path, capsys):
    db = str(tmp_path / "e.db")
    st = Store(db)
    st.add_sample({"ts": 1260, "code": 4, "tipo": "HEAT", "valido": 1, "p_cp": 999.0})
    f = tmp_path / "h.json"
    f.write_text(json.dumps({k: [[t, s] for t, s in v] for k, v in _changes(t0=900.0).items()}))
    n = backfill.import_file(str(f), db, now=1300)
    rows = Store(db).samples_since(0)
    assert n == 6 and [r["ts"] for r in rows] == [900, 960, 1020, 1080, 1140, 1200, 1260]
    assert rows[-1]["p_cp"] == 999.0
    out = capsys.readouterr().out
    assert "inseriti 6" in out and "E1" in out


def test_import_start_not_older_than_7_days(tmp_path):
    db = str(tmp_path / "e.db")
    now = 30 * 86400
    f = tmp_path / "h.json"
    f.write_text(json.dumps({k: [[0.0, v]] for k, v in BASE.items()}))
    n = backfill.import_file(str(f), db, now=now)
    rows = Store(db).samples_since(0)
    assert rows[0]["ts"] == now - 7 * 86400 and n == 7 * 1440


def test_add_samples_bulk(tmp_path):
    st = Store(str(tmp_path / "e.db"))
    st.add_samples([{"ts": 1, "cp_compressore": "ON"}, {"ts": 2, "cp_compressore": "OFF"}])
    assert [r["cp_compressore"] for r in st.samples_since(0)] == [1, 0]

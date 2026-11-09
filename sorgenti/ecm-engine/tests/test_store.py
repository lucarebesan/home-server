from ecm_engine.store import Store

def mk(tmp_path):
    return Store(str(tmp_path / "t.db"))

def test_sample_roundtrip(tmp_path):
    st = mk(tmp_path)
    st.add_sample({"ts": 100, "code": 5, "tipo": "HEAT", "valido": 1, "motivo": None,
                   "stagione": "INVERNO", "test_id": None, "cp_compressore": 1, "tosh_rps": 0.0,
                   "p_cp": 500.0, "p_tosh": 9.0, "t_zg": 21.0, "t_zn": 20.5, "t10": 21.0,
                   "t2": 30.0, "t_ext": 8.0, "soc": 60.0, "pv": 0.0, "load": 900.0, "imp": 0.0,
                   "discharge": 900.0, "charge": 0.0})
    rows = st.samples_since(0)
    assert len(rows) == 1 and rows[0]["code"] == 5 and rows[0]["p_cp"] == 500.0

def test_purge(tmp_path):
    st = mk(tmp_path)
    for ts in (10, 20, 30):
        st.add_sample({"ts": ts, "valido": 0})
    st.purge(25)
    assert [r["ts"] for r in st.samples_since(0)] == [30]

def test_tests_lifecycle(tmp_path):
    st = mk(tmp_path)
    tid = st.start_test(84, 20, "auto", 1000)
    assert st.open_test()["id"] == tid
    st.end_test(tid, 2200, "completata")
    assert st.open_test() is None
    assert st.last_test_end() == 2200
    assert len(st.tests_since(0, origine="auto")) == 1
    assert len(st.tests_since(0, origine="manuale")) == 0

def test_settings(tmp_path):
    st = mk(tmp_path)
    assert st.get_setting("auto", "0") == "0"
    st.set_setting("auto", "1")
    assert st.get_setting("auto", "0") == "1"

def test_cp_compressore_normalised(tmp_path):
    st = mk(tmp_path)
    for i, v in enumerate([True, "ON", "off", 0, None, "unavailable"]):
        st.add_sample({"ts": i, "cp_compressore": v})
    assert [r["cp_compressore"] for r in st.samples_since(0)] == [1, 1, 0, 0, None, None]

def test_iter_samples_since(tmp_path):
    st = mk(tmp_path)
    for ts in range(12000):
        st.db.execute("INSERT INTO samples (ts, valido) VALUES (?, 1)", (ts,))
    st.db.commit()
    it = st.iter_samples_since(100)
    assert next(it)["ts"] == 100
    assert sum(1 for _ in it) == 11899

def test_wal_and_timeout(tmp_path):
    st = mk(tmp_path)
    assert st.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert st.db.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

def test_last_tests_newest_first(tmp_path):
    st = mk(tmp_path)
    for i in range(5):
        st.start_test(i, 20, "auto", 1000 + i)
    assert [t["code"] for t in st.last_tests(3)] == [4, 3, 2]

def test_ventilation_and_room_columns_roundtrip(tmp_path):
    st = mk(tmp_path)
    st.add_sample({"ts": 1, "t1": 16.0, "t4": 19.2, "bypass_apre": "OFF", "bypass_chiude": "ON",
                   "serranda": "on", "t_sogg": 21.0, "bat_sogg": 80.0, "age_sogg": 30, "ok_sogg": 1,
                   "t_bagno": 20.8, "u_bagno": 61.0, "ok_bagno": 0})
    r = st.samples_since(0)[0]
    assert (r["t1"], r["t4"], r["bypass_apre"], r["bypass_chiude"], r["serranda"]) == (16.0, 19.2, 0, 1, 1)
    assert (r["t_sogg"], r["bat_sogg"], r["age_sogg"], r["ok_sogg"]) == (21.0, 80.0, 30, 1)
    assert (r["t_bagno"], r["u_bagno"], r["ok_bagno"]) == (20.8, 61.0, 0)

def test_old_db_gets_new_columns(tmp_path):
    import sqlite3
    p = str(tmp_path / "old.db")
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE samples (ts INTEGER PRIMARY KEY, valido INTEGER)")
    db.execute("INSERT INTO samples VALUES (5, 1)")
    db.commit(); db.close()
    st = Store(p)
    cols = {row[1] for row in st.db.execute("PRAGMA table_info(samples)")}
    assert {"t1", "t4", "serranda", "t_leo", "age_bagno", "u_bagno"} <= cols
    assert st.samples_since(0)[0]["t_leo"] is None

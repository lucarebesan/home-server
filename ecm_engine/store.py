"""Persistenza SQLite: campioni, prove, impostazioni."""
import sqlite3
import threading

SAMPLE_COLS = ["ts", "code", "tipo", "valido", "motivo", "stagione", "test_id", "cp_compressore",
               "tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext", "soc", "pv",
               "load", "imp", "discharge", "charge"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
  ts INTEGER PRIMARY KEY, code INTEGER, tipo TEXT, valido INTEGER, motivo TEXT, stagione TEXT,
  test_id INTEGER, cp_compressore INTEGER, tosh_rps REAL, p_cp REAL, p_tosh REAL, t_zg REAL,
  t_zn REAL, t10 REAL, t2 REAL, t_ext REAL, soc REAL, pv REAL, load REAL, imp REAL,
  discharge REAL, charge REAL);
CREATE TABLE IF NOT EXISTS tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, code INTEGER, durata_min INTEGER, origine TEXT,
  inizio INTEGER, fine INTEGER, esito TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def _norm_onoff(v) -> int | None:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return 1 if v else 0
    u = v.strip().upper() if isinstance(v, str) else ""
    return {"ON": 1, "OFF": 0}.get(u)


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.executescript(SCHEMA)
            self.db.commit()

    def add_sample(self, s: dict) -> None:
        s = dict(s)
        s["cp_compressore"] = _norm_onoff(s.get("cp_compressore"))
        vals = [s.get(c) for c in SAMPLE_COLS]
        with self._lock:
            self.db.execute(f"INSERT OR REPLACE INTO samples ({','.join(SAMPLE_COLS)}) "
                            f"VALUES ({','.join('?' * len(SAMPLE_COLS))})", vals)
            self.db.commit()

    def samples_since(self, ts: int) -> list[dict]:
        with self._lock:
            cur = self.db.execute("SELECT * FROM samples WHERE ts >= ? ORDER BY ts", (ts,))
            return [dict(r) for r in cur]

    def iter_samples_since(self, ts: int):
        """Genera i campioni a blocchi da 5000 (il lock è preso per ogni blocco)."""
        with self._lock:
            cur = self.db.execute("SELECT * FROM samples WHERE ts >= ? ORDER BY ts", (ts,))
        while True:
            with self._lock:
                rows = cur.fetchmany(5000)
            if not rows:
                return
            for r in rows:
                yield dict(r)

    def purge(self, older_than_ts: int) -> None:
        with self._lock:
            self.db.execute("DELETE FROM samples WHERE ts < ?", (older_than_ts,))
            self.db.commit()

    def start_test(self, code: int, durata_min: int, origine: str, ts: int) -> int:
        with self._lock:
            cur = self.db.execute("INSERT INTO tests (code, durata_min, origine, inizio) VALUES (?,?,?,?)",
                                  (code, durata_min, origine, ts))
            self.db.commit()
            return cur.lastrowid

    def end_test(self, test_id: int, ts: int, esito: str) -> None:
        with self._lock:
            self.db.execute("UPDATE tests SET fine=?, esito=? WHERE id=?", (ts, esito, test_id))
            self.db.commit()

    def open_test(self) -> dict | None:
        with self._lock:
            r = self.db.execute("SELECT * FROM tests WHERE fine IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        return dict(r) if r else None

    def last_test_end(self) -> int | None:
        with self._lock:
            r = self.db.execute("SELECT MAX(fine) FROM tests").fetchone()
        return r[0]

    def tests_since(self, ts: int, origine: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM tests WHERE inizio >= ?", [ts]
        if origine:
            q += " AND origine = ?"; a.append(origine)
        with self._lock:
            return [dict(r) for r in self.db.execute(q, a)]

    def get_setting(self, key: str, default: str) -> str:
        with self._lock:
            r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
            self.db.commit()

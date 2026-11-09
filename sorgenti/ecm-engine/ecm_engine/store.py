"""Persistenza SQLite: campioni, prove, impostazioni."""
import sqlite3
import threading

from .config import ROOMS

SAMPLE_COLS = ["ts", "code", "tipo", "valido", "motivo", "stagione", "test_id", "cp_compressore",
               "tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext", "soc", "pv",
               "load", "imp", "discharge", "charge", "t11", "t12", "acs_heat_test", "acs_source_ok"]

# aria esterna lungo la Compact, bypass/serranda e termometri ambiente (dal 09/11)
NEW_COLS = [("t1", "REAL"), ("t4", "REAL"), ("bypass_apre", "INTEGER"), ("bypass_chiude", "INTEGER"),
            ("serranda", "INTEGER"), ("u_bagno", "REAL"),
            *((f"{p}_{k}", typ) for k in ROOMS
              for p, typ in (("t", "REAL"), ("bat", "REAL"), ("age", "INTEGER"), ("ok", "INTEGER")))]
SAMPLE_COLS += [c for c, _ in NEW_COLS]
ONOFF_COLS = ("cp_compressore", "acs_heat_test", "bypass_apre", "bypass_chiude", "serranda")

# Colonne che solo il campionamento dal vivo conosce (il datalogger no): import e
# riparazioni che riscrivono una riga esistente devono conservarle.
LIVE_ONLY_COLS = ("t11", "t12", "acs_heat_test", "acs_source_ok", *(c for c, _ in NEW_COLS))

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
  ts INTEGER PRIMARY KEY, code INTEGER, tipo TEXT, valido INTEGER, motivo TEXT, stagione TEXT,
  test_id INTEGER, cp_compressore INTEGER, tosh_rps REAL, p_cp REAL, p_tosh REAL, t_zg REAL,
  t_zn REAL, t10 REAL, t2 REAL, t_ext REAL, soc REAL, pv REAL, load REAL, imp REAL,
  discharge REAL, charge REAL, t11 REAL, t12 REAL, acs_heat_test INTEGER);
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
            existing = {row[1] for row in self.db.execute("PRAGMA table_info(samples)")}
            for column, column_type in (("t11", "REAL"), ("t12", "REAL"),
                                        ("acs_heat_test", "INTEGER"), ("acs_source_ok", "INTEGER"),
                                        *NEW_COLS):
                if column not in existing:
                    self.db.execute(f"ALTER TABLE samples ADD COLUMN {column} {column_type}")
            self.db.commit()

    def add_sample(self, s: dict) -> None:
        self.add_samples([s])

    def add_samples(self, samples: list[dict]) -> None:
        """Inserimento in un'unica transazione (il backfill ne scrive migliaia)."""
        rows = []
        for s in samples:
            s = dict(s)
            for c in ONOFF_COLS:
                s[c] = _norm_onoff(s.get(c))
            rows.append([s.get(c) for c in SAMPLE_COLS])
        with self._lock:
            self.db.executemany(f"INSERT OR REPLACE INTO samples ({','.join(SAMPLE_COLS)}) "
                                f"VALUES ({','.join('?' * len(SAMPLE_COLS))})", rows)
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

    def last_tests(self, n: int) -> list[dict]:
        with self._lock:
            cur = self.db.execute("SELECT * FROM tests ORDER BY inizio DESC, id DESC LIMIT ?", (n,))
            return [dict(r) for r in cur]

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

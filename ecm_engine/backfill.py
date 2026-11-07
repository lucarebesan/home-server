"""Ricostruzione una tantum dei campioni al minuto dallo storico del recorder di HA.

Uso (dentro il container ecm-engine):
    python -m ecm_engine.backfill import /tmp/ecm_history.json
Il JSON è prodotto da scripts/export_history.py: {chiave: [[ts, stato], ...]}.
Riempie solo il periodo PRIMA del primo campione del motore, al massimo 7 giorni.
"""
import json
import sys
import time
from collections import Counter

from . import config
from .engine import REQUIRED, build_sample
from .ha_api import parse_snapshot
from .store import Store

IGNOTI = ("unavailable", "unknown")
MAX_DAYS = 7


def rebuild_samples(changes: dict, start_ts, end_ts, step: int = 60) -> list[dict]:
    """Per ogni minuto in [start, end) l'ultimo stato noto di ogni chiave -> build_sample.
    I minuti in cui una chiave REQUIRED non è mai stata vista vengono saltati."""
    keys = list(config.ENTITIES)
    series = {k: sorted(changes.get(k) or [], key=lambda x: x[0]) for k in keys}
    idx = {k: 0 for k in keys}
    cur: dict = {}
    out = []
    ts = -(-int(start_ts) // step) * step
    while ts < end_ts:
        for k in keys:
            ser, i = series[k], idx[k]
            while i < len(ser) and ser[i][0] <= ts:
                v = ser[i][1]
                cur[k] = None if v in IGNOTI else v
                i += 1
            idx[k] = i
        if all(k in cur for k in REQUIRED):
            raw = {k: cur.get(k) for k in keys}
            out.append(build_sample(parse_snapshot(raw, config.NUMERIC_KEYS), ts, None))
        ts += step
    return out


def import_file(path: str, db_path: str, now: float | None = None) -> int:
    now = time.time() if now is None else now
    with open(path) as f:
        changes = {k: [(float(t), s) for t, s in v] for k, v in json.load(f).items()}
    all_ts = [t for v in changes.values() for t, _ in v]
    if not all_ts:
        print("nessun dato nel file")
        return 0
    store = Store(db_path)
    with store._lock:
        first = store.db.execute("SELECT MIN(ts) FROM samples").fetchone()[0]
    start = max(min(all_ts), now - MAX_DAYS * 86400)
    end = first if first is not None else now
    samples = rebuild_samples(changes, start, end)
    store.add_samples(samples)
    valid = [s for s in samples if s["valido"]]
    print(f"periodo {time.strftime('%d/%m %H:%M', time.localtime(start))} -> "
          f"{time.strftime('%d/%m %H:%M', time.localtime(end))}")
    print(f"inseriti {len(samples)}, validi {len(valid)}")
    print("codici (top 15): " + ", ".join(f"E{c}={n}" for c, n in
                                          Counter(s["code"] for s in valid).most_common(15)))
    motivi = Counter(s["motivo"] for s in samples if not s["valido"])
    if motivi:
        print("non validi: " + ", ".join(f"{m}={n}" for m, n in motivi.most_common(10)))
    return len(samples)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "import":
        print("uso: python -m ecm_engine.backfill import <file.json>")
        return 2
    import_file(argv[1], config.DB_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

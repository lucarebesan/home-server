"""Esporta lo storico di alcune entità dal recorder di HA (sola lettura).

Gira DENTRO il container homeassistant, solo stdlib:
  ENTITIES='{"k": "sensor.x"}' DAYS=7 docker exec -i -e ENTITIES -e DAYS homeassistant \
      python3 - < scripts/export_history.py > /tmp/ecm_history.json
Output su stdout: {chiave: [[ts, stato], ...]} con in testa l'ultimo stato prima dell'inizio.
Statistiche su stderr. Nessun COUNT(*) né scansioni complete: solo query per metadata_id.
"""
import json
import os
import sqlite3
import sys
import time

DB = os.environ.get("HA_DB", "/config/home-assistant_v2.db")
entities = json.loads(os.environ["ENTITIES"])
start = time.time() - float(os.environ.get("DAYS", "7")) * 86400
t_begin = time.time()

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)
out = {}
for i, (key, eid) in enumerate(entities.items()):
    if i:
        time.sleep(0.5)
    t0 = time.time()
    r = db.execute("SELECT metadata_id FROM states_meta WHERE entity_id=?", (eid,)).fetchone()
    if r is None:
        print(f"{key:15s} {eid}: assente nel recorder", file=sys.stderr)
        out[key] = []
        continue
    mid = r[0]
    prev = db.execute("SELECT state, last_updated_ts FROM states WHERE metadata_id=? "
                      "AND last_updated_ts<? ORDER BY last_updated_ts DESC LIMIT 1",
                      (mid, start)).fetchone()
    rows = db.execute("SELECT state, last_updated_ts FROM states WHERE metadata_id=? "
                      "AND last_updated_ts>=? ORDER BY last_updated_ts", (mid, start)).fetchall()
    series = ([[prev[1], prev[0]]] if prev and prev[0] is not None else [])
    series += [[ts, st] for st, ts in rows if st is not None]
    out[key] = series
    print(f"{key:15s} {eid}: {len(rows)} righe (+{1 if prev else 0} precedente) "
          f"in {time.time() - t0:.1f}s", file=sys.stderr)
db.close()
json.dump(out, sys.stdout)
print(f"totale {time.time() - t_begin:.1f}s", file=sys.stderr)

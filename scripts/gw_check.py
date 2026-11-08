"""Riepilogo di un file di export datalogger del gateway (blocchi settimanali)."""
import datetime as dt
import json
import sys

for path in sys.argv[1:]:
    o = json.load(open(path))
    tot = 0
    for c in o:
        if "err" in c:
            print(path, "ERR", c["err"])
            continue
        try:
            d = json.loads(c["body"])["DATI"][0]
        except (ValueError, KeyError, IndexError):
            print(path, dt.datetime.fromtimestamp(c["s"]).date(), "RISPOSTA NON VALIDA", repr(c["body"][:80]))
            continue
        dd = d.get("DATI") or {}
        rows = dd.get("dati", []) if isinstance(dd, dict) else []
        tot += len(rows)
        first = dt.datetime.fromtimestamp(rows[0][0]).isoformat()[:16] if rows else ""
        print(path, dt.datetime.fromtimestamp(c["s"]).date(), "ERR", d["ERR"], "righe", len(rows), first)
    print(path, "TOTALE righe", tot)

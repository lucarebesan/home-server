"""Analisi degli export del datalogger del gateway (data_gw/) prima dell'import.

Uso: .venv/bin/python scripts/gw_inspect.py data_gw
Per ogni dispositivo: colonne, righe, periodo, valori distinti delle colonne a enumerazione,
statistiche di temperature e potenze. Le righe si deduplicano per minuto (vince la prima).
"""
import datetime as dt
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ecm_engine.gw_import import FILES, num, parse_chunks  # noqa: E402

ENUMS = {"mode_act", "mode_set", "Control_state", "vent_sel", "Comp", "Hot_water_heater", "onOff_state",
         "Alarm_status", "Bypass_open", "Bypass_close", "UnitONOFF", "UnitMode", "UnitFanSpeed",
         "UnitAlarmStatus", "ErrorCode", "Conf Ing 1", "Usc Dig 1", "Input_user_function",
         "Input_user_function2"}
NAMES = {"cp": "Compact P 2001969", "split": "Split Toshiba 2002144", "io": "Modulo I/O 2002022",
         "m_cp": "Contatore Compact 2002794", "m_tosh": "Contatore Split 2002795"}


def columns(chunks):
    for c in chunks:
        try:
            return [x["name"] for x in json.loads(c["body"])["DATI"][0]["DATI"]["lbl"]][2:]
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return []


def fmt(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def main(d):
    for key, files in FILES.items():
        chunks = []
        for n in files:
            chunks.extend(json.load(open(os.path.join(d, n))))
        cols = columns(chunks)
        rows = parse_chunks(chunks, cols)
        ts = sorted(rows)
        print(f"\n=== {NAMES[key]}: {len(ts)} righe, {fmt(ts[0])} -> {fmt(ts[-1])}")
        step = Counter(b - a for a, b in zip(ts, ts[1:]))
        holes = [(a, b) for a, b in zip(ts, ts[1:]) if b - a > 3600]
        print(f"  passi più frequenti {step.most_common(4)}; buchi > 1 h: {len(holes)}")
        for a, b in holes[:10]:
            print(f"    buco {fmt(a)} -> {fmt(b)} ({(b - a) / 3600:.1f} h)")
        print(f"  colonne: {cols}")
        for c in cols:
            vals = [rows[t].get(c) for t in ts]
            if c in ENUMS:
                cnt = Counter(num(v) for v in vals)
                print(f"  {c}: " + ", ".join(f"{k}={n}" for k, n in sorted(cnt.items(), key=lambda x: (x[0] is None, x[0] or 0))))
            else:
                xs = [x for x in (num(v) for v in vals) if x is not None]
                if not xs:
                    print(f"  {c}: nessun valore numerico")
                    continue
                q = statistics.quantiles(xs, n=20) if len(xs) > 20 else [min(xs)] * 19
                print(f"  {c}: n={len(xs)} nulli={len(vals) - len(xs)} min={min(xs):.1f} p5={q[0]:.1f} "
                      f"media={statistics.fmean(xs):.1f} p95={q[-1]:.1f} max={max(xs):.1f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data_gw")

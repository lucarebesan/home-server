"""Ripara i campioni scartati per stato macchine illeggibile usando il datalogger del gateway.

Uso (dentro il container ecm-engine, o in locale con DB_PATH):
    python -m ecm_engine.gw_repair <file.json>... [--from AAAA-MM-GG[THH:MM]] [--to ...] [--apply]

I file sono export del datalogger (lista di {"dev", "s", "e", "body"}) di Compact P (2001969)
e Split Toshiba (2002144). Per ogni campione nel periodo, non valido per uno dei motivi in
REPAIR_MOTIVI oppure valido ma con la resistenza ACS accesa secondo il gateway, ricostruisce lo
stato delle macchine dal datalogger e tiene le misure già salvate (consumi, temperature,
batteria). Il campione viene riclassificato con le regole correnti (build_sample).
Senza --apply mostra solo il riepilogo.
"""
import json
import sys
from collections import Counter

from . import config
from .engine import build_sample
from .gw_import import CP_COLS, DEV_MAX_AGE_S, SPLIT_COLS, StepLookup, decode_cp, decode_split, parse_chunks, parse_ts
from .store import SAMPLE_COLS, Store, _norm_onoff

DEV_CP, DEV_SPLIT = 2001969, 2002144
REPAIR_MOTIVI = ("cp non classificato", "toshiba non classificato", "resistenza ACS")
MEASURE_COLS = ["tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext", "soc", "pv",
                "load", "imp", "discharge", "charge"]


def _dev(chunk: dict) -> int | None:
    """Id del dispositivo: campo dev, altrimenti l'id dentro la risposta del datalogger."""
    if chunk.get("dev") is not None:
        return int(chunk["dev"])
    try:
        return int(json.loads(chunk["body"])["DATI"][0]["DATI"]["id"])
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def load_gw(paths: list[str]):
    chunks = []
    for p in paths:
        with open(p) as f:
            d = json.load(f)
        chunks.extend(json.loads(d) if isinstance(d, str) else d)
    cp = parse_chunks([c for c in chunks if _dev(c) == DEV_CP], CP_COLS)
    split = parse_chunks([c for c in chunks if _dev(c) == DEV_SPLIT], SPLIT_COLS)
    return cp, split


def rebuild(row: dict, cp_state: dict | None, split_state: dict | None, open_test: dict | None) -> dict | None:
    """Campione ricostruito: stati dal gateway, misure e stagione dal campione salvato."""
    if cp_state is None or split_state is None:
        return None
    c = {k: v for k, v in cp_state.items() if k not in ("mode_act", "cp_modo", "t10", "t2")}
    snap = {k: row.get(k) for k in MEASURE_COLS}
    snap.update(c, **split_state, stagione=row.get("stagione"), free_cooling=None)
    return build_sample(snap, row["ts"], open_test)


def is_target(row: dict, cp_state: dict | None) -> bool:
    if not row["valido"]:
        return row["motivo"] in REPAIR_MOTIVI
    return cp_state is not None and cp_state.get("cp_resistenza") == "ON" and row["motivo"] is None


def repair(store: Store, cp: dict, split: dict, t_from: int, t_to: int, apply: bool):
    cpl = StepLookup([(t, decode_cp(r)) for t, r in cp.items()], DEV_MAX_AGE_S)
    spl = StepLookup([(t, decode_split(r)) for t, r in split.items()], DEV_MAX_AGE_S)
    with store._lock:
        tests = {r["id"]: dict(r) for r in store.db.execute("SELECT * FROM tests")}
        rows = [dict(r) for r in store.db.execute(
            "SELECT * FROM samples WHERE ts >= ? AND ts < ? ORDER BY ts", (t_from, t_to))]
    esiti: Counter = Counter()
    codici: Counter = Counter()
    out = []
    for row in rows:
        cs = cpl(row["ts"])
        if not is_target(row, cs):
            continue
        t = tests.get(row["test_id"]) if row.get("test_id") is not None else None
        new = rebuild(row, cs, spl(row["ts"]), {"id": t["id"], "code": t["code"]} if t else None)
        prima = "valido" if row["valido"] else row["motivo"]
        if new is None:
            esiti[(prima, "gateway senza dati")] += 1
            continue
        dopo = ("valido" + (" (resistenza ACS)" if new["motivo"] else "")) if new["valido"] else new["motivo"]
        esiti[(prima, dopo)] += 1
        if new["valido"]:
            codici[new["code"]] += 1
        out.append(new)
    if apply and out:
        with store._lock:
            store.db.executemany(
                f"INSERT OR REPLACE INTO samples ({','.join(SAMPLE_COLS)}) VALUES ({','.join('?' * len(SAMPLE_COLS))})",
                [[dict(s, cp_compressore=_norm_onoff(s.get("cp_compressore"))).get(c) for c in SAMPLE_COLS]
                 for s in out])
            store.db.commit()
    return esiti, codici, len(out)


def main(argv: list[str]) -> int:
    args = list(argv)
    opts = {"--from": "0", "--to": str(2 ** 40)}
    for k in ("--from", "--to"):
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    apply = "--apply" in args
    args = [a for a in args if a != "--apply"]
    if not args:
        print(__doc__)
        return 2
    cp, split = load_gw(args)
    print(f"gateway: compact {len(cp)} minuti, split {len(split)} minuti")
    esiti, codici, n = repair(Store(config.DB_PATH), cp, split, parse_ts(opts["--from"]), parse_ts(opts["--to"]), apply)
    for (a, b), k in sorted(esiti.items(), key=lambda x: -x[1]):
        print(f"  {a} -> {b}: {k}")
    print("codici validi: " + ", ".join(f"E{c}={k}" for c, k in codici.most_common(25)))
    print(("scritti " if apply else "da scrivere (prova, senza --apply) ") + str(n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

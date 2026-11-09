"""Ripara i campioni scartati per stato macchine illeggibile usando il datalogger del gateway.

Uso (dentro il container ecm-engine, o in locale con DB_PATH):
    python -m ecm_engine.gw_repair <file.json>... [--from AAAA-MM-GG[THH:MM]] [--to ...] [--apply]

I file sono export del datalogger (lista di {"dev", "s", "e", "body"}) di Compact P (2001969)
e Split Toshiba (2002144). Per ogni campione nel periodo, non valido per uno dei motivi in
REPAIR_MOTIVI oppure valido ma con la resistenza ACS accesa secondo il gateway, ricostruisce lo
stato delle macchine dal datalogger e tiene le misure già salvate (consumi, temperature,
batteria). Il campione viene riclassificato con le regole correnti (build_sample).
Con --energia-cp (servono anche i file del Misuratore Compact, 2002794) sostituisce invece il
consumo Compact dei campioni ricostruiti dal datalogger (p_cp uguale alla potenza istantanea
registrata ogni 10 minuti) con la media esatta ricavata dal contatore di energia importata.
Senza --apply mostra solo il riepilogo.
"""
import json
import sys
from collections import Counter

from . import config
from .engine import build_sample
from .gw_import import CP_COLS, DEV_MAX_AGE_S, METER_COL, METER_MAX_AGE_S, SPLIT_COLS, num, StepLookup, decode_cp, decode_split, parse_chunks, parse_ts
from .store import LIVE_ONLY_COLS, SAMPLE_COLS, Store, _norm_onoff

DEV_CP, DEV_SPLIT, DEV_M_CP = 2001969, 2002144, 2002794
ENERGY_COL = "Totale energia importata"
ENERGY_MAX_GAP_S = 1800   # oltre, nessuna media (record mancanti per più di mezz'ora)
REPAIR_MOTIVI = ("cp non classificato", "toshiba non classificato", "resistenza ACS")
MEASURE_COLS = ["tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext", "soc", "pv",
                "load", "imp", "discharge", "charge", *LIVE_ONLY_COLS]


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
    meter = parse_chunks([c for c in chunks if _dev(c) == DEV_M_CP], [METER_COL, ENERGY_COL])
    return cp, split, meter


def energy_power(meter: dict) -> list[tuple[int, int, float]]:
    """Intervalli (inizio, fine, W medi) tra due letture consecutive del contatore di energia,
    se distano al più ENERGY_MAX_GAP_S e il contatore non torna indietro."""
    pts = [(t, num(r.get(ENERGY_COL))) for t, r in sorted(meter.items())]
    pts = [(t, e) for t, e in pts if e is not None]
    out = []
    for (t0, e0), (t1, e1) in zip(pts, pts[1:]):
        if 0 < t1 - t0 <= ENERGY_MAX_GAP_S and e1 >= e0:
            out.append((t0, t1, round((e1 - e0) * 3_600_000 / (t1 - t0), 1)))
    return out


def apply_cp_energy(store: Store, cp: dict, split: dict, meter: dict, t_from: int, t_to: int, apply: bool):
    """p_cp dei campioni costruiti dal datalogger -> media dal contatore di energia."""
    import bisect
    iv = energy_power(meter)
    starts = [a for a, _, _ in iv]
    inst = StepLookup([(t, num(r.get(METER_COL))) for t, r in meter.items()], METER_MAX_AGE_S)
    cpl = StepLookup([(t, decode_cp(r)) for t, r in cp.items()], DEV_MAX_AGE_S)
    spl = StepLookup([(t, decode_split(r)) for t, r in split.items()], DEV_MAX_AGE_S)
    with store._lock:
        tests = {r["id"]: dict(r) for r in store.db.execute("SELECT * FROM tests")}
        rows = [dict(r) for r in store.db.execute(
            "SELECT * FROM samples WHERE ts >= ? AND ts < ? ORDER BY ts", (t_from, t_to))]
    esiti: Counter = Counter()
    out = []
    delta = []
    for row in rows:
        i = bisect.bisect_right(starts, row["ts"]) - 1
        if i < 0 or row["ts"] >= iv[i][1]:
            continue
        p_new = iv[i][2]
        if row["p_cp"] is None:
            if row["valido"] or row["motivo"] != "dato mancante p_cp":
                continue
            t = tests.get(row["test_id"]) if row.get("test_id") is not None else None
            new = rebuild(dict(row, p_cp=p_new), cpl(row["ts"]), spl(row["ts"]),
                          {"id": t["id"], "code": t["code"]} if t else None)
            if new is None:
                esiti[("dato mancante p_cp", "gateway senza dati")] += 1
                continue
            esiti[("dato mancante p_cp", "valido" if new["valido"] else new["motivo"])] += 1
            out.append(new)
            continue
        v = inst(row["ts"])
        if v is None or abs(row["p_cp"] - v) > 0.05:
            esiti[("p_cp non dal datalogger", "invariato")] += 1
            continue
        delta.append(p_new - row["p_cp"])
        esiti[("p_cp istantaneo", "media da energia")] += 1
        out.append(dict(row, p_cp=p_new))
    if apply and out:
        with store._lock:
            store.db.executemany(
                f"INSERT OR REPLACE INTO samples ({','.join(SAMPLE_COLS)}) VALUES ({','.join('?' * len(SAMPLE_COLS))})",
                [[dict(s, cp_compressore=_norm_onoff(s.get("cp_compressore"))).get(c) for c in SAMPLE_COLS]
                 for s in out])
            store.db.commit()
    return esiti, delta, len(out)


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
    energia = "--energia-cp" in args
    args = [a for a in args if a not in ("--apply", "--energia-cp")]
    if not args:
        print(__doc__)
        return 2
    cp, split, meter = load_gw(args)
    print(f"gateway: compact {len(cp)} minuti, split {len(split)} minuti, contatore compact {len(meter)} letture")
    if energia:
        esiti, delta, n = apply_cp_energy(Store(config.DB_PATH), cp, split, meter,
                                          parse_ts(opts["--from"]), parse_ts(opts["--to"]), apply)
        for (a, b), k in sorted(esiti.items(), key=lambda x: -x[1]):
            print(f"  {a} -> {b}: {k}")
        if delta:
            ad = sorted(abs(x) for x in delta)
            print(f"differenza media {sum(delta) / len(delta):+.1f} W, |differenza| mediana {ad[len(ad) // 2]:.0f} W, "
                  f"p90 {ad[9 * len(ad) // 10]:.0f} W")
        print(("scritti " if apply else "da scrivere (prova, senza --apply) ") + str(n))
        return 0
    esiti, codici, n = repair(Store(config.DB_PATH), cp, split, parse_ts(opts["--from"]), parse_ts(opts["--to"]), apply)
    for (a, b), k in sorted(esiti.items(), key=lambda x: -x[1]):
        print(f"  {a} -> {b}: {k}")
    print("codici validi: " + ", ".join(f"E{c}={k}" for c, k in codici.most_common(25)))
    print(("scritti " if apply else "da scrivere (prova, senza --apply) ") + str(n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Import una tantum dello storico del datalogger del gateway nei campioni del motore.

Uso (dentro il container ecm-engine):
    python -m ecm_engine.gw_import /tmp/gw
La cartella contiene gli export del datalogger (vedi FILES) e ha_zone_stats.json con le
medie orarie delle temperature di zona prese dalle statistiche a lungo termine di HA.
Inserisce solo minuti PRIMA del primo campione già presente: non sovrascrive nulla.
Con --replace-before <ts> (epoch, o data locale AAAA-MM-GG[THH:MM]) invece SOSTITUISCE i campioni con
ts < <ts> oggi non validi per uno dei motivi in REPLACE_MOTIVI, lasciando intatto tutto il resto.
Mappatura e regole: docs/gateway/import_mapping.md.
"""
import bisect
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config
from .engine import build_sample
from .store import SAMPLE_COLS, Store, _norm_onoff

FILES = {
    "cp": ["cp_135_90.json", "cp_90_45.json", "cp_45_0.json", "cp_topup.json"],
    "split": ["dev_2002144.json", "retry_split_1009.json"],
    "io": ["dev_2002022.json"],
    "m_cp": ["dev_2002794.json"],
    "m_tosh": ["dev_2002795.json"],
}
ZONE_FILE = "ha_zone_stats.json"
ZONE_IDS = {"t_zg": "sensor.ecm_zona_giorno_temperatura_media",
            "t_zn": "sensor.ecm_zona_notte_temperatura_media"}

CP_COLS = ["vent_sel", "Comp", "Control_state", "Hot_water_heater", "mode_set", "mode_act", "T10", "T2"]
SPLIT_COLS = ["UnitONOFF", "UnitMode", "UnitFanSpeed"]
IO_COL = "Ing Temp 1"            # "Temperatura aria esterna prima EGWK" = sensor.egwk_temp_aria_esterna_prima_egwk
METER_COL = "Potenza Attiva"

DEV_MAX_AGE_S = 180              # dispositivi a 60 s: copre un minuto mancante
METER_MAX_AGE_S = 900            # contatori a 600 s: al massimo 15 minuti
SENTINEL = -3276.8               # valore "non disponibile" del gateway (int16 -32768 * 0.1)

# stesse stringhe dei value_template HA (docs/gateway/ha_side/nilan_sensori.yaml)
CONTROL_STATE = {0: "OFF", 1: "SHIFT", 2: "STOP", 3: "START", 4: "STANDBY", 5: "STOP VENTILAZIONE",
                 6: "VENTILAZIONE", 7: "RISCALDAMENTO", 8: "RAFFRESCAMENTO", 9: "ACS",
                 10: "ANTILEGIONELLA", 11: "RAFFRESCAMENTO + ACS", 12: "RISCALDAMENTO CENTRALE",
                 13: "SBRINAMENTO", 14: "PROTEZIONE ANTIGELO", 15: "SERVICE", 16: "ALLARME",
                 17: "RISCALDAMENTO + ACS"}
CP_MODO = {0: "OFF", 1: "RISCALDAMENTO", 2: "RAFFRESCAMENTO", 3: "AUTO", 4: "SERVICE"}
VENT_SEL = {0: "OFF", 1: "STEP 1", 2: "STEP 2", 3: "STEP 3", 4: "STEP 4"}
ONOFF = {0: "OFF", 1: "ON"}
TOSH_ON = {0: "SPENTO", 1: "ACCESO"}
TOSH_MODO = {0: "AUTOMATICO", 1: "RISCALDAMENTO", 2: "DEUMIDIFICATORE", 3: "VENTILAZIONE", 4: "RAFFRESCAMENTO"}
TOSH_VENT = {0: "AUTOMATICA", 1: "BASSA", 2: "MEDIA", 3: "ALTA"}


GW_TZ = ZoneInfo("Europe/Rome")

# motivi di scarto recuperabili con --replace-before (ripiego T10 su zone, V1 osservabile)
REPLACE_MOTIVI = ("dato mancante t_zg", "cp non classificato")


# ---------- parsing

def _tz_offset(raw: int) -> int:
    wall = datetime.fromtimestamp(raw, timezone.utc).replace(tzinfo=GW_TZ)
    return int(wall.utcoffset().total_seconds())


def gw_utc(rows):
    """Il campo utc del datalogger è l'ora locale del gateway scritta come epoch.
    Righe in ordine -> (epoch vero, riga). L'offset segue l'orologio del gateway: cambia
    quando l'ora torna indietro (fine ora legale, il gateway lo fa in ritardo) o salta
    avanti di almeno un'ora mentre Europe/Rome è passato all'ora legale."""
    off = prev = None
    for r in rows:
        raw = int(r[0])
        if off is None:
            off = _tz_offset(raw)
        elif raw < prev - 1800:
            off -= 3600
        elif raw - prev >= 3600 and _tz_offset(raw) > off:
            off = _tz_offset(raw)
        prev = raw
        yield raw - off, r


def parse_chunks(chunks, cols: list[str]) -> dict[int, dict]:
    """Blocchi del datalogger -> {minuto UTC: {colonna: valore grezzo}}.
    Salta corpi vuoti o non validi e righe con stato != 0; a parità di minuto vince la prima."""
    out: dict[int, dict] = {}
    for c in chunks:
        body = c.get("body") if isinstance(c, dict) else None
        if not body:
            continue
        try:
            d = json.loads(body)["DATI"][0]["DATI"]
            names = [x["name"] for x in d["lbl"]]
            rows = d["dati"]
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        idx = [(k, names.index(k)) for k in cols if k in names]
        for utc, r in gw_utc(rows):
            if len(r) < 2 or r[1] != 0:
                continue
            ts = utc // 60 * 60
            if ts in out:
                continue
            out[ts] = {k: r[i] if i < len(r) else None for k, i in idx}
    return out


def num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or abs(x - SENTINEL) < 1e-6:
        return None
    return x


def _enum(v, table: dict):
    x = num(v)
    return table.get(int(x)) if x is not None and x == int(x) else None


# ---------- decodifica

def decode_cp(raw: dict) -> dict:
    ma = num(raw.get("mode_act"))
    return {"cp_vent": _enum(raw.get("vent_sel"), VENT_SEL),
            "cp_compressore": _enum(raw.get("Comp"), ONOFF),
            "cp_stato": _enum(raw.get("Control_state"), CONTROL_STATE),
            "cp_resistenza": _enum(raw.get("Hot_water_heater"), ONOFF),
            "cp_modo": _enum(raw.get("mode_set"), CP_MODO),
            "mode_act": int(ma) if ma is not None else None,
            "t10": num(raw.get("T10")), "t2": num(raw.get("T2"))}


def decode_split(raw: dict) -> dict:
    return {"tosh_on": _enum(raw.get("UnitONOFF"), TOSH_ON),
            "tosh_modo": _enum(raw.get("UnitMode"), TOSH_MODO),
            "tosh_vent": _enum(raw.get("UnitFanSpeed"), TOSH_VENT)}


def stagione_of(mode_set: str | None, mode_act: int | None, cp_stato: str | None,
               prev: str | None) -> str | None:
    """Modo selezionato sul CP: RISCALDAMENTO -> INVERNO, RAFFRESCAMENTO -> ESTATE.
    In AUTO decide il modo attuale se è heat/cool (1/2) e altrimenti la direzione del
    controllo CP (RISCALDAMENTO[+ACS] / RAFFRESCAMENTO[+ACS]); in tutti gli altri casi resta
    la stagione precedente."""
    if mode_set == "RISCALDAMENTO":
        return "INVERNO"
    if mode_set == "RAFFRESCAMENTO":
        return "ESTATE"
    if mode_set == "AUTO":
        if mode_act == 1:
            return "INVERNO"
        if mode_act == 2:
            return "ESTATE"
        if cp_stato in ("RISCALDAMENTO", "RISCALDAMENTO + ACS"):
            return "INVERNO"
        if cp_stato in ("RAFFRESCAMENTO", "RAFFRESCAMENTO + ACS"):
            return "ESTATE"
    return prev


# ---------- serie

class StepLookup:
    """Ultimo valore noto al più max_age secondi prima (None se più vecchio o assente)."""

    def __init__(self, points, max_age: int):
        pts = sorted(points, key=lambda p: p[0])
        self.ts = [p[0] for p in pts]
        self.vals = [p[1] for p in pts]
        self.max_age = max_age

    def __call__(self, ts):
        i = bisect.bisect_right(self.ts, ts) - 1
        if i < 0 or ts - self.ts[i] > self.max_age:
            return None
        return self.vals[i]


class HourlyInterp:
    """Medie orarie (start_ts, mean) -> valore al secondo, interpolato tra i centri delle ore.
    Tra due punti distanti più di max_gap vale il bordo entro mezz'ora, poi None."""

    def __init__(self, stats, max_gap: int = 3 * 3600):
        pts = sorted((s + 1800, m) for s, m in stats if m is not None)
        self.ts = [p[0] for p in pts]
        self.vals = [p[1] for p in pts]
        self.max_gap = max_gap

    def __call__(self, ts):
        if not self.ts:
            return None
        i = bisect.bisect_right(self.ts, ts)
        if i == 0:
            return self.vals[0] if self.ts[0] - ts <= 1800 else None
        t0, v0 = self.ts[i - 1], self.vals[i - 1]
        if ts == t0:
            return v0
        if i == len(self.ts):
            return v0 if ts - t0 <= 1800 else None
        t1, v1 = self.ts[i], self.vals[i]
        if t1 - t0 > self.max_gap:
            if ts - t0 <= 1800:
                return v0
            if t1 - ts <= 1800:
                return v1
            return None
        return v0 + (v1 - v0) * (ts - t0) / (t1 - t0)


# ---------- campioni

def build_samples(cp: dict, split: dict, io: dict, m_cp, m_tosh, zones: dict, end_ts: int) -> list[dict]:
    """Un campione per ogni minuto CP prima di end_ts (escluso); gli altri dispositivi a
    forward-fill limitato, le zone interpolate dalle medie orarie."""
    sp = StepLookup([(t, decode_split(r)) for t, r in split.items()], DEV_MAX_AGE_S)
    te = StepLookup([(t, num(r.get(IO_COL))) for t, r in io.items()], DEV_MAX_AGE_S)
    pc = StepLookup(m_cp, METER_MAX_AGE_S)
    pt = StepLookup(m_tosh, METER_MAX_AGE_S)
    empty_split = {"tosh_on": None, "tosh_modo": None, "tosh_vent": None}
    # prima della prima statistica di zona di HA le zone mancano: ripiego sulla sonda ambiente Nilan T10
    zone_start = min((z.ts[0] - 1800 if z.ts else float("inf")) for z in zones.values())
    out, stagione = [], None
    for ts in sorted(cp):
        if ts >= end_ts:
            break
        c = decode_cp(cp[ts])
        stagione = stagione_of(c["cp_modo"], c.pop("mode_act"), c["cp_stato"], stagione)
        snap = {"stagione": stagione, "free_cooling": None, "tosh_rps": None, **c,
                **(sp(ts) or empty_split),
                "t_ext": te(ts), "p_cp": pc(ts), "p_tosh": pt(ts),
                "t_zg": zones["t_zg"](ts), "t_zn": zones["t_zn"](ts)}
        if snap["t_zg"] is None and snap["t_zn"] is None and ts < zone_start:
            snap["t_zg"] = snap["t_zn"] = snap["t10"]
        out.append(build_sample(snap, ts, None))
    return out


# ---------- CLI

def _load(d: str, names: list[str]) -> list:
    chunks = []
    for n in names:
        with open(os.path.join(d, n)) as f:
            chunks.extend(json.load(f))
    return chunks


def _meter(d: str, names: list[str]) -> list[tuple[int, float | None]]:
    return [(t, num(r.get(METER_COL))) for t, r in parse_chunks(_load(d, names), [METER_COL]).items()]


def _fmt(ts) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(ts))


def parse_ts(s: str) -> int:
    """Epoch oppure data/ora locale (Europe/Rome) AAAA-MM-GG[THH:MM[:SS]]."""
    if s.strip().isdigit():
        return int(s)
    return int(datetime.fromisoformat(s).replace(tzinfo=GW_TZ).timestamp())


def replace_invalid(store, samples: list[dict], before: int, motivi=REPLACE_MOTIVI) -> tuple[Counter, list[dict]]:
    """Sostituisce i campioni esistenti con ts < before, non validi per uno dei motivi dati,
    con quelli ricostruiti. Gli altri campioni (e i minuti assenti dal DB) restano intatti.
    Ritorna ({(motivo precedente, nuovo esito): n}, campioni scritti)."""
    done: Counter = Counter()
    written = []
    with store._lock:
        old = {r[0]: r[1] for r in store.db.execute(
            f"SELECT ts, motivo FROM samples WHERE ts < ? AND valido = 0 AND motivo IN ({','.join('?' * len(motivi))})",
            (before, *motivi))}
        rows = []
        for s in samples:
            if s["ts"] in old and s["ts"] < before:
                done[(old[s["ts"]], "valido" if s["valido"] else s["motivo"])] += 1
                written.append(s)
                s = dict(s, cp_compressore=_norm_onoff(s.get("cp_compressore")))
                rows.append([s.get(c) for c in SAMPLE_COLS])
        store.db.executemany(f"INSERT OR REPLACE INTO samples ({','.join(SAMPLE_COLS)}) "
                             f"VALUES ({','.join('?' * len(SAMPLE_COLS))})", rows)
        store.db.commit()
    return done, written


def import_dir(d: str, db_path: str, replace_before: int | None = None) -> int:
    t0 = time.time()
    cp = parse_chunks(_load(d, FILES["cp"]), CP_COLS)
    split = parse_chunks(_load(d, FILES["split"]), SPLIT_COLS)
    io = parse_chunks(_load(d, FILES["io"]), [IO_COL])
    m_cp, m_tosh = _meter(d, FILES["m_cp"]), _meter(d, FILES["m_tosh"])
    with open(os.path.join(d, ZONE_FILE)) as f:
        zs = json.load(f)
    zones = {k: HourlyInterp([(float(s), num(m)) for s, m in zs.get(sid) or []]) for k, sid in ZONE_IDS.items()}
    print(f"letti: cp {len(cp)}, split {len(split)}, io {len(io)}, contatori {len(m_cp)}/{len(m_tosh)}, "
          f"zone {len(zs.get(ZONE_IDS['t_zg']) or [])}/{len(zs.get(ZONE_IDS['t_zn']) or [])} ore")
    store = Store(db_path)
    with store._lock:
        first = store.db.execute("SELECT MIN(ts) FROM samples").fetchone()[0]
    end = first if first is not None else int(time.time())
    if replace_before is not None:
        samples = build_samples(cp, split, io, m_cp, m_tosh, zones, replace_before)
        done, written = replace_invalid(store, samples, replace_before)
        n = sum(done.values())
        print(f"sostituiti {n} campioni con ts < {_fmt(replace_before)}")
        for (old, new), k in sorted(done.items(), key=lambda x: -x[1]):
            print(f"  {old} -> {new}: {k}")
        v = [s for s in written if s["valido"]]
        print("codici dei sostituiti validi (top 20): " + ", ".join(
            f"E{c}={k}" for c, k in Counter(s["code"] for s in v).most_common(20)))
        print("codici V1 (u=7/8): " + ", ".join(
            f"E{c}={k}" for c, k in sorted(Counter(s["code"] for s in v if s["code"] % 10 >= 7).items())))
        return n
    samples = build_samples(cp, split, io, m_cp, m_tosh, zones, end)
    if not samples:
        print("nessun campione da inserire")
        return 0
    assert samples[-1]["ts"] < end
    with store._lock:  # mai sovrascrivere: INSERT OR IGNORE
        rows = []
        for s in samples:
            s = dict(s, cp_compressore=_norm_onoff(s.get("cp_compressore")))
            rows.append([s.get(c) for c in SAMPLE_COLS])
        cur = store.db.executemany(f"INSERT OR IGNORE INTO samples ({','.join(SAMPLE_COLS)}) "
                                   f"VALUES ({','.join('?' * len(SAMPLE_COLS))})", rows)
        inserted = cur.rowcount
        store.db.commit()
    valid = [s for s in samples if s["valido"]]
    print(f"periodo {_fmt(samples[0]['ts'])} -> {_fmt(samples[-1]['ts'])} (primo campione esistente {_fmt(end)})")
    print(f"campioni {len(samples)}, inseriti {inserted}, validi {len(valid)} ({time.time() - t0:.0f} s)")
    print("codici (top 20): " + ", ".join(f"E{c}={n}" for c, n in
                                          Counter(s["code"] for s in valid).most_common(20)))
    motivi = Counter(s["motivo"] for s in samples if not s["valido"])
    print("non validi: " + ", ".join(f"{m}={n}" for m, n in motivi.most_common(15)))
    for st in sorted({s["stagione"] for s in samples}, key=str):
        ss = [s for s in samples if s["stagione"] == st]
        v = [s for s in ss if s["valido"]]
        tipi = Counter(s["tipo"] for s in v)
        print(f"stagione {st}: campioni {len(ss)}, validi {len(v)}, tipi {dict(tipi)}")
    return inserted


def main(argv: list[str]) -> int:
    args, before = list(argv), None
    if "--replace-before" in args:
        i = args.index("--replace-before")
        if i + 1 >= len(args):
            print("--replace-before richiede un valore")
            return 2
        before = parse_ts(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print("uso: python -m ecm_engine.gw_import <cartella> [--replace-before <epoch|AAAA-MM-GGTHH:MM>]")
        return 2
    import_dir(args[0], config.DB_PATH, before)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Campioni -> periodi a combinazione costante."""
import math
from collections import deque
from dataclasses import dataclass
from statistics import median

from . import config
from .combo import RESISTENZA_ACS

R_ACS_DEFAULT = 1320.0   # W, resistenza ACS misurata sul contatore Nilan (03-08/11: 1260-1390)
ACS_LAG_S = 180          # il contatore segue il flag della resistenza con 1-2 minuti di ritardo
ACS_CTX_S = 600          # minuti senza resistenza prima e dopo, per la base del consumo Nilan
TEXT_ASSEST_S = 600      # la sonda esterna (condotto Compact) è affidabile dopo 10 min di ventilazione
TEXT_MAX_GAP_S = 12 * 3600   # interpolazione tra due letture buone distanti al più 12 ore
TEXT_HOLD_S = 6 * 3600       # senza lettura buona dopo: ultima buona per al più 6 ore


@dataclass
class Period:
    code: int
    tipo: str
    start: int
    end: int
    minutes: int
    p_cp: float
    p_tosh: float
    p_tot: float
    duty_cp: float
    duty_tosh: float
    slope_zg: float
    slope_zn: float
    t_ext: float
    da_prova: bool
    p_cp_on: float | None = None


def slope_per_hour(ts: list[int], ys: list[float]) -> float:
    n = len(ts)
    if n < 2:
        return 0.0
    xs = [t / 3600 for t in ts]
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def _mean(v):
    return sum(v) / len(v) if v else 0.0


def _close(group, settle_s, min_useful_s):
    t0 = group[0]["ts"]
    rows = [r for r in group if r["ts"] >= t0 + settle_s]
    if not rows or (rows[-1]["ts"] - rows[0]["ts"] + config.SAMPLE_PERIOD_S) < min_useful_s:
        return None
    ts = [r["ts"] for r in rows]
    p_cp = _mean([r["p_cp"] for r in rows])
    p_tosh = _mean([r["p_tosh"] for r in rows])
    on = [r["p_cp"] for r in rows if r["cp_compressore"]]
    return Period(
        code=rows[0]["code"], tipo=rows[0]["tipo"], start=ts[0], end=ts[-1], minutes=len(rows),
        p_cp=round(p_cp, 1), p_tosh=round(p_tosh, 1), p_tot=round(p_cp + p_tosh, 1),
        duty_cp=_mean([1.0 if r["cp_compressore"] else 0.0 for r in rows]),
        duty_tosh=_mean([1.0 if (r["tosh_rps"] or 0) > 0 else 0.0 for r in rows]),
        slope_zg=slope_per_hour(ts, [r["t_zg"] for r in rows]),
        slope_zn=slope_per_hour(ts, [r["t_zn"] for r in rows]),
        t_ext=_mean([r["t_ext"] for r in rows]),
        da_prova=rows[0]["test_id"] is not None,
        p_cp_on=round(_mean(on), 1) if on else None,
    )


_REQUIRED = ("t_zg", "t_zn", "p_cp", "p_tosh", "t_ext")


def _base(ctx: list[dict], target: list[dict]) -> dict:
    """Consumo Nilan senza resistenza, separato per compressore acceso/spento: dai minuti di
    contesto, altrimenti dai minuti dell'episodio chiaramente senza resistenza."""
    def med(rows, comp):
        v = [r["p_cp"] for r in rows if r.get("p_cp") is not None and bool(r.get("cp_compressore")) == comp]
        return median(v) if v else None
    out = {c: med(ctx, c) for c in (False, True)}
    if out[False] is None and out[True] is None:
        v = [r["p_cp"] for r in target if r.get("p_cp") is not None]
        if v:
            lo = min(v)
            low = [r for r in target if r.get("p_cp") is not None and r["p_cp"] < lo + R_ACS_DEFAULT / 2]
            out = {c: med(low, c) for c in (False, True)}
    for c in (False, True):
        if out[c] is None:
            out[c] = out[not c]
    return out


def fix_acs_episode(target: list[dict], ctx: list[dict]) -> list[dict]:
    """Toglie la resistenza ACS dal consumo Nilan dei minuti dell'episodio (e del ritardo del
    contatore). Deterministico:
    - base = consumo Nilan senza resistenza (compressore acceso/spento) dai minuti vicini;
    - un minuto "con resistenza" supera la base di almeno metà resistenza;
    - resistenza dell'episodio = mediana dell'eccesso sui minuti con resistenza;
    - minuto con resistenza: consumo - resistenza; minuto a metà (transizione) o sotto la base
      dopo la correzione: consumo = base."""
    base = _base(ctx, target)
    if base[False] is None:
        return target

    def b(r):
        return base[bool(r.get("cp_compressore"))]

    exc = [r["p_cp"] - b(r) for r in target if r.get("p_cp") is not None]
    high = [x for x in exc if x > R_ACS_DEFAULT / 2]
    r_ep = median(high) if high else R_ACS_DEFAULT
    out = []
    for r in target:
        p = r.get("p_cp")
        if p is None:
            out.append(r)
            continue
        x = p - b(r)
        if x > R_ACS_DEFAULT / 2:
            q = p - r_ep
            q = b(r) if q < b(r) - 100 else max(q, 0.0)
        elif x > 100:
            q = b(r)
        else:
            q = p
        out.append(dict(r, p_cp=round(q, 1), p_cp_stimato=q != p))
    return out


def correct_acs(samples):
    """Generatore: passa i campioni invariati, tranne gli episodi di resistenza ACS (motivo
    RESISTENZA_ACS) più ACS_LAG_S dopo, a cui toglie il consumo della resistenza."""
    pre: deque = deque()
    buf: list[dict] = []
    last_acs = None
    pending = iter(samples)
    for r in pending:
        acs = r.get("motivo") == RESISTENZA_ACS
        if last_acs is None:
            if not acs:
                pre.append(r)
                while r["ts"] - pre[0]["ts"] > ACS_CTX_S:
                    pre.popleft()
                yield r
                continue
            buf, last_acs = [r], r["ts"]
            continue
        if r["ts"] > last_acs + ACS_LAG_S + ACS_CTX_S:
            yield from _flush(pre, buf, last_acs)
            pre, buf, last_acs = deque(x for x in buf if x["ts"] > last_acs + ACS_LAG_S), [], None
            if acs:
                buf, last_acs = [r], r["ts"]
            else:
                pre.append(r)
                while r["ts"] - pre[0]["ts"] > ACS_CTX_S:
                    pre.popleft()
                yield r
            continue
        buf.append(r)
        if acs:
            last_acs = r["ts"]
    if last_acs is not None:
        yield from _flush(pre, buf, last_acs)


def _flush(pre, buf, last_acs):
    target = [r for r in buf if r["ts"] <= last_acs + ACS_LAG_S]
    post = [r for r in buf if r["ts"] > last_acs + ACS_LAG_S]
    ctx = [r for r in list(pre) + post if r.get("motivo") != RESISTENZA_ACS]
    yield from fix_acs_episode(target, ctx)
    yield from post


def _ventila(r: dict) -> bool:
    c = r.get("code")
    return c is not None and c % 10 != 0


def _fill_text(buf: list[dict], prima, dopo) -> list[dict]:
    """Minuti senza lettura affidabile: interpolati tra prima e dopo (ts, °C), oppure l'ultima
    buona entro TEXT_HOLD_S, altrimenti il valore grezzo."""
    out = []
    for r in buf:
        if prima and dopo and dopo[0] - prima[0] <= TEXT_MAX_GAP_S:
            v = prima[1] + (dopo[1] - prima[1]) * (r["ts"] - prima[0]) / (dopo[0] - prima[0])
        elif prima and r["ts"] - prima[0] <= TEXT_HOLD_S:
            v = prima[1]
        else:
            out.append(r)
            continue
        out.append(dict(r, t_ext=round(v, 2), t_ext_stimata=True))
    return out


def fix_text(samples):
    """Generatore: la temperatura esterna vale solo dopo TEXT_ASSEST_S di ventilazione Compact
    continua (con la Compact ferma la sonda legge aria ferma, in media +2,2 °C). Gli altri
    minuti la ricevono interpolata tra le letture buone vicine (vedi _fill_text)."""
    prima = None          # ultima lettura buona (ts, °C)
    on_since = None
    buf: list[dict] = []
    for r in samples:
        if _ventila(r):
            on_since = r["ts"] if on_since is None else on_since
        else:
            on_since = None
        buona = on_since is not None and r["ts"] - on_since >= TEXT_ASSEST_S and r.get("t_ext") is not None
        if buona:
            dopo = (r["ts"], r["t_ext"])
            yield from _fill_text(buf, prima, dopo)
            buf = []
            prima = dopo
            yield r
            continue
        buf.append(r)
        if r["ts"] - buf[0]["ts"] > TEXT_MAX_GAP_S:
            # nessuna lettura buona da troppo: questi minuti non avranno una "dopo" utile
            yield from _fill_text(buf, prima, None)
            buf = []
    yield from _fill_text(buf, prima, None)


def _usable(r: dict) -> bool:
    if not r.get("valido") or r.get("code") is None:
        return False
    for k in _REQUIRED:
        v = r.get(k)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return False
    return True


def segment(samples, gap_s: int = 180, settle_s: int = 300,
            min_useful_s: int = 600) -> list[Period]:
    out, group = [], []
    for r in correct_acs(fix_text(samples)):
        ok = _usable(r)
        if group and ok and r["code"] == group[-1]["code"] \
                and r.get("test_id") == group[-1].get("test_id") \
                and r["ts"] - group[-1]["ts"] <= gap_s:
            group.append(r)
            continue
        if group:
            p = _close(group, settle_s, min_useful_s)
            if p:
                out.append(p)
        group = [r] if ok else []
    if group:
        p = _close(group, settle_s, min_useful_s)
        if p:
            out.append(p)
    return out

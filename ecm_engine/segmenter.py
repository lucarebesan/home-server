"""Campioni -> periodi a combinazione costante."""
from dataclasses import dataclass


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
    if not rows or (rows[-1]["ts"] - rows[0]["ts"] + 60) < min_useful_s:
        return None
    ts = [r["ts"] for r in rows]
    p_cp = _mean([r["p_cp"] for r in rows])
    p_tosh = _mean([r["p_tosh"] for r in rows])
    return Period(
        code=rows[0]["code"], tipo=rows[0]["tipo"], start=ts[0], end=ts[-1], minutes=len(rows),
        p_cp=round(p_cp, 1), p_tosh=round(p_tosh, 1), p_tot=round(p_cp + p_tosh, 1),
        duty_cp=_mean([1.0 if r["cp_compressore"] else 0.0 for r in rows]),
        duty_tosh=_mean([1.0 if (r["tosh_rps"] or 0) > 0 else 0.0 for r in rows]),
        slope_zg=slope_per_hour(ts, [r["t_zg"] for r in rows]),
        slope_zn=slope_per_hour(ts, [r["t_zn"] for r in rows]),
        t_ext=_mean([r["t_ext"] for r in rows]),
        da_prova=rows[0]["test_id"] is not None,
    )


def segment(samples: list[dict], gap_s: int = 180, settle_s: int = 300,
            min_useful_s: int = 600) -> list[Period]:
    out, group = [], []
    for r in samples:
        ok = r.get("valido") and r.get("code") is not None
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

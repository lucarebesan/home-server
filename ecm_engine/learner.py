"""Aggregazione periodi -> statistiche per (codice, tipo, fascia esterna)."""
import math
from dataclasses import dataclass
from statistics import pstdev

from .combo import tipo_of

FASCE = [(-99, 5, "<5"), (5, 10, "5-10"), (10, 15, "10-15"), (15, 20, "15-20"),
         (20, 25, "20-25"), (25, 30, "25-30"), (30, 99, "≥30")]
NOMI = [f[2] for f in FASCE]
SIGN = {"HEAT": 1, "COOL": -1, "DRY": -1, "NEUTRO": 0}
EFF_MIN = 0.1


@dataclass
class Stat:
    code: int
    tipo: str
    fascia: str
    periodi: int
    minuti: int
    p_tot: float
    duty_cp: float
    duty_tosh: float
    eff_zg: float
    eff_zn: float
    eff: float
    costo: float | None
    affidabilita: float
    p_cp_on: float | None = None


def fascia(t_ext: float) -> str:
    if t_ext is None or not isinstance(t_ext, (int, float)) or not math.isfinite(t_ext):
        raise ValueError(f"t_ext non valida: {t_ext!r}")
    for lo, hi, name in FASCE:
        if lo <= t_ext < hi:
            return name
    return NOMI[-1]


def _wmean(vals, weights):
    tw = sum(weights)
    return sum(v * w for v, w in zip(vals, weights)) / tw if tw else 0.0


def aggregate(periods) -> dict:
    groups = {}
    for p in periods:
        groups.setdefault((p.code, p.tipo, fascia(p.t_ext)), []).append(p)
    out = {}
    for (code, tipo, f), ps in groups.items():
        sign = SIGN[tipo]
        w = [p.minutes for p in ps]
        eff_zg = sign * _wmean([p.slope_zg for p in ps], w)
        eff_zn = sign * _wmean([p.slope_zn for p in ps], w)
        eff = (eff_zg + eff_zn) / 2
        p_tot = _wmean([p.p_tot for p in ps], w)
        if sign == 0:
            serie = [p.p_tot for p in ps]
        else:
            serie = [sign * (p.slope_zg + p.slope_zn) / 2 for p in ps]
        m = sum(serie) / len(serie)
        coerente = len(serie) < 2 or (abs(m) > 0 and pstdev(serie) < 0.5 * abs(m))
        aff = min(len(ps) / 5, 1.0) * (1.0 if coerente else 0.6)
        costo = p_tot / eff if sign != 0 and eff > EFF_MIN else None
        on_w = [p.minutes * p.duty_cp for p in ps]
        p_cp_on = (sum(p.p_cp_on * w for p, w in zip(ps, on_w) if p.p_cp_on is not None)
                   / sum(w for p, w in zip(ps, on_w) if p.p_cp_on is not None)
                   if any(p.p_cp_on is not None and w > 0 for p, w in zip(ps, on_w)) else None)
        out[(code, tipo, f)] = Stat(code, tipo, f, len(ps), sum(w), round(p_tot, 1),
                              _wmean([p.duty_cp for p in ps], w), _wmean([p.duty_tosh for p in ps], w),
                              eff_zg, eff_zn, eff, costo, aff, p_cp_on)
    return out


def _vicine(f: str) -> list[str]:
    i = NOMI.index(f)
    return [NOMI[j] for j in (i - 1, i + 1) if 0 <= j < len(NOMI)]


def ranking(stats: dict, tipo: str, f: str) -> list[Stat]:
    sel = [s for s in stats.values() if s.tipo == tipo and s.fascia == f]
    if not sel:
        sel = [s for s in stats.values() if s.tipo == tipo and s.fascia in _vicine(f)]
    return sorted(sel, key=lambda s: (s.costo is None, s.costo or 0, s.p_tot))


def learning_pct(stats: dict, codes: list[int], f: str, stagione: str) -> int:
    if not codes:
        return 0
    keys = [(c, tipo_of(c, stagione), f) for c in codes]
    tot = sum(stats[k].affidabilita if k in stats else 0.0 for k in keys)
    return round(100 * tot / len(codes))

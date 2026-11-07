"""Aggregazione periodi -> statistiche per (combinazione, fascia esterna)."""
from dataclasses import dataclass
from statistics import pstdev

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


def fascia(t_ext: float) -> str:
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
        groups.setdefault((p.code, fascia(p.t_ext)), []).append(p)
    out = {}
    for (code, f), ps in groups.items():
        tipo, sign = ps[0].tipo, SIGN[ps[0].tipo]
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
        coerente = len(serie) < 2 or pstdev(serie) <= 0.5 * abs(m)
        aff = min(len(ps) / 5, 1.0) * (1.0 if coerente else 0.6)
        costo = p_tot / eff if sign != 0 and eff > EFF_MIN else None
        out[(code, f)] = Stat(code, tipo, f, len(ps), sum(w), round(p_tot, 1),
                              _wmean([p.duty_cp for p in ps], w), _wmean([p.duty_tosh for p in ps], w),
                              eff_zg, eff_zn, eff, costo, aff)
    return out


def _vicine(f: str) -> list[str]:
    i = NOMI.index(f)
    return [NOMI[j] for j in (i - 1, i + 1) if 0 <= j < len(NOMI)]


def ranking(stats: dict, tipo: str, f: str) -> list[Stat]:
    sel = [s for s in stats.values() if s.tipo == tipo and s.fascia == f]
    if not sel:
        sel = [s for s in stats.values() if s.tipo == tipo and s.fascia in _vicine(f)]
    return sorted(sel, key=lambda s: (s.costo is None, s.costo or 0, s.p_tot))


def learning_pct(stats: dict, codes: list[int], f: str) -> int:
    if not codes:
        return 0
    tot = sum(stats[(c, f)].affidabilita if (c, f) in stats else 0.0 for c in codes)
    return round(100 * tot / len(codes))

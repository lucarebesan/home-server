"""Consumo delle due macchine, appreso separatamente dai campioni corretti."""
import math
from dataclasses import dataclass

from .learner import fascia


@dataclass(frozen=True)
class PowerStat:
    W: float
    minuti: int
    periodi: int


class PowerLearner:
    """Un cambio della CP non interrompe l'assestamento dello SPLIT e viceversa."""

    def __init__(self, settle_s: int = 300, min_useful_s: int = 600, gap_s: int = 180):
        self.settle_s = settle_s
        self.min_useful_s = min_useful_s
        self.gap_s = gap_s
        self._runs = {"cp": [], "tosh": []}
        self._sums = {}

    def _close(self, unit):
        run = self._runs[unit]
        self._runs[unit] = []
        if not run:
            return
        useful = [r for r in run if r["ts"] >= run[0]["ts"] + self.settle_s]
        if not useful or useful[-1]["ts"] - useful[0]["ts"] + 60 < self.min_useful_s:
            return
        by_band = {}
        for r in useful:
            key = (r["stagione"], unit, r["unit_code"], fascia(r["t_ext"]))
            by_band.setdefault(key, []).append(r["power"])
        for key, values in by_band.items():
            total, minutes, periods = self._sums.get(key, (0.0, 0, 0))
            self._sums[key] = (total + sum(values), minutes + len(values), periods + 1)

    def feed(self, row):
        code = row.get("code")
        season = row.get("stagione")
        ts = row.get("ts")
        ext = row.get("t_ext")
        for unit, column in (("cp", "p_cp"), ("tosh", "p_tosh")):
            power = row.get(column)
            valid = (row.get("valido") and isinstance(code, int) and season in ("INVERNO", "ESTATE")
                     and isinstance(ts, int) and isinstance(ext, (int, float)) and math.isfinite(ext)
                     and isinstance(power, (int, float)) and math.isfinite(power))
            if not valid:
                self._close(unit)
                continue
            unit_code = code % 10 if unit == "cp" else code // 10
            run = self._runs[unit]
            if run and ((season, unit_code) != (run[-1]["stagione"], run[-1]["unit_code"])
                        or ts - run[-1]["ts"] > self.gap_s):
                self._close(unit)
                run = self._runs[unit]
            run.append({"ts": ts, "stagione": season, "unit_code": unit_code,
                        "t_ext": ext, "power": power})

    def result(self):
        for unit in self._runs:
            self._close(unit)
        return {key: PowerStat(round(total / minutes, 1), minutes, periods)
                for key, (total, minutes, periods) in self._sums.items() if minutes}


def combo_w(power_stats, code: int, band: str, season: str):
    """Somma dei consumi appresi della CP e dello SPLIT nella stessa fascia."""
    cp = power_stats.get((season, "cp", code % 10, band))
    tosh = power_stats.get((season, "tosh", code // 10, band))
    return (round(cp.W + tosh.W), cp, tosh) if cp and tosh else (None, cp, tosh)

"""Candidati, proposta di prova, condizioni di avvio e di interruzione."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .combo import tipo_of
from .learner import EFF_MIN, fascia

AUTO_WINDOW = (time(10, 0), time(17, 0))
AUTO_MAX_PER_DAY = 3
AUTO_PAUSE = timedelta(minutes=60)
MARGINE = 0.3


@dataclass
class Ctx:
    now: datetime
    stagione: str
    manuale: str
    free_cooling: str
    acs_attivo: bool
    soc: float
    pv: float
    load: float
    t_zg: float
    t_zn: float
    lim_inf: float
    lim_sup: float
    mattina: time
    serale: time
    t_ext: float


@dataclass
class Proposal:
    code: int
    tipo: str
    durata: int
    motivo: str


def is_night(c: Ctx) -> bool:
    """Giorno = tra mattina e serale (anche se serale è dopo mezzanotte).
    Se mattina == serale non c'è notte."""
    t = c.now.time()
    if c.mattina == c.serale:
        return False
    if c.mattina < c.serale:
        return not (c.mattina <= t < c.serale)
    return not (t >= c.mattina or t < c.serale)


def codes_for_season(stagione: str, night: bool) -> list[int]:
    if stagione == "INVERNO":
        codes = [0, 1, 2, 3, 4, 5, 6] + [10 * d + u for d in (7, 8, 9) for u in range(7)]
    elif stagione == "ESTATE":
        codes = [0, 1, 2, 3, 4, 5, 6] + [10 * d + u for d in range(1, 7) for u in range(7)]
    else:
        return []
    if night:
        codes = [c for c in codes if c % 10 not in (3, 6) and not (c >= 10 and (c // 10) % 3 == 0)]
    return codes


def _energia_ok(c: Ctx, soc_min: float) -> bool:
    return c.soc >= soc_min or c.pv >= c.load


def zone_blockers(c: Ctx, tipo: str) -> list[str]:
    b = []
    zmax, zmin = max(c.t_zg, c.t_zn), min(c.t_zg, c.t_zn)
    lo, hi = c.lim_inf + MARGINE, c.lim_sup - MARGINE
    if tipo in ("HEAT", "NEUTRO") and zmax > hi:
        b.append("zona troppo calda per scaldare" if tipo == "HEAT" else "zona fuori fascia")
    if tipo in ("COOL", "DRY", "NEUTRO") and zmin < lo:
        b.append("zona troppo fredda per raffrescare" if tipo != "NEUTRO" else "zona fuori fascia")
    return b


def start_blockers(c: Ctx, tipo: str, auto: bool, tests_today: int,
                   last_end: datetime | None) -> list[str]:
    b = []
    if c.manuale != "AUTO":
        b.append("modalità manuale già attiva")
    if c.free_cooling in ("ATTIVATO", "PREPARAZIONE"):
        b.append("free cooling attivo")
    if c.acs_attivo:
        b.append("ciclo ACS in corso")
    if not _energia_ok(c, 40):
        b.append("energia insufficiente")
    b += zone_blockers(c, tipo)
    if auto:
        if not (AUTO_WINDOW[0] <= c.now.time() < AUTO_WINDOW[1]):
            b.append("fuori finestra prove automatiche")
        if tests_today >= AUTO_MAX_PER_DAY:
            b.append(f"già {AUTO_MAX_PER_DAY} prove oggi")
        if last_end and c.now - last_end < AUTO_PAUSE:
            b.append("pausa tra le prove")
    return b


def abort_reason(c: Ctx, tipo: str, expected_label: str) -> str | None:
    if c.manuale != expected_label:
        return "interrotta dall'utente"
    zmax, zmin = max(c.t_zg, c.t_zn), min(c.t_zg, c.t_zn)
    if tipo in ("HEAT", "NEUTRO") and zmax > c.lim_sup:
        return "zona oltre il limite superiore"
    if tipo in ("COOL", "DRY", "NEUTRO") and zmin < c.lim_inf:
        return "zona sotto il limite inferiore"
    if c.soc < 25 and c.pv < c.load:
        return "batteria sotto 25%"
    return None


def propose(stats: dict, c: Ctx) -> Proposal | None:
    f = fascia(c.t_ext)
    cands = [x for x in codes_for_season(c.stagione, is_night(c))
             if not zone_blockers(c, tipo_of(x, c.stagione))]
    if not cands:
        return None

    def key(code):
        tipo = tipo_of(code, c.stagione)
        st = stats.get((code, tipo, f))
        return (st.affidabilita if st else 0.0, tipo == "NEUTRO", code)

    code = min(cands, key=key)
    tipo = tipo_of(code, c.stagione)
    st = stats.get((code, tipo, f))
    if tipo == "NEUTRO":
        if st is None or st.affidabilita < 1:
            durata, motivo = 15, "manca il consumo"
        else:
            durata, motivo = 20, "dato da confermare"
    elif st is None or st.eff < EFF_MIN:
        durata, motivo = 30, "manca l'efficacia"
    else:
        durata, motivo = 20, "dato da confermare"
    return Proposal(code, tipo, durata, motivo)

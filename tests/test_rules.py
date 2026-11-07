from datetime import datetime, time
from ecm_engine.rules import Ctx, abort_reason, codes_for_season, propose, start_blockers
from ecm_engine.learner import aggregate
from ecm_engine.segmenter import Period

def ctx(**kw):
    base = dict(now=datetime(2026, 11, 8, 11, 0), stagione="INVERNO", manuale="AUTO",
                free_cooling="DISATTIVATO", acs_attivo=False, soc=60.0, pv=0.0, load=800.0,
                t_zg=21.0, t_zn=20.8, lim_inf=20.0, lim_sup=21.7, mattina=time(8, 30),
                serale=time(22, 0), t_ext=8.0)
    base.update(kw)
    return Ctx(**base)

def test_codes_inverno_day_night():
    day = codes_for_season("INVERNO", night=False)
    assert 0 not in day and 1 in day and 4 in day and 96 in day and 45 not in day
    night = codes_for_season("INVERNO", night=True)
    assert 6 not in night and 93 not in night and 3 not in night and 85 in night

def test_codes_estate():
    c = codes_for_season("ESTATE", night=False)
    assert 66 in c and 14 in c and 74 not in c

def test_blockers_ok():
    assert start_blockers(ctx(), "HEAT", auto=False, tests_today=0, last_end=None) == []

def test_blockers_each():
    assert "modalità manuale già attiva" in start_blockers(ctx(manuale="E5 - CP ON V3 • Split OFF"), "HEAT", False, 0, None)
    assert "ciclo ACS in corso" in start_blockers(ctx(acs_attivo=True), "HEAT", False, 0, None)
    assert "energia insufficiente" in start_blockers(ctx(soc=30, pv=100, load=800), "HEAT", False, 0, None)
    assert start_blockers(ctx(soc=30, pv=900, load=800), "HEAT", False, 0, None) == []
    assert "zona troppo calda per scaldare" in start_blockers(ctx(t_zg=21.5), "HEAT", False, 0, None)
    assert "zona troppo fredda per raffrescare" in start_blockers(ctx(stagione="ESTATE", t_zn=20.1), "COOL", False, 0, None)

def test_blockers_auto_only():
    assert "fuori finestra prove automatiche" in start_blockers(ctx(now=datetime(2026, 11, 8, 18, 0)), "HEAT", True, 0, None)
    assert "già 3 prove oggi" in start_blockers(ctx(), "HEAT", True, 3, None)
    assert "pausa tra le prove" in start_blockers(ctx(), "HEAT", True, 1, datetime(2026, 11, 8, 10, 30))
    assert start_blockers(ctx(now=datetime(2026, 11, 8, 18, 0)), "HEAT", False, 3, None) == []

def test_abort():
    lbl = "E84 - CP ON V2 • HEAT V2"
    assert abort_reason(ctx(manuale=lbl), "HEAT", lbl) is None
    assert abort_reason(ctx(manuale="AUTO"), "HEAT", lbl) == "interrotta dall'utente"
    assert abort_reason(ctx(manuale=lbl, t_zg=21.8), "HEAT", lbl) == "zona oltre il limite superiore"
    assert abort_reason(ctx(manuale=lbl, soc=24, pv=0), "HEAT", lbl) == "batteria sotto 25%"

def per(code, tipo, s=1.0):
    return Period(code, tipo, 0, 1, 20, 300.0, 0.0, 300.0, 1.0, 0.0, s, s, 8.0, False)

def test_propose_picks_least_known_and_duration():
    stats = aggregate([per(c, "HEAT") for c in codes_for_season("INVERNO", False) if c >= 4] * 5)
    p = propose(stats, ctx())
    assert p.code in (1, 2, 3) and p.durata == 15       # restano solo i neutri senza dati
    p2 = propose({}, ctx())
    assert p2.code == 4 and p2.durata == 30              # niente dati: prima prova HEAT, 30 min

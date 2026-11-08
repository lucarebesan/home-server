from datetime import datetime, time
from ecm_engine.rules import (Ctx, abort_reason, codes_for_season, is_night, propose,
                              start_blockers, zone_blockers)
from ecm_engine.learner import aggregate
from ecm_engine.segmenter import Period

def ctx(**kw):
    base = dict(now=datetime(2026, 11, 8, 11, 0), stagione="INVERNO", manuale="AUTO",
                free_cooling="DISATTIVATO", acs_attivo=False, soc=60.0, pv=0.0, load=800.0,
                t_zg=21.0, t_zn=20.8, lim_inf=20.0, lim_sup=21.7, mattina=time(8, 30),
                serale=time(22, 0), t_ext=8.0, soglia_estate=24.5)
    base.update(kw)
    return Ctx(**base)

def test_codes_inverno_day_night():
    day = codes_for_season("INVERNO", night=False)
    assert 0 in day and 1 in day and 4 in day and 96 in day and 45 not in day
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
    assert "zona troppo calda per scaldare" in start_blockers(ctx(t_zg=23.6), "HEAT", False, 0, None)
    # d'inverno lim_sup (21.7) non limita più le prove di riscaldamento
    assert start_blockers(ctx(t_zg=22.0, t_zn=22.1), "HEAT", False, 0, None) == []
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
    assert abort_reason(ctx(manuale=lbl, t_zg=21.8), "HEAT", lbl) is None
    assert abort_reason(ctx(manuale=lbl, t_zg=24.1), "HEAT", lbl) == "zona vicina al cambio stagione"
    assert abort_reason(ctx(manuale=lbl, soc=24, pv=0), "HEAT", lbl) == "batteria sotto 25%"

def per(code, tipo, s=1.0):
    return Period(code, tipo, 0, 1, 20, 300.0, 0.0, 300.0, 1.0, 0.0, s, s, 8.0, False)

def test_propose_picks_least_known_and_duration():
    stats = aggregate([per(c, "HEAT") for c in codes_for_season("INVERNO", False) if c >= 4] * 5)
    p = propose(stats, ctx())
    assert p.code in (0, 1, 2, 3) and p.durata == 15       # restano solo i neutri senza dati
    p2 = propose({}, ctx())
    assert p2.code == 4 and p2.durata == 30              # niente dati: prima prova HEAT, 30 min

def test_codes_zero_both_seasons_and_unknown():
    assert 0 in codes_for_season("INVERNO", False) and 0 in codes_for_season("ESTATE", False)
    assert 0 in codes_for_season("ESTATE", True)
    assert codes_for_season("BOH", False) == []

def test_is_night_three_cases():
    at = lambda h, **kw: ctx(now=datetime(2026, 11, 8, h, 0), **kw)
    # normale
    assert not is_night(at(12)) and is_night(at(23)) and is_night(at(7))
    # serale dopo mezzanotte
    kw = dict(mattina=time(8, 0), serale=time(1, 0))
    assert not is_night(at(12, **kw)) and not is_night(at(0, **kw)) and is_night(at(3, **kw))
    # uguali: mai notte
    kw = dict(mattina=time(8, 0), serale=time(8, 0))
    assert not is_night(at(3, **kw)) and not is_night(at(12, **kw))

def test_zone_blockers_shared():
    assert zone_blockers(ctx(t_zg=23.6), "HEAT") == ["zona troppo calda per scaldare"]
    assert zone_blockers(ctx(t_zg=23.4), "HEAT") == []
    assert zone_blockers(ctx(t_zg=23.6, soglia_estate=26.0), "HEAT") == []
    assert zone_blockers(ctx(), "HEAT") == []

def test_zone_blockers_neutro_only_cold():
    assert zone_blockers(ctx(t_zg=23.0, t_zn=22.9), "NEUTRO") == []
    assert zone_blockers(ctx(t_zn=20.2), "NEUTRO") == ["zona troppo fredda"]
    assert zone_blockers(ctx(stagione="ESTATE", t_zn=20.2), "COOL") == ["zona troppo fredda per raffrescare"]
    assert zone_blockers(ctx(stagione="ESTATE", t_zn=20.2), "DRY") == ["zona troppo fredda per raffrescare"]

def test_abort_neutro_and_cool():
    lbl = "E2 - CP OFF V3 • Split OFF"
    assert abort_reason(ctx(manuale=lbl, t_zg=23.0), "NEUTRO", lbl) is None
    assert abort_reason(ctx(manuale=lbl, t_zn=19.9), "NEUTRO", lbl) == "zona sotto il limite inferiore"
    lbl = "E44 - CP ON V2 • COOL V1"
    assert abort_reason(ctx(stagione="ESTATE", manuale=lbl, t_zn=19.9), "COOL", lbl) == "zona sotto il limite inferiore"

def test_propose_skips_zone_blocked():
    # inverno, zona troppo calda per scaldare e troppo fredda per i neutri -> nessuna proposta
    assert propose({}, ctx(t_zg=23.6, t_zn=20.0)) is None
    # inverno, zona vicina al cambio stagione: solo neutri
    p = propose({}, ctx(t_zg=23.6))
    assert p is not None and p.tipo == "NEUTRO"
    # inverno, zona troppo fredda per i neutri ma non per scaldare: solo HEAT
    p = propose({}, ctx(t_zn=19.9))
    assert p is not None and p.tipo == "HEAT"
    # estate, zona troppo calda: niente neutri, solo COOL/DRY
    p = propose({}, ctx(stagione="ESTATE", t_zg=21.6))
    assert p is not None and p.tipo in ("COOL", "DRY")

def test_propose_duration_signed_eff():
    cands = [c for c in codes_for_season("INVERNO", False) if c != 4]
    stats = aggregate([per(4, "HEAT", s=-1.0)] * 5)
    stats.update(aggregate([per(c, "HEAT" if c >= 4 else "NEUTRO") for c in cands] * 5))
    p = propose(stats, ctx())
    assert p.code == 4 and p.durata == 30 and p.motivo == "manca l'efficacia"

def test_propose_neutro_durations(monkeypatch):
    monkeypatch.setattr("ecm_engine.rules.codes_for_season", lambda s, n: [2])
    p = propose({}, ctx())
    assert (p.durata, p.motivo) == (15, "manca il consumo")
    p = propose(aggregate([per(2, "NEUTRO")] * 2), ctx())          # affidabilita 0.4
    assert (p.durata, p.motivo) == (15, "manca il consumo")
    p = propose(aggregate([per(2, "NEUTRO")] * 5), ctx())          # affidabilita 1
    assert (p.durata, p.motivo) == (20, "dato da confermare")

def test_unknown_manuale_blocker():
    for v in ("unavailable", "unknown", None):
        b = start_blockers(ctx(manuale=v), "HEAT", False, 0, None)
        assert "stato manuale sconosciuto" in b and "modalità manuale già attiva" not in b

def test_neutro_summer_too_hot():
    hot = ctx(stagione="ESTATE", t_zg=22.0, t_zn=21.0)      # lim_sup 21.7
    assert "zona troppo calda" in start_blockers(hot, "NEUTRO", False, 0, None)
    assert abort_reason(hot, "NEUTRO", "AUTO") == "zona troppo calda"
    ok = ctx(stagione="ESTATE", t_zg=21.5, t_zn=21.0)
    assert start_blockers(ok, "NEUTRO", False, 0, None) == []
    assert abort_reason(ok, "NEUTRO", "AUTO") is None

def test_neutro_winter_not_blocked_by_lim_sup():
    w = ctx(t_zg=22.5, t_zn=22.0)
    assert start_blockers(w, "NEUTRO", False, 0, None) == []
    assert abort_reason(w, "NEUTRO", "AUTO") is None

def test_ordered_candidates_first_is_propose():
    from ecm_engine.rules import ordered_candidates
    stats = aggregate([Period(82, "HEAT", 0, 1, 20, 450.0, 0.0, 450.0, 1.0, 0.0, 1.0, 1.0, 8.0, False)] * 5)
    cs = ordered_candidates(stats, ctx())
    assert cs[0] == propose(stats, ctx())
    assert len(cs) == len(codes_for_season("INVERNO", False))
    assert cs[-1].code == 82   # il più misurato in fondo
    assert ordered_candidates({}, ctx(t_zg=23.6, t_zn=20.0)) == [] and propose({}, ctx(t_zg=23.6, t_zn=20.0)) is None


def test_write_off_blocks_first_manual_and_auto():
    c = ctx(write_on=False, acs_attivo=True)
    assert start_blockers(c, "HEAT", auto=False, tests_today=0, last_end=None)[0] == "write spenta"
    assert start_blockers(c, "HEAT", auto=True, tests_today=0, last_end=None)[0] == "write spenta"
    assert "write spenta" not in start_blockers(ctx(), "HEAT", auto=True, tests_today=0, last_end=None)


def test_v1_codes_never_proposed():
    from ecm_engine.rules import ordered_candidates
    for st in ("INVERNO", "ESTATE"):
        for night in (False, True):
            assert all(c % 10 < 7 for c in codes_for_season(st, night))
    stats = aggregate([Period(88, "HEAT", 0, 1, 20, 300.0, 0.0, 300.0, 1.0, 0.0, 1.0, 1.0, 8.0, False)] * 5)
    assert all(p.code % 10 < 7 for p in ordered_candidates(stats, ctx()))

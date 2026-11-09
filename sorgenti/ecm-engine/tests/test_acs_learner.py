from ecm_engine.acs_learner import learn_acs


def samples(code=74, rate=3, test=False):
    return [dict(ts=i*60, code=code, valido=1, stagione='INVERNO',
                 acs_source_ok=1, cp_compressore=1, motivo=None,
                 t11=45, t12=26+rate*i/60, p_cp=450, p_tosh=600,
                 acs_heat_test=int(test)) for i in range(41)]


def test_normal_and_test_are_both_learned():
    for flag in (False, True):
        rows = learn_acs(samples(test=flag))['tabella']
        assert len(rows) == 1
        assert rows[0]['resa_bollitore_basso_c_h'] == 3
        assert rows[0]['finestre_prova'] == (rows[0]['finestre'] if flag else 0)
        assert rows[0]['combinazione'] == 'CP HEAT V2 + SPLIT HEAT V1'


def test_draw_invalidates_window_and_restarts_settling():
    rows = samples()[:20]
    rows[15]['t12'] -= 4
    assert learn_acs(rows)['tabella'] == []


def test_unknown_or_resistance_never_learns():
    for field, value in [('acs_source_ok', None), ('acs_source_ok', 0),
                         ('motivo', 'resistenza ACS'), ('valido', 0)]:
        rows = samples()
        for row in rows:
            row[field] = value
        assert learn_acs(rows)['tabella'] == []


def test_gaps_and_combo_changes_do_not_bridge():
    rows = samples()[:17]
    rows += [dict(r, ts=r['ts']+2000, code=75) for r in samples()[:17]]
    assert learn_acs(rows)['tabella'] == []


def test_zero_and_negative_rates_are_preserved():
    for rate in (0, -1):
        assert learn_acs(samples(rate=rate))['tabella'][0]['resa_bollitore_basso_c_h'] == rate

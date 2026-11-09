from ecm_engine.acs_learner import learn_acs


def samples(code=74, rate=3, test=False, count=20, start=0):
    return [dict(ts=start+i*60, code=code, valido=1, stagione='INVERNO',
                 acs_source_ok=1, cp_compressore=1, motivo=None,
                 t11=45, t12=26+rate*(start/60+i)/60, p_cp=450, p_tosh=600,
                 acs_heat_test=int(test)) for i in range(count)]


def test_venti_campioni_danno_finestra_completa_dopo_cinque_di_avvio():
    for flag in (False, True):
        out = learn_acs(samples(test=flag))
        row = out['tabella'][0]
        assert row['resa_bollitore_basso_c_h'] == 3
        assert row['finestre'] == 1 and row['tratti_provvisori'] == 0
        assert row['finestre_prova'] == int(flag)
        assert row['combinazione'] == 'CP HEAT V2'
        assert row['split_contesto'] == 'SPLIT HEAT V1'
        assert out['assestamento_campioni'] == 5
        assert out['finestra_campioni'] == 15


def test_tratto_corto_resta_visibile_come_provvisorio():
    row = learn_acs(samples(count=16, test=True))['tabella'][0]
    assert row['resa_bollitore_basso_c_h'] == 3
    assert row['finestre'] == 0 and row['osservazioni'] == 1
    assert row['tratti_provvisori'] == 1 and row['provvisoria']
    assert row['minuti'] == 11 and row['supporto'] == 'provvisorio'


def test_prelievo_invalida_il_tratto_e_riparte_dall_avvio():
    rows = samples()
    rows[15]['t12'] -= 4
    assert learn_acs(rows)['tabella'] == []


def test_dati_invalidi_o_resistenza_non_vengono_appresi():
    for field, value in [('acs_source_ok', None), ('acs_source_ok', 0),
                         ('motivo', 'resistenza ACS'), ('valido', 0)]:
        rows = samples()
        for row in rows:
            row[field] = value
        assert learn_acs(rows)['tabella'] == []


def test_cambio_split_non_interrompe_acse_della_stessa_velocita():
    rows = samples(code=74, count=16)
    rows += samples(code=84, count=16, start=16*60)
    out = learn_acs(rows)['tabella']
    assert len(out) == 1
    assert out[0]['combinazione'] == 'CP HEAT V2'
    assert out[0]['finestre'] == 1 and out[0]['tratti_provvisori'] == 1
    assert out[0]['split_contesto'] == 'SPLIT HEAT V1 / SPLIT HEAT V2'


def test_cambio_velocita_crea_due_stime_provvisorie():
    rows = samples(code=74, count=16)
    rows += samples(code=75, count=16, start=16*60)
    out = learn_acs(rows)['tabella']
    assert [(r['codice'], r['provvisoria']) for r in out] == [
        ('ACSe V2', True), ('ACSe V3', True)]


def test_pendenze_nulle_e_negative_sono_conservate():
    for rate in (0, -1):
        assert learn_acs(samples(rate=rate))['tabella'][0]['resa_bollitore_basso_c_h'] == rate


def test_attributi_entro_il_limite_del_recorder():
    import json
    from ecm_engine.acs_learner import ATTR_MAX_BYTES

    rows, ts = [], 0
    for code in (4, 5, 6, 8):
        for band in range(0, 60, 5):
            for i in range(20):
                rows.append(dict(ts=ts, code=code, valido=1, stagione='INVERNO',
                                 acs_source_ok=1, cp_compressore=1, motivo=None,
                                 t11=45, t12=band + 1 + i * 0.01,
                                 p_cp=450, p_tosh=600, acs_heat_test=0))
                ts += 60
            ts += 3600
    out = learn_acs(rows)
    assert len(json.dumps(out, ensure_ascii=False).encode()) <= ATTR_MAX_BYTES
    assert out['righe_omesse'] > 0
    assert len(out['tabella']) + out['righe_omesse'] == 4 * 12
    keys = [(int(r['codice'].split('V')[1]),
             int(r['fascia_bollitore_basso'].split('–')[0])) for r in out['tabella']]
    assert keys == sorted(keys)


def test_tabella_piccola_intera():
    out = learn_acs(samples())
    assert out['righe_omesse'] == 0 and len(out['tabella']) == 1

from ecm_engine.segmenter import segment, slope_per_hour

def smp(ts, code=5, valido=1, t_zg=20.0, t_zn=20.0, p_cp=500.0, comp=1, test_id=None):
    return {"ts": ts, "code": code, "tipo": "HEAT", "valido": valido, "test_id": test_id,
            "cp_compressore": comp, "tosh_rps": 0.0, "p_cp": p_cp, "p_tosh": 10.0,
            "t_zg": t_zg, "t_zn": t_zn, "t_ext": 8.0}

def test_slope():
    assert abs(slope_per_hour([0, 3600], [20.0, 21.0]) - 1.0) < 1e-9

def test_settle_and_min_length():
    # 30 minuti a combinazione costante, temperatura +1 °C/h
    rows = [smp(60 * i, t_zg=20 + i / 60, t_zn=20 + i / 60) for i in range(31)]
    ps = segment(rows)
    assert len(ps) == 1
    p = ps[0]
    assert p.start == 300 and p.minutes == 26
    assert abs(p.slope_zg - 1.0) < 1e-6
    assert p.p_tot == 510.0 and p.duty_cp == 1.0

def test_too_short_ignored():
    rows = [smp(60 * i) for i in range(14)]  # 13 min -> 8 utili
    assert segment(rows) == []

def test_split_on_code_gap_invalid_and_test():
    a = [smp(60 * i) for i in range(20)]
    b = [smp(60 * i, code=6) for i in range(20, 40)]
    gap = [smp(60 * i, code=6) for i in range(44, 64)]          # buco di 4 minuti
    bad = [smp(60 * 64, code=6, valido=0)]
    t = [smp(60 * i, code=6, test_id=7) for i in range(65, 85)]
    ps = segment(a + b + gap + bad + t)
    assert [p.code for p in ps] == [5, 6, 6, 6]
    assert ps[-1].da_prova is True and ps[0].da_prova is False

def test_duty():
    rows = [smp(60 * i, comp=1 if i % 2 else 0) for i in range(31)]
    p = segment(rows)[0]
    assert 0.4 < p.duty_cp < 0.6

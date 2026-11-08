"""Temperatura esterna: affidabile solo dopo 10 minuti di ventilazione Compact."""
from ecm_engine.segmenter import fix_text


def _r(i, code, t):
    return {"ts": 60 * i, "code": code, "t_ext": t, "motivo": None}


def test_interpola_tra_due_letture_buone():
    rows = [_r(i, 1, 10.0) for i in range(12)]                 # ventila: dal minuto 10 buona
    rows += [_r(i, 0, 14.0) for i in range(12, 30)]            # ferma: aria stagnante
    rows += [_r(i, 1, 13.0 if i < 40 else 12.0) for i in range(30, 45)]  # riparte, buona dal 40
    out = list(fix_text(rows))
    assert [r["ts"] for r in out] == [r["ts"] for r in rows]
    assert out[11]["t_ext"] == 10.0 and "t_ext_stimata" not in out[11]
    assert out[0]["t_ext"] == 10.0                               # prima della prima buona: grezzo
    v = {r["ts"] // 60: r["t_ext"] for r in out}
    assert v[25] == round(10.0 + 2.0 * (25 - 11) / (40 - 11), 2)   # tra 10 (min 11) e 12 (min 40)
    assert all(out[i].get("t_ext_stimata") for i in range(12, 40))
    assert v[40] == 12.0


def test_senza_lettura_dopo_tiene_l_ultima_per_6_ore():
    rows = [_r(i, 1, 8.0) for i in range(11)] + [_r(i, 0, 15.0) for i in range(11, 11 + 400)]
    out = list(fix_text(rows))
    assert out[100]["t_ext"] == 8.0 and out[100]["t_ext_stimata"]
    assert out[-1]["t_ext"] == 15.0                              # oltre 6 ore: grezzo
    assert len(out) == len(rows)


def test_campione_non_valido_interrompe_la_ventilazione():
    rows = [_r(i, 1, 9.0) for i in range(5)] + [_r(5, None, 9.0)] + [_r(i, 1, 9.0) for i in range(6, 12)]
    out = list(fix_text(rows))
    assert all(r.get("t_ext_stimata") is None for r in out)      # nessuna buona: tutto grezzo

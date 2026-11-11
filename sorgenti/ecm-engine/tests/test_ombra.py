from datetime import datetime

from ecm_engine.decisore.ombra import Ombra, appresi_da, vel_toshiba
from ecm_engine.decisore.tipi import Stato
from ecm_engine.learner import Stat
from ecm_engine.power_learner import PowerStat
from ecm_engine.store import Store

T0 = int(datetime(2026, 11, 11, 11, 0).timestamp())   # giorno


class Pub:
    def __init__(self):
        self.states = {}

    def set_state(self, k, v, attrs=None):
        self.states[k] = (v, attrs)


SNAP = dict(stagione="INVERNO", manuale="AUTO", auto_10="on", t_min_inv=20.5, massimo_acc=23.5,
            mattina="08:30:00", serale="20:30:00", t_zg=21.2, t_zn=20.8, tosh_on="SPENTO",
            tosh_modo="RISCALDAMENTO", tosh_vent="MEDIA", soc=60.0, pv=0.0, load=500.0, imp=0.0,
            discharge=300.0, consenso_fv="off", rec_zg="off", rec_zn="off", accumulo_ha="off", p_tosh=10.0)


def mk(tmp_path):
    store, pub = Store(str(tmp_path / "e.db")), Pub()
    return Ombra(store, pub, T0), store, pub


def run(o, minutes, t_start=T0, **kw):
    out = None
    for i in range(minutes):
        out = o.passo(dict(SNAP, **kw), t_start + 60 * i, None, {}, {})
    return out


def test_vel_toshiba():
    assert vel_toshiba({"tosh_on": "SPENTO"}) == 0
    assert vel_toshiba({"tosh_on": "ACCESO", "tosh_modo": "RISCALDAMENTO", "tosh_vent": "ALTA"}) == 3
    assert vel_toshiba({"tosh_on": "ACCESO", "tosh_modo": "RAFFRESCAMENTO", "tosh_vent": "ALTA"}) is None
    assert vel_toshiba({"tosh_on": "unavailable"}) is None


def test_appresi_da_stats_e_power():
    st = {(80, "HEAT", "10-15"): Stat(80, "HEAT", "10-15", 5, 100, 900, 0, 1, .3, .3, .3, 3000.0, 1.0),
          (90, "HEAT", "10-15"): Stat(90, "HEAT", "10-15", 1, 30, 1270, 0, 1, .3, .3, .3, 2500.0, 0.2)}
    pw = {("INVERNO", "tosh", 8, "10-15"): PowerStat(910.0, 100, 4)}
    a = appresi_da(st, pw, "10-15")
    assert a.costo == {2: 3000.0}          # E90 poco affidabile: non entra nel ranking
    assert a.w == {2: 910.0}


def test_concorde_e_persistenza(tmp_path):
    o, store, pub = mk(tmp_path)
    r = run(o, 2)
    assert r["confronto"] == "concorde" and r["py_vel"] == 0 and r["ha_vel"] == 0
    assert pub.states["ombra_ambiente"][0] == "concorde"
    assert Stato.from_json(store.get_setting("decisore_stato", "")).seq == 2
    assert len(store.ombra_since(0)) == 2


def test_divergenza_solo_dopo_tre_cicli(tmp_path):
    o, _, _ = mk(tmp_path)
    # zona giorno 20.0 con latch HA di recupero: Python vuole accendere, Toshiba spento
    rows = [o.passo(dict(SNAP, t_zg=20.0, rec_zg="on"), T0 + 60 * i, None, {}, {}) for i in range(4)]
    assert [r["confronto"] for r in rows] == ["transitorio", "transitorio", "divergente", "divergente"]
    assert rows[-1]["fonte_stato"] == "ha" and rows[-1]["sotto_zg"] == 1


def test_non_confrontabile(tmp_path):
    o, _, _ = mk(tmp_path)
    assert run(o, 1, manuale="E80 - CP OFF V0 • HEAT V2")["confronto"] == "non confrontabile"
    assert run(o, 1, auto_10="off")["motivo_confronto"] == "10 non accesa"
    assert o.passo(dict(SNAP), T0, {"id": 1}, {}, {})["motivo_confronto"] == "prova in corso"
    assert run(o, 1, stagione="ESTATE")["confronto"] == "non confrontabile"


def test_media_dieci_minuti_e_trend(tmp_path):
    o, _, _ = mk(tmp_path)
    for i in range(61):
        o.passo(dict(SNAP, t_zg=20.0 + 0.01 * i), T0 + 60 * i, None, {}, {})
    c = o.ultimo_contesto
    assert abs(c.t_zg - 20.555) < 0.01            # media degli ultimi 10 minuti
    assert c.trend_zg[20] == 0.2 and c.trend_zg[60] > 0.5


def test_permanenza_dal_cambio_reale(tmp_path):
    o, _, _ = mk(tmp_path)
    run(o, 1)
    o.passo(dict(SNAP, tosh_on="ACCESO", tosh_vent="MEDIA"), T0 + 60, None, {}, {})
    assert o.ultimo_contesto.vel_reale == 2 and o.ultimo_contesto.vel_reale_dal == T0 + 60


def test_metriche(tmp_path):
    o, store, pub = mk(tmp_path)
    store.add_sample({"ts": T0, "p_tosh": 1200.0, "imp": 600.0, "valido": 1})
    run(o, 4, t_zg=20.0, rec_zg="on")
    m = o.metriche(T0 + 300)
    assert m["minuti_confrontabili"] == 4 and m["minuti_divergenti"] == 2
    assert m["minuti_sotto_soglia_zg"] == 4 and m["kwh_toshiba"] == 0.02 and m["kwh_rete"] == 0.01
    assert pub.states["ombra_metriche"][0] == 2


def test_t_ext_zero_vale(tmp_path):
    o, _, _ = mk(tmp_path)
    st = {(80, "HEAT", "<5"): Stat(80, "HEAT", "<5", 5, 100, 900, 0, 1, .3, .3, .3, 3000.0, 1.0)}
    o.passo(dict(SNAP, t_ext_aff=0.0, t_ext=12.0, t_zg=20.0, rec_zg="on"), T0, None, st, {})
    assert o.ultimo_piano.vel == 2

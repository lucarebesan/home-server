from ecm_engine.decisore.tipi import Appresi, Contesto, Risorsa, Stato
from ecm_engine.decisore import ambiente, energia
from ecm_engine.decisore.arbitro import decidi

T0 = 1_762_855_200  # istante fisso


def ctx(**kw):
    base = dict(ts=T0, notte=False, t_min=20.5, massimo=23.5, t_zg=21.2, t_zn=20.8,
                trend_zg={20: 0.1, 30: 0.1, 60: 0.1}, trend_zn={20: 0.1, 30: 0.1, 60: 0.1},
                vel_reale=0, vel_reale_dal=T0 - 3600, soc=60.0, pv=0.0, load=500.0, imp=0.0,
                consumo_base=500.0, discharge=300.0, charge=0.0, consenso_fv=False,
                prelievo_rete_stabile=False, ore_al_mattino=10.0, carico_notte_wh=4000.0,
                risorse_occupate=frozenset(), latch_ha=None)
    base.update(kw)
    return Contesto(**base)


NESSUNO = Appresi(costo={}, w={})


# ---------- soglie
def test_soglie_matrice():
    assert ambiente.soglie(20.5, notte=False) == {"zg": (20.5, 21.0), "zn": (20.0, 20.5)}
    assert ambiente.soglie(20.5, notte=True) == {"zg": (19.5, 20.0), "zn": (19.0, 19.5)}


def test_latch_recupero_si_accende_e_resta_fino_alla_fine():
    st, r, _ = ambiente.domanda(ctx(t_zg=20.4), Stato())
    assert st.rec_zg and r.servizio == "recupero" and r.zone == ("zg",)
    st, r, _ = ambiente.domanda(ctx(t_zg=20.8), st)          # sopra avvio, sotto fine
    assert st.rec_zg and r.servizio == "recupero"
    st, r, _ = ambiente.domanda(ctx(t_zg=21.0), st)          # raggiunta la fine
    assert not st.rec_zg and r is None


def test_zona_notte_di_notte_ha_soglie_sue():
    st, r, _ = ambiente.domanda(ctx(notte=True, t_zg=19.8, t_zn=19.1), Stato())
    assert not st.rec_zg and not st.rec_zn and r is None
    st, r, _ = ambiente.domanda(ctx(notte=True, t_zg=19.8, t_zn=18.9), Stato())
    assert st.rec_zn and r.zone == ("zn",)


def test_massimo_di_una_zona():
    st, richiesta, info = ambiente.domanda(ctx(t_zg=23.5, t_zn=20.0),
                                           Stato(rec_zg=True, rec_zn=True, accumulo=True))
    assert info["massimo"] and richiesta is None
    assert not st.rec_zg and not st.rec_zn and not st.accumulo


def test_accumulo_proposto_solo_senza_recupero():
    _, r, _ = ambiente.domanda(ctx(), Stato())
    assert r is None
    _, r, _ = ambiente.domanda(ctx(), Stato(), accumulo_possibile=True)
    assert r.servizio == "accumulo" and r.livello > ambiente.LIVELLO_RECUPERO


# ---------- energia
def test_energia_giorno_avvio_usa_consenso():
    ok, _ = energia.giudica(ctx(consenso_fv=True), 2, 900, accumulo_attivo=False)
    assert ok
    ok, motivo = energia.giudica(ctx(consenso_fv=False), 2, 900, accumulo_attivo=False)
    assert not ok and "consenso" in motivo


def test_energia_giorno_continuazione_ferma_su_rete():
    ok, _ = energia.giudica(ctx(imp=50, discharge=0, pv=600), 2, 900, accumulo_attivo=True)
    assert ok
    ok, motivo = energia.giudica(ctx(imp=301, discharge=0, pv=600), 2, 900, accumulo_attivo=True)
    assert not ok and "rete" in motivo


def test_energia_giorno_usa_soglie_e_consensi_della_10():
    ok, _ = energia.giudica(ctx(consenso_fv=True), 2, 1100, accumulo_attivo=False)
    assert ok
    ok, motivo = energia.giudica(ctx(consenso_fv=True, prelievo_rete_stabile=True),
                                 2, 1100, accumulo_attivo=False)
    assert not ok and "consenso" in motivo
    ok, motivo = energia.giudica(ctx(imp=300, discharge=251, pv=600), 2, 1100, accumulo_attivo=True)
    assert not ok and "scarica" in motivo


def test_energia_notte_soc_previsto():
    # 60% di 20 kWh = 12 kWh; base 4 kWh + 900 W x 10 h = 13 kWh -> sotto riserva
    ok, motivo = energia.giudica(ctx(notte=True), 2, 900, accumulo_attivo=False)
    assert not ok and "SOC" in motivo
    ok, _ = energia.giudica(ctx(notte=True, soc=100.0, ore_al_mattino=5.0), 2, 900, accumulo_attivo=False)
    assert ok


def test_energia_notte_blocca_rete_e_dati_incompleti():
    ok, motivo = energia.giudica(ctx(notte=True, soc=100.0, ore_al_mattino=1.0, imp=301),
                                 2, 1100, accumulo_attivo=False)
    assert not ok and "rete" in motivo
    ok, motivo = energia.giudica(ctx(notte=True, soc=100.0, ore_al_mattino=1.0, charge=None),
                                 2, 1100, accumulo_attivo=False)
    assert not ok and "mancanti" in motivo


def test_profilo_carico_mediana_per_ora():
    p = energia.ProfiloCarico()
    for i, load in enumerate((400, 500, 600)):
        p.feed({"ts": T0 + i * 86400, "load": load})
    prof = p.result()
    assert len(prof) == 1 and list(prof.values()) == [500]


# ---------- arbitro
def test_comfort_spento():
    p = decidi(ctx(), NESSUNO, Stato())
    assert p.vel == 0 and p.richiesta is None


def test_recupero_usa_ripiego_giorno_v3_e_notte_v2():
    assert decidi(ctx(t_zg=20.3), NESSUNO, Stato()).vel == 3
    assert decidi(ctx(notte=True, t_zn=18.8), NESSUNO, Stato()).vel == 2


def test_recupero_sceglie_la_piu_economica_appresa():
    a = Appresi(costo={1: 3000.0, 2: 2500.0, 3: 3300.0}, w={1: 700, 2: 950, 3: 1270})
    p = decidi(ctx(t_zg=20.3), a, Stato())
    assert p.vel == 2 and p.code == 80


def test_migliore_caldo_prevale_anche_se_da_confermare():
    a = Appresi(costo={2: 2000.0}, w={}, preferita=1)
    assert decidi(ctx(t_zg=20.3), a, Stato()).vel == 1


def test_recupero_prevale_sul_budget():
    p = decidi(ctx(t_zg=20.3, soc=5.0, notte=True, t_zn=18.5), NESSUNO, Stato())
    assert p.vel == 2


def test_notte_mai_oltre_v2():
    a = Appresi(costo={3: 1000.0}, w={})
    p = decidi(ctx(notte=True, t_zn=18.8), a, Stato())
    assert p.vel <= 2 and "V2" in p.scartati[3]


def test_permanenza_minima_dallo_stato_reale():
    # Toshiba acceso da 5 minuti, recupero finito: resta acceso
    p = decidi(ctx(vel_reale=2, vel_reale_dal=T0 - 300), NESSUNO, Stato())
    assert p.vel == 2 and "permanenza" in p.scartati[0]
    p = decidi(ctx(vel_reale=2, vel_reale_dal=T0 - 1000), NESSUNO, Stato())
    assert p.vel == 0


def test_massimo_ferma_anche_in_permanenza():
    p = decidi(ctx(t_zg=23.6, vel_reale=2, vel_reale_dal=T0 - 60), NESSUNO, Stato())
    assert p.vel == 0


def test_trend_insufficienti_fanno_salire_di_una():
    a = Appresi(costo={1: 2000.0}, w={})
    st = Stato(rec_zg=True)
    fermo = {20: 0.0, 30: -0.1, 60: 0.2}
    p = decidi(ctx(t_zg=20.6, vel_reale=1, vel_reale_dal=T0 - 1200, trend_zg=fermo), a, st)
    assert p.vel == 2
    p = decidi(ctx(t_zg=20.6, vel_reale=1, vel_reale_dal=T0 - 1200), a, st)
    assert p.vel == 1


def test_trend_incompleti_non_fanno_salire():
    a = Appresi(costo={1: 2000.0}, w={})
    st = Stato(rec_zg=True)
    incompleti = {20: 0.0, 30: -0.1, 60: None}
    p = decidi(ctx(t_zg=20.6, vel_reale=1, vel_reale_dal=T0 - 1200,
                   trend_zg=incompleti), a, st)
    assert p.vel == 1


def test_accumulo_richiede_energia():
    p = decidi(ctx(consenso_fv=False), NESSUNO, Stato())
    assert p.vel == 0
    p = decidi(ctx(consenso_fv=True), NESSUNO, Stato())
    assert p.vel > 0 and p.richiesta.servizio == "accumulo" and p.stato.accumulo


def test_accumulo_puo_partire_senza_margine_sotto_il_massimo():
    p = decidi(ctx(consenso_fv=True, t_zg=23.49, t_zn=23.49), NESSUNO, Stato())
    assert p.richiesta.servizio == "accumulo" and p.vel > 0


def test_accumulo_si_ferma_al_massimo():
    p = decidi(ctx(consenso_fv=True, t_zg=23.5, vel_reale=2, vel_reale_dal=T0 - 3600),
               NESSUNO, Stato(accumulo=True))
    assert p.vel == 0 and not p.stato.accumulo


def test_parita_di_stato_usa_latch_ha():
    p = decidi(ctx(t_zg=20.8, latch_ha={"rec_zg": True, "rec_zn": False, "accumulo": False}),
               NESSUNO, Stato())
    assert p.fonte_stato == "ha" and p.vel > 0
    p = decidi(ctx(t_zg=20.8), NESSUNO, Stato())
    assert p.fonte_stato == "proprio" and p.vel == 0


def test_dati_critici_non_validi_nessun_cambio():
    p = decidi(ctx(t_zg=None, vel_reale=2), NESSUNO, Stato(rec_zg=True))
    assert p.vel == 2 and "non validi" in p.motivo and p.stato.rec_zg


def test_risorsa_occupata_scarta():
    p = decidi(ctx(t_zg=20.0, risorse_occupate=frozenset({Risorsa.TOSHIBA})), NESSUNO, Stato())
    assert p.vel == 0 and p.rinviate == ("recupero",)


def test_piano_ha_sequenza_e_lease():
    p = decidi(ctx(), NESSUNO, Stato(seq=41))
    assert p.seq == 42 and p.stato.seq == 42 and p.valido_fino > p.emesso == T0


def test_stato_json_versionato():
    s = Stato(rec_zg=True, seq=3, vel_dal=T0, ultimo_vel=2)
    assert Stato.from_json(s.to_json()) == s
    assert Stato.from_json('{"versione": 999}') == Stato()
    assert Stato.from_json("rotto") == Stato()


def test_limite_notturno_prevale_sulla_permanenza():
    p = decidi(ctx(notte=True, t_zn=18.8, vel_reale=3, vel_reale_dal=T0 - 120), NESSUNO, Stato())
    assert p.vel == 2

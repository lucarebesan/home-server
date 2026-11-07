from datetime import datetime
from ecm_engine.engine import Engine, build_sample
from ecm_engine.store import Store

SNAP = {"stagione": "INVERNO", "free_cooling": "DISATTIVATO", "manuale": "AUTO",
        "durata_manuale": None, "lim_inf": 20.0, "lim_sup": 21.7, "commutazione": 22.5,
        "isteresi_comm": 2.0, "mattina": "08:30:00",
        "serale": "22:00:00", "acs_inv": "off", "acs_soc": "off", "cp_modo": "RISCALDAMENTO",
        "cp_compressore": "OFF", "cp_vent": "STEP 2", "cp_stato": "VENTILAZIONE",
        "cp_resistenza": "OFF", "tosh_on": "SPENTO", "tosh_modo": "RISCALDAMENTO",
        "tosh_vent": "MEDIA", "tosh_rps": 0.0, "p_cp": 30.0, "p_tosh": 9.0, "t_zg": 21.0,
        "t_zn": 20.8, "t10": 21.0, "t2": 19.0, "t_ext": 8.0, "soc": 60.0, "pv": 0.0,
        "load": 800.0, "imp": 0.0, "discharge": 800.0, "charge": 0.0}


class FakeApi:
    def __init__(self):
        self.snap = dict(SNAP)
        self.calls = []

    def snapshot(self, entities, numeric):
        return dict(self.snap)

    def call_service(self, d, s, data):
        self.calls.append((d, s, data))


class FakePub:
    def __init__(self):
        self.states = {}

    def set_state(self, k, v, attrs=None):
        self.states[k] = (v, attrs)


def mk(tmp_path, t):
    api, pub = FakeApi(), FakePub()
    clock = {"t": t}
    e = Engine(api, Store(str(tmp_path / "e.db")), pub, clock=lambda: clock["t"])
    return e, api, pub, clock


T0 = datetime(2026, 11, 8, 11, 0).timestamp()


def test_build_sample_valid_and_invalid():
    s = build_sample(SNAP, 100, None)
    assert s["code"] == 1 and s["valido"] == 1 and s["tipo"] == "NEUTRO"
    bad = dict(SNAP, p_cp=None)
    s2 = build_sample(bad, 100, None)
    assert s2["valido"] == 0 and s2["motivo"] == "dato mancante p_cp"


def test_build_sample_during_test_uses_test_code():
    snap = dict(SNAP, cp_compressore="ON", tosh_on="ACCESO", cp_vent="STEP 2")
    s = build_sample(snap, 100, {"id": 3, "code": 84})
    assert s["code"] == 84 and s["test_id"] == 3 and s["valido"] == 1
    s2 = build_sample(dict(SNAP), 100, {"id": 3, "code": 84})  # toshiba spento: non ancora applicata
    assert s2["valido"] == 0 and s2["motivo"] == "prova non ancora applicata"


def test_tick_sample_stores(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample()
    assert len(e.store.samples_since(0)) == 1


def test_tick_sample_ha_down(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    api.snapshot = lambda *a: (_ for _ in ()).throw(OSError("conn refused"))
    e.tick_sample()
    assert pub.states["stato"][0] == "errore HA"
    assert e.store.samples_since(0) == []


def test_soglia_estate_from_snapshot(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample()
    assert e._ctx().soglia_estate == 24.5
    api.snap.update(commutazione=None)
    e.tick_sample()
    assert e._ctx().soglia_estate == 24.5
    api.snap.update(commutazione=23.0, isteresi_comm=1.0)
    e.tick_sample()
    assert e._ctx().soglia_estate == 24.0


def test_manual_button_starts_test(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    assert api.calls[0][0:2] == ("input_number", "set_value")
    assert api.calls[0][2]["value"] == 30
    assert api.calls[1][2]["option"] == "E4 - CP ON V2 • Split OFF"
    assert e.store.open_test()["origine"] == "manuale"


def test_durata_failure_does_not_block_start(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    orig = api.call_service

    def cs(d, s, data):
        if d == "input_number":
            raise OSError("400 entity not found")
        orig(d, s, data)
    api.call_service = cs
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    assert api.calls[0][2]["option"].startswith("E4 ")
    assert e.store.open_test() is not None


def test_abort_and_completion(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    label = api.calls[1][2]["option"]
    api.snap["manuale"] = label
    api.snap["t_zg"] = 21.9            # sopra lim_sup: d'inverno non interrompe più
    clock["t"] += 60; e.tick_sample()
    assert e.store.open_test() is not None
    api.snap["t_zg"] = 24.1            # vicina al cambio stagione (24.5 - 0.5) -> interrompe
    clock["t"] += 60; e.tick_sample()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.open_test() is None
    assert e.store.tests_since(0)[0]["esito"] == "zona vicina al cambio stagione"


def test_user_interrupt_does_not_reselect(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    n = len(api.calls)
    api.snap["manuale"] = "AUTO"       # utente o 09 a fine durata prima del tempo
    clock["t"] += 120; e.tick_sample()
    assert len(api.calls) == n
    assert e.store.tests_since(0)[0]["esito"] == "interrotta dall'utente"


def test_completed_after_duration(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    api.snap["manuale"] = api.calls[1][2]["option"]
    clock["t"] += 60; e.tick_sample()
    api.snap["manuale"] = "AUTO"
    clock["t"] += 30 * 60; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "completata"


def test_switch_persists_and_auto_start(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.on_command("ecm_engine/prove_automatiche/set", "ON")
    assert e.store.get_setting("auto", "0") == "1"
    assert pub.states["prove_automatiche"][0] == "ON"
    e.tick_sample(); e.tick_learn(); e.tick_sample()
    assert e.store.open_test()["origine"] == "auto"


def test_no_auto_start_when_switch_off(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn(); e.tick_sample()
    assert e.store.open_test() is None


def test_publish_after_learn(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    for k in ("stato", "in_breve", "migliore_caldo", "migliore_freddo", "apprendimento_caldo",
              "apprendimento_freddo", "prova_proposta", "prova_in_corso", "dettaglio", "avvisi"):
        assert k in pub.states, k
    assert pub.states["stato"][0] == "online"
    assert pub.states["prova_proposta"][1]["avviabile"] is True
    assert pub.states["prova_proposta"][1]["codice"] == "E4"


def test_proposal_blocked_low_battery(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    api.snap["soc"] = 19.0
    e.tick_sample(); e.tick_learn()
    attrs = pub.states["prova_proposta"][1]
    assert attrs["avviabile"] is False and attrs["motivo_blocco"] == "energia insufficiente"


def test_recover_closes_open_test(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    api.snap["manuale"] = api.calls[1][2]["option"]
    e2 = Engine(api, e.store, pub, clock=lambda: clock["t"] + 60)
    e2.recover()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.tests_since(0)[0]["esito"] == "interrotta dal riavvio del motore"


# ---------- supervisione robusta
def _started(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    e.on_command("ecm_engine/avvia_prova/cmd", "PRESS")
    label = api.calls[1][2]["option"]
    api.snap["manuale"] = label
    clock["t"] += 60; e.tick_sample()
    assert e.store.open_test() is not None
    return e, api, pub, clock, label


def test_completed_even_without_ctx(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap.update(manuale="AUTO", lim_sup=None)      # ctx incompleto
    clock["t"] += 30 * 60; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "completata"


def test_user_interrupt_without_ctx(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    n = len(api.calls)
    api.snap.update(manuale="AUTO", t_zg=None)
    clock["t"] += 60; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "interrotta dall'utente"
    assert len(api.calls) == n


def test_other_option_is_user_interrupt_without_auto(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    n = len(api.calls)
    api.snap["manuale"] = "E5 - CP ON V3 • Split OFF"
    clock["t"] += 60; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "interrotta dall'utente"
    assert len(api.calls) == n


def test_unavailable_manuale_concludes_nothing_briefly(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    n = len(api.calls)
    for v in ("unavailable", "unknown", None):
        api.snap["manuale"] = v
        clock["t"] += 60; e.tick_sample()
    assert e.store.open_test() is not None
    assert len(api.calls) == n


def test_unknown_manuale_over_5_minutes_selects_auto(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap["manuale"] = "unavailable"
    for _ in range(6):                                # 0..300 s: ancora aperta
        clock["t"] += 60 if _ else 0
        e.tick_sample()
        assert e.store.open_test() is not None
    clock["t"] += 60; e.tick_sample()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.tests_since(0)[0]["esito"] == "stato manuale sconosciuto"


def test_unknown_manuale_auto_failure_keeps_open(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap["manuale"] = None
    e.tick_sample()
    api.call_service = lambda *a: (_ for _ in ()).throw(OSError("HA 500"))
    clock["t"] += 400; e.tick_sample()
    assert e.store.open_test() is not None


def test_unknown_manuale_overrun_selects_auto(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap["manuale"] = "unknown"
    clock["t"] = e.store.open_test()["inizio"] + 30 * 60 + 181
    e.tick_sample()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.open_test() is None


def test_missing_data_with_other_option_does_not_touch_09(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    n = len(api.calls)
    api.snap.update(manuale="E5 - CP ON V3 • Split OFF", t_zg=None)
    e.tick_sample()
    clock["t"] += 400; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "dati mancanti"
    assert len(api.calls) == n


def test_missing_data_for_5_minutes_selects_auto(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap["t_zg"] = None
    for _ in range(6):                                # 0..300 s: ancora aperta
        clock["t"] += 60 if _ else 0
        e.tick_sample()
        assert e.store.open_test() is not None
    clock["t"] += 60; e.tick_sample()                 # 360 s > 5 minuti
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.tests_since(0)[0]["esito"] == "dati mancanti"


def test_missing_data_timer_resets(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.snap["t_zg"] = None
    for _ in range(4):
        clock["t"] += 60; e.tick_sample()
    api.snap["t_zg"] = 21.0
    clock["t"] += 60; e.tick_sample()
    api.snap["t_zg"] = None
    for _ in range(4):
        clock["t"] += 60; e.tick_sample()
    assert e.store.open_test() is not None


def test_overrun_selects_auto(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    clock["t"] = e.store.open_test()["inizio"] + 30 * 60 + 180
    e.tick_sample()
    assert e.store.open_test() is not None
    clock["t"] += 60; e.tick_sample()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.tests_since(0)[0]["esito"] == "durata superata"


def test_auto_select_failure_keeps_test_open(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    api.call_service = lambda *a: (_ for _ in ()).throw(OSError("HA 500"))
    api.snap["t_zg"] = 24.1
    clock["t"] += 60; e.tick_sample()
    assert e.store.open_test() is not None            # riprova al prossimo minuto


def _recovering(tmp_path):
    e, api, pub, clock, label = _started(tmp_path)
    clock["t"] += 60
    e2 = Engine(api, e.store, pub, clock=lambda: clock["t"])
    return e2, api, pub, clock, label


def test_recover_snapshot_failure_leaves_open(tmp_path):
    e2, api, pub, clock, label = _recovering(tmp_path)
    good = api.snapshot
    api.snapshot = lambda *a: (_ for _ in ()).throw(OSError("conn refused"))
    e2.recover()
    assert e2.store.open_test() is not None
    api.snapshot = good
    n = len(api.calls)
    clock["t"] += 60; e2.tick_sample()                # la supervisione riprova
    assert api.calls[n][2]["option"] == "AUTO"
    assert e2.store.tests_since(0)[0]["esito"] == "interrotta dal riavvio del motore"


def test_recover_unavailable_leaves_open(tmp_path):
    e2, api, pub, clock, label = _recovering(tmp_path)
    api.snap["manuale"] = "unavailable"
    e2.recover()
    assert e2.store.open_test() is not None
    api.snap["manuale"] = "AUTO"
    clock["t"] += 60; e2.tick_sample()
    assert e2.store.tests_since(0)[0]["esito"] == "interrotta dal riavvio del motore"


def test_recover_call_failure_leaves_open(tmp_path):
    e2, api, pub, clock, label = _recovering(tmp_path)
    orig = api.call_service
    api.call_service = lambda *a: (_ for _ in ()).throw(OSError("HA 500"))
    e2.recover()
    assert e2.store.open_test() is not None
    api.call_service = orig
    clock["t"] += 60; e2.tick_sample()
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e2.store.tests_since(0)[0]["esito"] == "interrotta dal riavvio del motore"


def test_recover_when_already_auto_does_not_call(tmp_path):
    e2, api, pub, clock, label = _recovering(tmp_path)
    api.snap["manuale"] = "AUTO"
    n = len(api.calls)
    e2.recover()
    assert len(api.calls) == n
    assert e2.store.tests_since(0)[0]["esito"] == "interrotta dal riavvio del motore"


# ---------- avvio protetto
def _fail_select(api, option_prefix="E"):
    orig = api.call_service

    def cs(d, s, data):
        if s == "select_option" and data["option"].startswith(option_prefix):
            raise OSError("HA 500")
        orig(d, s, data)
    api.call_service = cs


def test_select_failure_rolls_back(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    _fail_select(api)
    err = e.start_test("manuale")
    assert err and err.startswith("avvio fallito")
    assert api.calls[-1][2]["option"] == "AUTO"
    assert e.store.open_test() is None
    assert e.store.tests_since(0)[0]["esito"] == "avvio fallito"
    assert e.auto_block_until == T0 + 900


def test_select_failure_with_auto_failure_leaves_row_open(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    api.call_service = lambda *a: (_ for _ in ()).throw(OSError("HA giù"))
    err = e.start_test("manuale")
    assert err.startswith("avvio fallito")
    assert e.store.open_test() is not None
    assert e.auto_block_until == T0 + 900


def test_test_row_written_before_select(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    seen = []
    orig = api.call_service

    def cs(d, s, data):
        if s == "select_option":
            seen.append(e.store.open_test())
        orig(d, s, data)
    api.call_service = cs
    assert e.start_test("manuale") is None
    assert seen[0] is not None


def test_auto_start_respects_block(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.store.set_setting("auto", "1")
    e.auto_block_until = T0 + 900
    e.tick_sample(); e.tick_learn(); e.tick_sample()
    assert e.store.open_test() is None
    clock["t"] = T0 + 901
    # la pausa tra le prove non c'è: nessuna prova chiusa prima
    e.tick_sample()
    assert e.store.open_test()["origine"] == "auto"


def test_stale_snapshot_refuses_start(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    clock["t"] += 121
    assert e.start_test("manuale") == "dati non aggiornati"
    assert api.calls == []


def test_exception_after_snapshot_still_publishes(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample()
    pub.states.clear()

    def boom():
        raise RuntimeError("bug")
    e._supervise = boom
    try:
        e.tick_sample()
    except RuntimeError:
        pass
    assert "stato" in pub.states


# ---------- apprendimento fuori dal lock
def test_tick_learn_segments_outside_lock(tmp_path, monkeypatch):
    import threading
    import ecm_engine.engine as eng
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample()
    free = []
    real = eng.segment

    def spy(rows):
        def probe():
            ok = e.lock.acquire(blocking=False)
            free.append(ok)
            if ok:
                e.lock.release()
        th = threading.Thread(target=probe)
        th.start(); th.join()
        return real(rows)
    monkeypatch.setattr(eng, "segment", spy)
    e.tick_learn()
    assert free == [True]
    assert "in_breve" in pub.states


def test_migliore_attributes_published(tmp_path):
    e, api, pub, clock = mk(tmp_path, T0)
    e.tick_sample(); e.tick_learn()
    assert pub.states["migliore_caldo"][1] == {}
    assert pub.states["migliore_freddo"][1] == {}


def test_proposal_error_does_not_skip_supervision(tmp_path, monkeypatch):
    import ecm_engine.engine as eng
    e, api, pub, clock, label = _started(tmp_path)
    monkeypatch.setattr(eng, "propose", lambda *a: (_ for _ in ()).throw(ValueError("bug")))
    api.snap["t_zg"] = 24.1
    clock["t"] += 60; e.tick_sample()
    assert e.store.tests_since(0)[0]["esito"] == "zona vicina al cambio stagione"

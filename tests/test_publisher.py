import json
from ecm_engine.publisher import AVAIL, button_config, sensor_config, switch_config


def test_sensor_config():
    topic, payload = sensor_config("in_breve", "In breve", "mdi:text")
    p = json.loads(payload)
    assert topic == "homeassistant/sensor/ecm_engine/in_breve/config"
    assert p["unique_id"] == "ecm_engine_in_breve"
    assert p["default_entity_id"] == "sensor.ecm_engine_in_breve"
    assert p["state_topic"] == "ecm_engine/in_breve/state"
    assert p["json_attributes_topic"] == "ecm_engine/in_breve/attr"
    assert p["availability_topic"] == AVAIL
    assert p["device"]["identifiers"] == ["ecm_engine"]


def test_sensor_unit():
    p = json.loads(sensor_config("apprendimento_caldo", "x", "mdi:school", unit="%")[1])
    assert p["unit_of_measurement"] == "%"


def test_button_and_switch():
    t, p = button_config("avvia_prova", "Avvia prova proposta", "mdi:play")
    assert t == "homeassistant/button/ecm_engine/avvia_prova/config"
    assert json.loads(p)["command_topic"] == "ecm_engine/avvia_prova/cmd"
    t, p = switch_config("prove_automatiche", "Prove automatiche", "mdi:robot")
    p = json.loads(p)
    assert p["command_topic"] == "ecm_engine/prove_automatiche/set"
    assert p["state_topic"] == "ecm_engine/prove_automatiche/state"


def test_main_importable():
    import ecm_engine.__main__ as m
    assert callable(m.main)


def test_failing_learn_does_not_rerun_every_minute():
    import ecm_engine.__main__ as m

    class E:
        def __init__(self):
            self.learns = 0
            self.samples = 0

        def tick_sample(self):
            self.samples += 1

        def tick_learn(self):
            self.learns += 1
            raise RuntimeError("bug")
    e = E()
    nl = 0.0
    for i in range(5):
        nl = m.cycle(e, 1000.0 + 60 * i, nl)
    assert e.learns == 1 and e.samples == 5


class _RC:
    def __init__(self, fail=False):
        self.is_failure = fail


class _FakeClient:
    def __init__(self, *a, **kw):
        self.pubs = []
        self.subs = []

    def username_pw_set(self, *a): pass
    def will_set(self, *a, **kw): pass
    def connect_async(self, *a, **kw): pass
    def loop_start(self): pass

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.pubs.append((topic, payload, qos, retain))

    def subscribe(self, t): self.subs.append(t)


def _pub(monkeypatch, on_command=None):
    import ecm_engine.publisher as P
    monkeypatch.setattr(P.mqtt, "Client", _FakeClient)
    return P.Publisher("h", 1883, on_command=on_command)


def test_states_qos1_and_republished_on_reconnect(monkeypatch):
    p = _pub(monkeypatch)
    p.set_state("stato", "online")
    p.set_state("avvisi", 0, {"elenco": []})
    p.set_state("avvisi", 1)                       # attributi invariati restano in cache
    assert ("ecm_engine/stato/state", "online", 1, True) in p.c.pubs
    fresh = _FakeClient()
    p._on_connect(fresh, None, None, _RC())
    topics = {t: (pl, q) for t, pl, q, r in fresh.pubs}
    assert "homeassistant/sensor/ecm_engine/stato/config" in topics
    assert topics["ecm_engine/stato/state"] == ("online", 1)
    assert topics["ecm_engine/avvisi/state"] == ("1", 1)
    assert json.loads(topics["ecm_engine/avvisi/attr"][0]) == {"elenco": []}


def test_callbacks_do_not_raise(monkeypatch):
    def boom(t, p):
        raise RuntimeError("x")
    p = _pub(monkeypatch, on_command=boom)

    class Bad(_FakeClient):
        def publish(self, *a, **kw):
            raise OSError("socket")
    p._on_connect(Bad(), None, None, _RC())        # non deve sollevare

    class Msg:
        topic = "ecm_engine/avvia_prova/cmd"
        payload = b"\xff\xfe"                      # decode fallisce
    p._on_message(p.c, None, Msg())

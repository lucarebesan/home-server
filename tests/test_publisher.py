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

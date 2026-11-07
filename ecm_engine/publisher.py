"""Entità MQTT con discovery automatica per Home Assistant."""
import json
import logging

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)
AVAIL = "ecm_engine/availability"
DEVICE = {"identifiers": ["ecm_engine"], "name": "ECM Engine", "model": "fase 1", "manufacturer": "Misc"}

SENSORS = [
    ("stato", "Stato motore", "mdi:engine", None),
    ("in_breve", "In breve", "mdi:text", None),
    ("migliore_caldo", "Migliore per scaldare", "mdi:fire", None),
    ("migliore_freddo", "Migliore per raffrescare", "mdi:snowflake", None),
    ("apprendimento_caldo", "Apprendimento caldo", "mdi:school", "%"),
    ("apprendimento_freddo", "Apprendimento freddo", "mdi:school", "%"),
    ("prova_proposta", "Prova proposta", "mdi:flask-outline", None),
    ("prova_in_corso", "Prova in corso", "mdi:flask", None),
    ("dettaglio", "Dettaglio combinazioni", "mdi:table", None),
    ("avvisi", "Avvisi", "mdi:alert", None),
]


def _base(kind, key, name, icon):
    return {"name": name, "unique_id": f"ecm_engine_{key}", "default_entity_id": f"{kind}.ecm_engine_{key}",
            "icon": icon, "availability_topic": AVAIL, "device": DEVICE}


def sensor_config(key, name, icon, unit=None):
    p = _base("sensor", key, name, icon)
    p.update(state_topic=f"ecm_engine/{key}/state", json_attributes_topic=f"ecm_engine/{key}/attr")
    if unit:
        p["unit_of_measurement"] = unit
    return f"homeassistant/sensor/ecm_engine/{key}/config", json.dumps(p)


def button_config(key, name, icon):
    p = _base("button", key, name, icon)
    p["command_topic"] = f"ecm_engine/{key}/cmd"
    return f"homeassistant/button/ecm_engine/{key}/config", json.dumps(p)


def switch_config(key, name, icon):
    p = _base("switch", key, name, icon)
    p.update(command_topic=f"ecm_engine/{key}/set", state_topic=f"ecm_engine/{key}/state")
    return f"homeassistant/switch/ecm_engine/{key}/config", json.dumps(p)


class Publisher:
    def __init__(self, host, port, user=None, password=None, on_command=None):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ecm_engine")
        if user:
            self.c.username_pw_set(user, password)
        self.c.will_set(AVAIL, "offline", retain=True)
        self.on_command = on_command
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.connect_async(host, port, keepalive=60)
        self.c.loop_start()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        log.info("MQTT connesso rc=%s", rc)
        if rc.is_failure:
            return
        for key, name, icon, unit in SENSORS:
            client.publish(*sensor_config(key, name, icon, unit), retain=True)
        client.publish(*button_config("avvia_prova", "Avvia prova proposta", "mdi:play"), retain=True)
        client.publish(*switch_config("prove_automatiche", "Prove automatiche", "mdi:robot"), retain=True)
        client.publish(AVAIL, "online", retain=True)
        client.subscribe("ecm_engine/+/cmd")
        client.subscribe("ecm_engine/+/set")

    def _on_message(self, client, userdata, msg):
        if self.on_command:
            try:
                self.on_command(msg.topic, msg.payload.decode())
            except Exception:
                log.exception("errore nel comando %s", msg.topic)

    def set_state(self, key: str, state, attrs: dict | None = None) -> None:
        self.c.publish(f"ecm_engine/{key}/state", str(state)[:255], retain=True)
        if attrs is not None:
            self.c.publish(f"ecm_engine/{key}/attr", json.dumps(attrs, ensure_ascii=False), retain=True)

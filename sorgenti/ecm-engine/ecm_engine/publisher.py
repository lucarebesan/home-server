"""Entità MQTT con discovery automatica per Home Assistant."""
import json
import logging
import threading

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)
AVAIL = "ecm_engine/availability"
DEVICE = {"identifiers": ["ecm_engine"], "name": "ECM Engine", "model": "fase 1", "manufacturer": "Misc"}

SENSORS = [
    ("resa_acs", "Resa ACS per combinazione", "mdi:water-thermometer", None),
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
    ("ultime_prove", "Ultime prove", "mdi:history", None),
    ("da_misurare", "Da misurare", "mdi:format-list-numbered", None),
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


def binary_sensor_config(key, name, icon):
    p = _base("binary_sensor", key, name, icon)
    p.update(state_topic=f"ecm_engine/{key}/state", payload_on="ON", payload_off="OFF")
    return f"homeassistant/binary_sensor/ecm_engine/{key}/config", json.dumps(p)


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
        self._lock = threading.Lock()
        self._states: dict[str, str] = {}    # ultimo stato per chiave, ripubblicato alla riconnessione
        self._attrs: dict[str, str] = {}
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.connect_async(host, port, keepalive=60)
        self.c.loop_start()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        try:
            log.info("MQTT connesso rc=%s", rc)
            if rc.is_failure:
                return
            for key, name, icon, unit in SENSORS:
                client.publish(*sensor_config(key, name, icon, unit), retain=True)
            client.publish(*binary_sensor_config("prova_avviabile", "Prova avviabile", "mdi:play-circle-outline"),
                           retain=True)
            client.publish(*button_config("avvia_prova", "Avvia prova proposta", "mdi:play"), retain=True)
            client.publish(*switch_config("prove_automatiche", "Prove automatiche", "mdi:robot"), retain=True)
            with self._lock:   # stesso lock di set_state: una cache vecchia non sovrascrive un valore nuovo
                for key, v in self._states.items():
                    client.publish(f"ecm_engine/{key}/state", v, qos=1, retain=True)
                for key, v in self._attrs.items():
                    client.publish(f"ecm_engine/{key}/attr", v, qos=1, retain=True)
            client.publish(AVAIL, "online", qos=1, retain=True)
            client.subscribe("ecm_engine/+/cmd")
            client.subscribe("ecm_engine/+/set")
        except Exception:
            log.exception("errore in on_connect")

    def _on_message(self, client, userdata, msg):
        try:
            if self.on_command:
                self.on_command(msg.topic, msg.payload.decode())
        except Exception:
            log.exception("errore nel comando %s", getattr(msg, "topic", "?"))

    def set_state(self, key: str, state, attrs: dict | None = None) -> None:
        v = str(state)[:255]
        a = json.dumps(attrs, ensure_ascii=False) if attrs is not None else None
        with self._lock:
            self._states[key] = v
            if a is not None:
                self._attrs[key] = a
            self.c.publish(f"ecm_engine/{key}/state", v, qos=1, retain=True)
            if a is not None:
                self.c.publish(f"ecm_engine/{key}/attr", a, qos=1, retain=True)

    def close(self) -> None:
        try:
            self.c.publish(AVAIL, "offline", retain=True).wait_for_publish(2)
        except Exception:
            pass
        self.c.disconnect()
        self.c.loop_stop()

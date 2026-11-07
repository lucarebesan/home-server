"""Avvio: python -m ecm_engine"""
import logging
import os
import signal
import sys
import time

from . import config
from .engine import Engine
from .ha_api import HAApi
from .publisher import Publisher
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ecm_engine")


def main():
    store = Store(config.DB_PATH)
    api = HAApi(config.HA_BASE, config.HA_TOKEN_FILE)
    holder = {}

    def on_command(topic, payload):
        if "e" in holder:
            holder["e"].on_command(topic, payload)

    pub = Publisher(config.MQTT_HOST, config.MQTT_PORT, os.environ.get("MQTT_USER"),
                    os.environ.get("MQTT_PASS"), on_command=on_command)
    engine = Engine(api, store, pub)
    holder["e"] = engine
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    engine.recover()
    log.info("motore avviato")
    next_learn = 0.0
    try:
        while True:
            t0 = time.time()
            try:
                engine.tick_sample()
                if t0 >= next_learn:
                    engine.tick_learn()
                    next_learn = t0 + config.LEARN_PERIOD_S
            except Exception:
                log.exception("errore nel ciclo")
            time.sleep(max(1.0, config.SAMPLE_PERIOD_S - (time.time() - t0)))
    finally:
        pub.close()
        log.info("motore fermato")


if __name__ == "__main__":
    main()

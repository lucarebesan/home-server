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


def cycle(engine, t0: float, next_learn: float) -> float:
    """Un giro del ciclo; restituisce il prossimo istante di apprendimento.
    next_learn avanza prima di tick_learn: un apprendimento che fallisce non si
    ripete a ogni minuto."""
    try:
        engine.tick_sample()
    except Exception:
        log.exception("errore nel campionamento")
    if t0 >= next_learn:
        next_learn = t0 + config.LEARN_PERIOD_S
        try:
            engine.tick_learn()
        except Exception:
            log.exception("errore nell'apprendimento")
    return next_learn


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
            next_learn = cycle(engine, t0, next_learn)
            time.sleep(max(1.0, config.SAMPLE_PERIOD_S - (time.time() - t0)))
    finally:
        pub.close()
        log.info("motore fermato")


if __name__ == "__main__":
    main()

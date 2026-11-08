"""Costanti ed elenco entità HA lette dal motore."""
import os

HA_BASE = os.environ.get("HA_BASE", "http://127.0.0.1:8123")
HA_TOKEN_FILE = os.environ.get("HA_TOKEN_FILE", "/run/secrets/ha_token")
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
DB_PATH = os.environ.get("DB_PATH", "/data/engine.db")

SAMPLE_PERIOD_S = 60
LEARN_PERIOD_S = 900
RETENTION_DAYS = 400

# chiave interna -> entity_id
ENTITIES = {
    "stagione": "input_select.stagione",
    "free_cooling": "input_select.free_cooling",
    "manuale": "input_select.ecm_manuale",
    "durata_manuale": "input_number.ecm_manuale_durata_minuti",
    "lim_inf": "sensor.ecm_limite_inferiore",
    "lim_sup": "sensor.ecm_limite_superiore",
    "commutazione": "input_number.commutazione_estate_inverno",
    "isteresi_comm": "input_number.isteresi_commutazione_estate_inverno",
    "mattina": "input_datetime.nilan_mattina",
    "serale": "input_datetime.nilan_serale",
    "acs_inv": "input_boolean.ecm_acs_inverno_ciclo_attivo",
    "acs_soc": "input_boolean.ecm_acs_ciclo_soc_attivo",
    "cp_modo": "sensor.compactp_modo_funzionale_selezionato",
    "cp_compressore": "sensor.compactp_compressore",
    "cp_vent": "sensor.compactp_ventilazione_selezionata",
    "cp_stato": "sensor.compactp_stato_controllo",
    "cp_resistenza": "sensor.compactp_resistenza_elettrica_acs",
    "tosh_on": "sensor.toshiba_on_off_unita",
    "tosh_modo": "sensor.toshiba_modo_unita",
    "tosh_vent": "sensor.toshiba_velocita_ventilatore",
    "tosh_rps": "sensor.toshiba_velocita_compressore_u_e",
    "p_cp": "sensor.compactp_potenza_attiva",
    "p_tosh": "sensor.toshiba_potenza_attiva",
    "t_zg": "sensor.ecm_zona_giorno_temperatura_media",
    "t_zn": "sensor.ecm_zona_notte_temperatura_media",
    "t10": "sensor.compactp_t10_temperatura_sensore_stanza",
    "t2": "sensor.compactp_t2_temperatura_immissione",
    "t_ext": "sensor.egwk_temp_aria_esterna_prima_egwk",
    "soc": "sensor.growatt_inverter_growatt_battery_soc",
    "pv": "sensor.growatt_inverter_growatt_pv_power_total",
    "load": "sensor.growatt_inverter_growatt_total_load_power",
    "imp": "sensor.growatt_inverter_growatt_total_import_power",
    "discharge": "sensor.growatt_inverter_growatt_battery_discharge_power",
    "charge": "sensor.growatt_inverter_growatt_battery_charge_power",
    "write": "automation.nilan_write",
}

NUMERIC_KEYS = ["tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext",
                "soc", "pv", "load", "imp", "discharge", "charge", "lim_inf", "lim_sup",
                "commutazione", "isteresi_comm"]

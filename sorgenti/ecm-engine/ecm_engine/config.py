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
    "t11": "sensor.compactp_t11_temperatura_bollitore_parte_alta",
    "t12": "sensor.compactp_t12_temperatura_bollitore_parte_bassa",
    "acs_heat_test": "input_boolean.ecm_acs_prova_caldo_attiva",
    "t_ext": "sensor.egwk_temp_aria_esterna_prima_egwk",
    # stessa sonda, ma solo dopo 10 min di ventilazione Compact (package HA ecm_temperatura_esterna)
    "t_ext_aff": "sensor.ecm_temperatura_esterna_affidabile",
    "soc": "sensor.growatt_inverter_growatt_battery_soc",
    "pv": "sensor.growatt_inverter_growatt_pv_power_total",
    "load": "sensor.growatt_inverter_growatt_total_load_power",
    "imp": "sensor.growatt_inverter_growatt_total_import_power",
    "discharge": "sensor.growatt_inverter_growatt_battery_discharge_power",
    "charge": "sensor.growatt_inverter_growatt_battery_charge_power",
    "write": "automation.nilan_write",
    # catena dell'aria esterna: sonda prima EGWK (t_ext) -> T1 -> T4 -> T2 immessa
    "t1": "sensor.compactp_t1_temperatura_aria_esterna_post_egwk",
    "t4": "sensor.compactp_t4_temperatura_dopo_scambiatore_passivo",
    "bypass_apre": "sensor.compactp_apertura_bypass",
    "bypass_chiude": "sensor.compactp_chiusura_bypass",
    "serranda": "sensor.compactp_serranda_aria",
    "u_bagno": "sensor.ble_humidity_mija_bagno",
}

# termometri ambiente (MIJA via ble_monitor): giorno = sogg + studio, notte = matr + ale + leo;
# il bagno non entra nelle medie (zona ponte fra giorno e notte)
ROOMS = {"sogg": "soggiorno", "studio": "studio", "matr": "matrimoniale", "ale": "ale", "leo": "leo",
         "bagno": "bagno"}
for _k, _n in ROOMS.items():
    ENTITIES[f"t_{_k}"] = f"sensor.ble_temperature_mija_{_n}"
    ENTITIES[f"bat_{_k}"] = f"sensor.ble_battery_mija_{_n}"
# istante dell'ultima lettura ricevuta (last_reported) del termometro: serve per l'età del dato
REPORTED = {f"lr_{_k}": f"sensor.ble_temperature_mija_{_n}" for _k, _n in ROOMS.items()}
ROOM_BATTERY_MIN = 10   # stessa soglia del package HA ecm_zone_climate

NUMERIC_KEYS = ["tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t11", "t12", "t_ext", "t_ext_aff",
                "soc", "pv", "load", "imp", "discharge", "charge", "lim_inf", "lim_sup",
                "commutazione", "isteresi_comm", "t1", "t4", "u_bagno",
                *(f"{p}_{k}" for k in ROOMS for p in ("t", "bat", "lr"))]

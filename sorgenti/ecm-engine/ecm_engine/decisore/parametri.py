"""Soglie e costanti del decisore, allineate alla ``10 - ECM INVERNO`` live."""

# matrice inverno: avvio = T min + offset, fine recupero = avvio + MARGINE_RECUPERO
OFFSET = {(False, "zg"): 0.0, (False, "zn"): -0.5, (True, "zg"): -1.0, (True, "zn"): -1.5}
MARGINE_RECUPERO = 0.5
MASSIMO_DEFAULT = 23.5
MARGINE_AVVIO_ACCUMULO = 0.0      # la 10 parte a qualunque T sotto il massimo
LIVELLO_RECUPERO = 3              # graduatoria della proposta: limiti minimi delle zone
LIVELLO_ACCUMULO = 6              # accumulo termico con energia favorevole

VEL_MAX = {False: 3, True: 2}     # giorno / notte
VEL_RIPIEGO = {False: 3, True: 2}
PERMANENZA_S = 900
TREND_FINESTRE_MIN = (20, 30, 60)
TREND_NON_POSITIVI = 2            # finestre non positive della zona in recupero per salire
MEDIA_S = 600                     # medie zona a 10 minuti come la 10

# energia
BATTERIA_WH = 20000
RISERVA_SOC = 15.0
IMPORT_MAX_W = 300
SCARICA_MAX_W = 250
DUTY_NOTTE = 1.0                  # la 10 assume Toshiba acceso per tutta la notte residua
W_RIPIEGO = {1: 1000.0, 2: 1100.0, 3: 1270.0}

# contratto futuro con HA
LEASE_S = 180
DIVERGENZA_CICLI = 3

# entità lette in più dal motore (chiave interna -> entity_id)
ENTITA = {
    "t_min_inv": "input_number.t_min_inverno",
    "massimo_acc": "input_number.ecm_inverno_massimo_accumulo",
    "auto_10": "automation.10_ecm_inverno",
    "rec_zg": "input_boolean.ecm_inverno_recupero_zona_giorno",
    "rec_zn": "input_boolean.ecm_inverno_recupero_zona_notte",
    # aggregato OR dei due latch di zona; serve a diagnosticare la parità, non è un terzo latch
    "rec_minimo_ha": "input_boolean.ecm_inverno_recupero_minimo_attivo",
    "accumulo_ha": "input_boolean.ecm_inverno_accumulo_attivo",
    "fascia_climatica": "sensor.ecm_fascia_climatica_attiva",
    "t_zg_10m": "sensor.ecm_zona_giorno_temperatura_media_10m",
    "t_zn_10m": "sensor.ecm_zona_notte_temperatura_media_10m",
    "trend_zg_20": "sensor.ecm_zg_trend_temperatura_20m",
    "trend_zg_30": "sensor.ecm_zg_trend_temperatura_30m",
    "trend_zg_60": "sensor.ecm_zg_trend_temperatura_60m",
    "trend_zn_20": "sensor.ecm_zn_trend_temperatura_20m",
    "trend_zn_30": "sensor.ecm_zn_trend_temperatura_30m",
    "trend_zn_60": "sensor.ecm_zn_trend_temperatura_60m",
    "consumo_base": "sensor.ecm_consumo_base_casa",
    "consenso_carica": "binary_sensor.ecm_acs_inverno_carica_disponibile_stabile",
    "consenso_batteria_piena": "binary_sensor.ecm_acs_batteria_piena_stabile",
    "prelievo_rete_stabile": "binary_sensor.ecm_acs_prelievo_rete_stabile",
    "copertura_profilo": "sensor.ecm_copertura_profilo_casa",
}
for _h in range(24):
    ENTITA[f"profilo_h{_h:02d}"] = f"input_number.ecm_profilo_casa_h{_h:02d}"

NUMERICHE = ["t_min_inv", "massimo_acc", "t_zg_10m", "t_zn_10m", "consumo_base",
             "copertura_profilo", *(f"trend_{z}_{m}" for z in ("zg", "zn") for m in (20, 30, 60)),
             *(f"profilo_h{h:02d}" for h in range(24))]

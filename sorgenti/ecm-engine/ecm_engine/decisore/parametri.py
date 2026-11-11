"""Soglie e costanti del decisore. Quelle marcate DA VERIFICARE sono ricostruite dal
diario e vanno confrontate con automations/nilan/10_ecm_inverno.yaml sul server."""

# matrice inverno: avvio = T min + offset, fine recupero = avvio + MARGINE_RECUPERO
OFFSET = {(False, "zg"): 0.0, (False, "zn"): -0.5, (True, "zg"): -1.0, (True, "zn"): -1.5}
MARGINE_RECUPERO = 0.5
MASSIMO_DEFAULT = 23.5
MARGINE_AVVIO_ACCUMULO = 0.3      # DA VERIFICARE: l'accumulo parte sotto massimo - margine
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
IMPORT_MAX_W = 200                # DA VERIFICARE: oltre, l'accumulo diurno si ferma
SCARICA_MAX_W = 200               # DA VERIFICARE
DUTY_NOTTE = 1.0                  # DA VERIFICARE: quota della notte con Toshiba acceso
W_RIPIEGO = {1: 700.0, 2: 1000.0, 3: 1300.0}   # DA VERIFICARE; E90 misurato ~1272 W il 10/11
PROFILO_GIORNI = 14

# contratto futuro con HA
LEASE_S = 180
DIVERGENZA_CICLI = 3

# entità lette in più dal motore (chiave interna -> entity_id)
ENTITA = {
    "t_min_inv": "input_number.t_min_inverno",
    "massimo_acc": "input_number.ecm_inverno_massimo_accumulo",
    "auto_10": "automation.10_ecm_inverno",
    "rec_zg": "input_boolean.ecm_inverno_recupero_giorno",      # DA VERIFICARE
    "rec_zn": "input_boolean.ecm_inverno_recupero_notte",       # DA VERIFICARE
    "accumulo_ha": "input_boolean.ecm_inverno_accumulo_attivo",
    "consenso_fv": "binary_sensor.ecm_consenso_fv_stabile",     # DA VERIFICARE
}
NUMERICHE = ["t_min_inv", "massimo_acc"]

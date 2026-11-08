# Stage A - confronto nilan_batch.py vs sensori command_line attuali (2026-11-08)

Script: `/config/scripts/nilan_batch.py` (python3 stdlib, nel container homeassistant), cookie proprio
`/config/tmp/gwc_batch_cookie.txt`. Una login + UNA POST `pluginManager.cgi` con 31 `sendCommand`
(proxy 1999108/1999494/1999667) + `getShm` 1999237 (Gestione Split, 8 valori) + `getShm` 1999690 (umidita).
Nessun comando di scrittura.

Metodo: script lanciato nel container, subito dopo `GET /api/states`; il valore del batch e' passato
nello STESSO template di stato che andra' in `nilan_sensori.yaml` e renderizzato con `POST /api/template`
(quindi le mappature tipo `{0:'SPENTO',1:'ACCESO'}` sono verificate davvero).

Note emerse:
- Il gateway risponde sempre gzip (anche senza Accept-Encoding): lo script decomprime.
- La login con cookie separato NON invalida la sessione di nilan_sensor.sh (gwc_cookie.txt non e' stato riscritto).
- Gestione Split letto da `getShm 1999237` (modulo) invece che dal proxy 1999752 IdN: valori identici dopo arrotondamento.
- `compactp_potenza_attiva` in HA era `unavailable` al momento del run 3: timeout del vecchio command_line
  (358 timeout di nilan_sensor.sh nelle ultime 24 h nei log HA). Nel run 1 il valore coincideva.
- `sensor.umidita_media_aria_interna` era commentato (1999108 Id15 non mappato, "done"): ora 68.1 % da
  `getShm 1999690.humidity`, la stessa grandezza "Rh Compact P" della UI del gateway (76.98 % il 07/11;
  oggi Uspec/DewPoint dello split sono scesi coerentemente: 10.9 g/kg contro 12.8).

## Durata
| run | durata script |
|---|---|
| 1 | 18.0 s |
| 2 | 6.8 s |
| 3 | 14.1 s |
| (prova iniziale) | 8.2 s |

Variabilita' dovuta al gateway (esegue i comandi in serie e serve in parallelo i vecchi nilan_sensor.sh).
command_timeout del sensore: 55 s.

## Run 1
| entity_id | HA ora (command_line) | batch (template) | unita | esito |
|---|---|---|---|---|
| sensor.toshiba_on_off_unita | SPENTO | SPENTO |  | OK |
| sensor.toshiba_modo_unita | RISCALDAMENTO | RISCALDAMENTO |  | OK |
| sensor.toshiba_velocita_ventilatore | ALTA | ALTA |  | OK |
| sensor.toshiba_setpoint | 29 | 29 | °C | OK |
| sensor.toshiba_velocita_compressore_u_e | 0 | 0 | rps | OK |
| sensor.toshiba_potenza_attiva | 10 | 10 | W | OK |
| sensor.gestione_split_auto_mode | 0 | 0 |  | OK |
| sensor.gestione_split_current_mode | 1 | 1 |  | OK |
| sensor.gestione_split_dew_point | 15.4 | 15.4 | °C | OK |
| sensor.gestione_split_offset_accensione_estate | 1 | 1 |  | OK |
| sensor.gestione_split_offset_accensione_inverno | -3 | -3 |  | OK |
| sensor.gestione_split_orario_fine_spegnimento_notturno | 8.5 | 8.5 |  | OK |
| sensor.gestione_split_orario_spegnimento_notturno | 20.5 | 20.5 |  | OK |
| sensor.gestione_split_u_spec | 10.9 | 10.9 |  | OK |
| sensor.egwk_temp_aria_esterna_prima_egwk | 13.4 | 13.4 | °C | OK |
| sensor.compactp_t1_temperatura_aria_esterna_post_egwk | 20.2 | 20.2 | °C | OK |
| sensor.compactp_potenza_attiva | 5 | 5 | W | OK |
| sensor.compactp_t2_temperatura_immissione | 21.1 | 21.1 | °C | OK |
| sensor.compactp_t4_temperatura_dopo_scambiatore_passivo | 22.9 | 22.9 | °C | OK |
| sensor.compactp_t5_temperatura_batteria_superiore | 20.2 | 20.2 | °C | OK |
| sensor.compactp_t6_temperatura_batteria_inferiore | 19.4 | 19.4 | °C | OK |
| sensor.compactp_t10_temperatura_sensore_stanza | 21.5 | 21.5 | °C | OK |
| sensor.compactp_t11_temperatura_bollitore_parte_alta | 47.1 | 47.1 | °C | OK |
| sensor.compactp_t12_temperatura_bollitore_parte_bassa | 20.6 | 20.6 | °C | OK |
| sensor.compactp_stato_controllo | STOP VENTILAZIONE | STOP VENTILAZIONE |  | OK |
| sensor.compactp_modo_funzionale_selezionato | RISCALDAMENTO | RISCALDAMENTO |  | OK |
| sensor.compactp_ventilazione_selezionata | OFF | OFF |  | OK |
| sensor.compactp_setpoint_aria | 25 | 25 | °C | OK |
| sensor.compactp_setpoint_acs_resistenza | 38 | 38 | °C | OK |
| sensor.compactp_setpoint_acs_compressore | 20 | 20 | °C | OK |
| sensor.compactp_offset_raffrescamento | +4 | +4 |  | OK |
| sensor.compactp_temperatura_massima_bollitore | 80 | 80 | °C | OK |
| sensor.compactp_serranda_aria | OFF | OFF |  | OK |
| sensor.compactp_apertura_bypass | OFF | OFF |  | OK |
| sensor.compactp_chiusura_bypass | OFF | OFF |  | OK |
| sensor.compactp_compressore | OFF | OFF |  | OK |
| sensor.compactp_resistenza_elettrica_acs | OFF | OFF |  | OK |
| sensor.compactp_isteresi_nz | 0.8 | 0.8 | °C | OK |
| sensor.compactp_soglia_commutazione_estate_inverno | 16 | 16 | °C | OK |
| sensor.umidita_media_aria_interna | unavailable | 68.1 | % | DIVERSO |

validi=40 durata_s=18.0

## Run 3
| entity_id | HA ora (command_line) | batch (template) | unita | esito |
|---|---|---|---|---|
| sensor.toshiba_on_off_unita | SPENTO | SPENTO |  | OK |
| sensor.toshiba_modo_unita | RISCALDAMENTO | RISCALDAMENTO |  | OK |
| sensor.toshiba_velocita_ventilatore | ALTA | ALTA |  | OK |
| sensor.toshiba_setpoint | 29 | 29 | °C | OK |
| sensor.toshiba_velocita_compressore_u_e | 0 | 0 | rps | OK |
| sensor.toshiba_potenza_attiva | 8 | 8 | W | OK |
| sensor.gestione_split_auto_mode | 0 | 0 |  | OK |
| sensor.gestione_split_current_mode | 1 | 1 |  | OK |
| sensor.gestione_split_dew_point | 15.4 | 15.4 | °C | OK |
| sensor.gestione_split_offset_accensione_estate | 1 | 1 |  | OK |
| sensor.gestione_split_offset_accensione_inverno | -3 | -3 |  | OK |
| sensor.gestione_split_orario_fine_spegnimento_notturno | 8.5 | 8.5 |  | OK |
| sensor.gestione_split_orario_spegnimento_notturno | 20.5 | 20.5 |  | OK |
| sensor.gestione_split_u_spec | 10.9 | 10.9 |  | OK |
| sensor.egwk_temp_aria_esterna_prima_egwk | 13.3 | 13.3 | °C | OK |
| sensor.compactp_t1_temperatura_aria_esterna_post_egwk | 20.2 | 20.2 | °C | OK |
| sensor.compactp_potenza_attiva | unavailable | 5 | W | DIVERSO |
| sensor.compactp_t2_temperatura_immissione | 21.1 | 21.1 | °C | OK |
| sensor.compactp_t4_temperatura_dopo_scambiatore_passivo | 22.9 | 22.9 | °C | OK |
| sensor.compactp_t5_temperatura_batteria_superiore | 20.2 | 20.2 | °C | OK |
| sensor.compactp_t6_temperatura_batteria_inferiore | 19.4 | 19.4 | °C | OK |
| sensor.compactp_t10_temperatura_sensore_stanza | 21.5 | 21.5 | °C | OK |
| sensor.compactp_t11_temperatura_bollitore_parte_alta | 47.1 | 47.1 | °C | OK |
| sensor.compactp_t12_temperatura_bollitore_parte_bassa | 20.6 | 20.6 | °C | OK |
| sensor.compactp_stato_controllo | STOP VENTILAZIONE | STOP VENTILAZIONE |  | OK |
| sensor.compactp_modo_funzionale_selezionato | RISCALDAMENTO | RISCALDAMENTO |  | OK |
| sensor.compactp_ventilazione_selezionata | OFF | OFF |  | OK |
| sensor.compactp_setpoint_aria | 25 | 25 | °C | OK |
| sensor.compactp_setpoint_acs_resistenza | 38 | 38 | °C | OK |
| sensor.compactp_setpoint_acs_compressore | 20 | 20 | °C | OK |
| sensor.compactp_offset_raffrescamento | +4 | +4 |  | OK |
| sensor.compactp_temperatura_massima_bollitore | 80 | 80 | °C | OK |
| sensor.compactp_serranda_aria | OFF | OFF |  | OK |
| sensor.compactp_apertura_bypass | OFF | OFF |  | OK |
| sensor.compactp_chiusura_bypass | OFF | OFF |  | OK |
| sensor.compactp_compressore | OFF | OFF |  | OK |
| sensor.compactp_resistenza_elettrica_acs | OFF | OFF |  | OK |
| sensor.compactp_isteresi_nz | 0.8 | 0.8 | °C | OK |
| sensor.compactp_soglia_commutazione_estate_inverno | 16 | 16 | °C | OK |
| sensor.umidita_media_aria_interna | unavailable | 68.1 | % | DIVERSO |

validi=40 durata_s=14.1

## Esito deploy (Stage B/C, 2026-11-08 20:39-20:47)
- Deploy senza riavvio: `command_line.reload`, rimozione delle 40 voci registry command_line
  (WebSocket `config/entity_registry/remove`), `template.reload`. 40/40 entity_id ripresi, nessun `_2`.
- `compactp_offset_raffrescamento` tornato command_line individuale: come template il valore `+4` diventava `4`
  (HA converte i risultati numerici dei template), l'API /api/template usata nel confronto non lo mostrava.
- 6 minuti di osservazione: Nilan Batch aggiornato ogni 60 s, durata 5.7-6.0 s, 39/39 valori validi, nessun unavailable,
  nessun errore command_line/template dopo il passaggio.
- Carico: processi nilan_sensor.sh in 60 s 67 -> 0-1 (+1 nilan_batch.py), curl 63 -> 0; CPU container HA
  17-49 % (media ~30) -> 20-30 % (media ~24); loadavg 1 min 2.27 -> 1.34.
- Commit 9b22cc2 su lucarebesan/home-assistant-config (main).

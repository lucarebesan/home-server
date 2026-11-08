# Import dello storico del datalogger nei campioni del motore

Import una tantum (`python -m ecm_engine.gw_import <cartella>`, codice in `ecm_engine/gw_import.py`)
degli export del datalogger del gateway (`data_gw/`, fuori dal repo) nella tabella `samples`
di `/data/engine.db`. Analisi preliminare: `scripts/gw_inspect.py data_gw`.

## File usati

| Dispositivo | File | Passo |
|---|---|---|
| Compact P 2001969 | cp_135_90, cp_90_45, cp_45_0, cp_topup (cp_180_135 vuoto, test_week sovrapposto: ignorati) | 60 s |
| Split Toshiba 2002144 | dev_2002144 + retry_split_1009 (riempie il blocco 09-23/10 mancante) | 60 s |
| Modulo I/O 2002022 | dev_2002022 | 60 s |
| Contatore Compact 2002794 | dev_2002794 | 600 s |
| Contatore Split 2002795 | dev_2002795 | 600 s |
| Zone (HA) | ha_zone_stats.json: statistiche orarie a lungo termine di HA | 1 h |

Blocchi con corpo vuoto o non JSON e righe con `stato` diverso da 0 vengono scartati; a parità di minuto vince la prima riga letta.

## Orario: il campo `utc` NON è UTC

Il gateway scrive nel campo `utc` la propria ora locale codificata come epoch. Lo si vede confrontando le medie orarie del
gateway con le statistiche di HA (T10, EGWK, potenza Toshiba): il minimo errore arriva con +2 h in estate e +1 h in
inverno (errore medio su T10 0,01-0,02 °C dopo la correzione). `gw_utc()` sottrae l'offset Europe/Rome e segue l'orologio
del gateway: il 25/10 il gateway è rimasto in ora legale fino alle 07:52 locali e poi è tornato alle 06:54. Il cambio si
riconosce dal salto all'indietro nella sequenza delle righe, non dall'ora ufficiale (le 03:00). Poi l'allineamento è al
minuto (troncamento).

## Mappatura

Le stringhe sono quelle dei `value_template` HA (`docs/gateway/ha_side/nilan_sensori.yaml`): i plugin API che legge HA
inoltrano lo stesso registro grezzo (`variabili_*.csv`, colonna maps_to_grandezza), quindi le codifiche coincidono.

| Chiave campione | Colonna gateway | Decodifica |
|---|---|---|
| cp_vent | CP `vent_sel` | 0 OFF, 1-4 STEP n (STEP 1 = V1, osservabile come E7/E8, vedi sotto) |
| cp_compressore | CP `Comp` | 0 OFF, 1 ON |
| cp_stato | CP `Control_state` | 0 OFF … 7 RISCALDAMENTO, 8 RAFFRESCAMENTO, 9 ACS, 10 ANTILEGIONELLA, 11 RAFFRESCAMENTO + ACS, 13 SBRINAMENTO, 16 ALLARME, 17 RISCALDAMENTO + ACS (mappa HA completa) |
| cp_resistenza | CP `Hot_water_heater` | 0 OFF, 1 ON |
| cp_modo | CP `mode_set` | 0 OFF, 1 RISCALDAMENTO, 2 RAFFRESCAMENTO, 3 AUTO, 4 SERVICE (non entra nel campione: serve a stagione) |
| t10, t2 | CP `T10`, `T2` | numerico |
| tosh_on | Split `UnitONOFF` | 0 SPENTO, 1 ACCESO |
| tosh_modo | Split `UnitMode` | 0 AUTOMATICO, 1 RISCALDAMENTO, 2 DEUMIDIFICATORE, 3 VENTILAZIONE, 4 RAFFRESCAMENTO |
| tosh_vent | Split `UnitFanSpeed` | 0 AUTOMATICA, 1 BASSA, 2 MEDIA, 3 ALTA |
| tosh_rps | — | `CompressorRevolution` (2002144163) non è registrato dal datalogger (abilRec 0): None. Serve solo a duty_tosh, che non viene pubblicato |
| t_ext | I/O `Ing Temp 1` "Temperatura aria esterna prima EGWK" | è la grandezza dietro `sensor.egwk_temp_aria_esterna_prima_egwk` (plugin 1999108 Id14 = 2002022022). Nessun ripiego su CP T1: T1 è l'aria dopo il pozzo EGWK, quindi un'altra grandezza. Dove manca l'I/O il campione è "dato mancante t_ext" |
| p_cp | contatore 2002794 `Potenza Attiva` | forward-fill del valore a 10 minuti, al massimo 15 minuti, poi None |
| p_tosh | contatore 2002795 `Potenza Attiva` | come p_cp |
| t_zg, t_zn | statistiche HA `sensor.ecm_zona_giorno/notte_temperatura_media` | media oraria posta al centro dell'ora, interpolazione lineare al minuto; tra due medie distanti più di 3 h vale il bordo per 30 minuti, poi None. **Prima della prima statistica di zona** (HA le ha dal 27/08 14:00) e solo se mancano entrambe, t_zg e t_zn valgono T10 (sonda ambiente Nilan): il campione non porta un flag, vale la regola per data |
| stagione | CP `mode_set`, `mode_act`, `Control_state` | vedi sotto |
| free_cooling | — | non ricostruibile (`input_select.free_cooling` è solo in HA): None, cioè "non attivo" |

Gli stati dei dispositivi a 60 s sono in forward-fill per al massimo 180 s, così un minuto mancante non scarta il campione.
Il valore -3276,8 (int16 -32768 × 0,1) è "non disponibile" e vale None. Si produce un campione per ogni minuto CP; il
resto passa da `engine.build_sample(snap, ts, None)`, quindi validità e codici seguono le stesse regole del motore dal vivo.

## Nilan V1 (STEP 1)

`cp_vent` STEP 1 non è nella numerazione HA (E = 10·d + u, u 0..6; le opzioni di 09 la usano). Per osservarlo e
impararlo è u=7 (CP OFF V1) e u=8 (CP ON V1): codici E7, E8, E87, E88... Non esistono in 09, quindi non entrano mai
nei candidati di prova (`rules.codes_for_season`), né nei consigli (`texts.best_stat`) e `label_09` li rifiuta.
Tipo: u=7 NEUTRO, u=8 come gli altri CP ON (HEAT/COOL secondo stagione).

## Stagione

`input_select.stagione` ha storico solo dal 31/10. Regola:

1. `mode_set` RISCALDAMENTO → INVERNO, RAFFRESCAMENTO → ESTATE;
2. `mode_set` AUTO: `mode_act` 1 → INVERNO, 2 → ESTATE. Nei dati però `mode_act` coincide sempre con `mode_set` (3 = AUTO),
   quindi decide la direzione del controllo CP: `Control_state` RISCALDAMENTO[ + ACS] → INVERNO, RAFFRESCAMENTO[ + ACS] → ESTATE;
3. altrimenti (standby, stop, ACS, OFF) resta la stagione precedente.

Dal 05/07 al 15/10 il CP è sempre in AUTO; dal 15/10 è in RAFFRESCAMENTO e dal 02/11 in RISCALDAMENTO. HA è passato
a INVERNO il 03/11 alle 23:00, quindi il punto 1 concorda con HA. In AUTO la stagione segue la direzione del compressore CP,
e così le combinazioni "solo CP ON" (4/5/6) prendono il tipo fisicamente giusto (HEAT quando il CP scalda: T2 − T10 ≈ +16 °C;
COOL quando raffresca: ≈ −9 °C). Unico caso incoerente noto: con `mode_set` RAFFRESCAMENTO e controllo in RISCALDAMENTO
con compressore acceso, 232 minuti a metà ottobre risultano ESTATE/COOL. È lo stesso comportamento del motore dal vivo.

## Cosa si inserisce

Solo i minuti precedenti il primo campione già presente nel DB (`INSERT OR IGNORE`, niente sovrascritture).

## Ripasso con `--replace-before`

`python -m ecm_engine.gw_import <cartella> --replace-before <epoch|AAAA-MM-GGTHH:MM>` ricostruisce i minuti con
ts < il limite e SOSTITUISCE solo i campioni già nel DB non validi con motivo "dato mancante t_zg" o "cp non
classificato" (`REPLACE_MOTIVI`): serve a recuperare i minuti scartati dalla prima importazione grazie al ripiego T10 e
a V1. Tutti gli altri campioni, e i minuti assenti dal DB, restano intatti. Stampa i conteggi per motivo precedente.

## Correzioni successive all'import (08/11/2026)

- `t_ext` resta la sonda "Ing Temp 1" grezza nel database; il segmenter (`fix_text`) la sostituisce nei minuti con la Compact ferma o appena ripartita, interpolando tra le letture dopo 10 minuti di ventilazione.
- `p_cp` fino al 31/10 21:00 è stato sostituito con la media dal contatore "Totale energia importata" (`gw_repair --energia-cp`): la potenza istantanea registrata ogni 600 s perdeva i cicli del compressore.
- I minuti con resistenza ACS e quelli con stati non classificabili sono stati riclassificati con `gw_repair` usando gli stati del datalogger.

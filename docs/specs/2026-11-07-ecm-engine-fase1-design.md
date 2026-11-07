# ECM Engine – Fase 1: apprendimento consumi ed efficacia

Data: 2026-11-07. Server: HP `home@192.168.1.100` (HA in Docker, Mosquitto locale).

## Obiettivo

Un servizio Python sul server impara, per ogni combinazione E (CompactP + Toshiba), quanto consuma e quanto scalda o raffresca ciascuna zona, in funzione della temperatura esterna. Propone ed esegue sessioni di prova brevi per riempire i buchi (soprattutto HEAT, oggi mai misurato). Mostra i risultati in una tab di ECM v2 leggibile da Luca.

In fase 1 il motore **non decide il clima**: l'unico comando che invia è l'avvio o l'arresto di una sessione di prova tramite `09 - ECM MANUALE`.

Fuori ambito (fasi successive, spec separate): modalità ombra per l'inverno, controllo invernale, sostituzione di EG/EN.

## Contesto verificato

- Potenze dedicate: `sensor.compactp_potenza_attiva`, `sensor.toshiba_potenza_attiva` (W, lettura dal gateway Nilan ogni 60 s).
- Stato reale macchine: `sensor.compactp_compressore` (ON/OFF), `sensor.compactp_ventilazione_selezionata` (OFF/STEP n), `sensor.compactp_modo_funzionale_selezionato`, `sensor.compactp_stato_controllo`, `sensor.compactp_resistenza_elettrica_acs`, `sensor.toshiba_on_off_unita`, `sensor.toshiba_modo_unita`, `sensor.toshiba_velocita_ventilatore`, `sensor.toshiba_velocita_compressore_u_e` (rps).
- Temperature: `sensor.ecm_zona_giorno_temperatura_media`, `sensor.ecm_zona_notte_temperatura_media`, `sensor.compactp_t10_temperatura_sensore_stanza`, `sensor.compactp_t2_temperatura_immissione`, esterna vera `sensor.egwk_temp_aria_esterna_prima_egwk`.
- Energia: `sensor.growatt_inverter_growatt_battery_soc`, `..._pv_power_total`, `..._total_load_power`, `..._total_import_power`, `..._battery_discharge_power`, `..._battery_charge_power`.
- Contesto: `input_select.stagione`, `input_select.free_cooling`, `input_select.ecm_manuale`, `input_number.t_min_inverno`, `input_number.t_max_estate`, `sensor.ecm_limite_inferiore`, `sensor.ecm_limite_superiore`, `input_datetime.nilan_mattina`, `input_datetime.nilan_serale`, `input_boolean.ecm_acs_inverno_ciclo_attivo`, `input_boolean.ecm_acs_ciclo_soc_attivo`.
- Il registro storico HA tiene 7 giorni e non conserva la combinazione nelle statistiche lunghe: il motore raccoglie i propri dati in diretta.
- Token HA in `~/.config/ecm/ha_token` (600) sul server.

## Numerazione combinazioni (riferimento: quella di HA)

Codice `E = 10·d + u`.

- `u` (CompactP): 0 = CP OFF V0, 1/2/3 = CP OFF V2/V3/V4, 4/5/6 = CP ON V2/V3/V4. CP ON significa compressore nella modalità della stagione (COOL in ESTATE, HEAT in INVERNO).
- `d` (Toshiba): 0 = OFF, 1/2/3 = DRY V1/V2/V3, 4/5/6 = COOL V1/V2/V3, **7/8/9 = HEAT V1/V2/V3 (nuovi)**.

La numerazione del sito (E4–E7 con CP V1, Toshiba COOL V4–V6, E100–E113) non è usata; va segnalata a chi cura il sito.

Il motore ricava il codice dallo **stato reale** delle macchine, non dagli helper. Mappatura velocità Toshiba: BASSA/MEDIA/ALTA → V1/V2/V3 (valori diversi, per esempio AUTO, finiscono in un codice "non classificato" e il campione è escluso). Il CP è "ON" ai fini del codice se il modo funzionale è quello della stagione e il controllo non è in ACS; l'accensione effettiva del compressore è registrata a parte come duty.

## Architettura

Container `ecm-engine` (Python 3.12 slim, `network_mode: host`, `restart: unless-stopped`, log 5 MB × 2), sorgente in `Misc/ecm-engine/`, deploy in `~/ecm-engine` sul server, database SQLite in `~/ecm-engine/data/engine.db`. Token montato in sola lettura.

Moduli, ognuno testabile da solo:

| Modulo | Compito | Dipende da |
|---|---|---|
| `config.py` | Costanti ed elenco entità; lettura variabili d'ambiente | — |
| `ha_client.py` | WebSocket HA: autenticazione, `get_states`, sottoscrizione `state_changed` filtrata, `call_service`; riconnessione con backoff | `websockets` |
| `combo.py` | Stato reale → codice E, tipo (NEUTRO/COOL/DRY/HEAT), validità | — |
| `store.py` | Schema SQLite e accesso: `samples`, `periods`, `tests` | `sqlite3` |
| `collector.py` | Ogni 60 s fotografa lo stato corrente e salva un campione | `ha_client`, `combo`, `store` |
| `segmenter.py` | Divide i campioni in periodi a combinazione costante; scarta i primi 5 minuti e i periodi disturbati | `store` |
| `learner.py` | Aggrega per combinazione × fascia di temperatura esterna: consumo, duty, efficacia per zona, affidabilità; produce le graduatorie | `store` |
| `proposer.py` | Sceglie la prova più utile ammessa ora e la durata | `learner`, stato corrente |
| `tester.py` | Avvia, sorveglia e chiude una sessione di prova (manuale o automatica) | `ha_client`, `store` |
| `publisher.py` | Entità MQTT con discovery; riceve pulsante e interruttore | `paho-mqtt` |
| `main.py` | Ciclo asincrono che lega tutto | tutti |

### Campione (`samples`, uno al minuto)

ts, codice E, tipo, valido (bool) e motivo di esclusione, stagione, cp_modo, cp_compressore, cp_vent, cp_stato_controllo, cp_resistenza, tosh_on, tosh_modo, tosh_vent, tosh_rps, p_cp, p_tosh, t_zg, t_zn, t10, t2, t_ext, soc, pv, load, import, discharge, charge, manuale (selezione 09), test_id.

Campione non valido se: una potenza o una temperatura di zona non è numerica; resistenza ACS accesa; controllo CP in ACS; Free Cooling attivo; codice non classificato.

Conservazione: 400 giorni (circa 576 mila righe, pochi MB).

### Periodo (`periods`)

Sequenza di campioni validi consecutivi con lo stesso codice, senza buchi oltre 3 minuti. I primi 5 minuti sono scartati (assestamento). Un periodo con meno di 10 minuti utili è ignorato. Per ogni periodo: durata utile, potenza media CP e Toshiba, potenza media con compressore acceso, duty del compressore CP (frazione di minuti ON) e del Toshiba (rps > 0), pendenza della temperatura di ogni zona in °C/h (regressione lineare), temperatura esterna media, differenza media esterno-zona, flag `da_prova`.

### Apprendimento (`learner`)

Fasce di temperatura esterna: < 5, 5–10, 10–15, 15–20, 20–25, 25–30, ≥ 30 °C.

Per ogni (codice, fascia):

- consumo medio totale (media pesata sulla durata);
- consumo con compressore acceso e duty medio;
- efficacia per zona: pendenza media in °C/h, nel verso del tipo (positiva per HEAT, negativa per COOL/DRY); per NEUTRO solo consumo;
- costo dell'efficacia: W per °C/h guadagnato, calcolato solo se l'efficacia ha il verso giusto ed è maggiore di 0,1 °C/h;
- affidabilità: `min(periodi / 5, 1)` × fattore di coerenza (1 se la deviazione standard dell'efficacia è sotto il 50% della media, altrimenti 0,6). Un dato con affidabilità sotto 0,4 è mostrato come "da confermare".

Graduatorie per HEAT e per COOL nella fascia attuale (e nelle vicine se mancano dati): ordinate per costo dell'efficacia, a parità per consumo minore. Una combinazione con efficacia sotto 0,1 °C/h è etichettata "non rende in queste condizioni".

### Proposta di prova (`proposer`)

Candidati: combinazioni del tipo coerente con la stagione (HEAT e NEUTRO in INVERNO, COOL/DRY e NEUTRO in ESTATE), con l'affidabilità più bassa nella fascia esterna attuale. Esclusioni:

- di notte (fuori `nilan_mattina`–`nilan_serale`): niente CP V4 e niente Toshiba V3;
- in INVERNO niente prove HEAT se la zona più calda supera `ecm_limite_superiore` − 0,3; in ESTATE niente prove COOL se la zona più fredda è sotto `ecm_limite_inferiore` + 0,3.

Durata suggerita: 15 minuti se manca solo il consumo, 30 se manca l'efficacia, 20 negli altri casi.

### Sessioni di prova (`tester`)

Avvio manuale: pulsante MQTT "Avvia prova proposta". Avvio automatico: interruttore MQTT "Prove automatiche" (spento di default, stato salvato nel database).

Condizioni per l'avvio, valide anche per quello manuale:

- `input_select.ecm_manuale` = AUTO, Free Cooling spento, nessun ciclo ACS attivo;
- energia: SOC ≥ 40% oppure FV ≥ consumo casa;
- tutte le zone tra `ecm_limite_inferiore` + 0,3 e `ecm_limite_superiore` − 0,3 (con la regola del verso descritta sopra).

Solo per le prove automatiche: finestra 10:00–17:00, al massimo 3 al giorno, almeno 60 minuti tra la fine di una e l'inizio della successiva.

Esecuzione: imposta `input_number.ecm_manuale_durata_minuti`, poi seleziona l'opzione della combinazione in `input_select.ecm_manuale`. Sorveglianza ogni minuto: interrompe (selezionando AUTO) se una zona esce dalla fascia ammessa, se il SOC scende sotto il 25% con FV inferiore al consumo, se la selezione di 09 cambia per mano di altri (in quel caso registra "interrotta dall'utente" e non riseleziona AUTO). A fine durata 09 torna da solo in AUTO; il motore lo verifica e registra l'esito nella tabella `tests`.

Al riavvio del motore, una prova in corso trovata nel database viene chiusa: se 09 è ancora sulla combinazione della prova, il motore riseleziona AUTO.

### Entità pubblicate (MQTT discovery, prefisso `ecm_engine`)

Disponibilità con LWT: se il motore si ferma le entità diventano non disponibili.

- `sensor.ecm_engine_stato`: online, prova in corso, errore HA.
- `sensor.ecm_engine_in_breve`: frase sintetica (≤ 255 caratteri); l'attributo `righe` contiene l'elenco delle frasi per la sezione "In breve".
- `sensor.ecm_engine_migliore_caldo` e `sensor.ecm_engine_migliore_freddo`: descrizione leggibile della combinazione migliore nella fascia attuale; attributi codice, W, °C/h, affidabilità.
- `sensor.ecm_engine_apprendimento_caldo` e `sensor.ecm_engine_apprendimento_freddo`: percentuale (media delle affidabilità delle combinazioni ammesse nella fascia attuale).
- `sensor.ecm_engine_prova_proposta`: testo; attributi codice, durata, motivo, `avviabile` e `motivo_blocco`.
- `sensor.ecm_engine_prova_in_corso`: testo o "nessuna"; attributi inizio, fine prevista, minuti trascorsi.
- `sensor.ecm_engine_dettaglio`: stato = numero di combinazioni con dati; attributo `tabella` = elenco di righe {codice, descrizione, fascia, W, duty, °C/h ZG, °C/h ZN, W per °C/h, periodi, affidabilità}.
- `sensor.ecm_engine_avvisi`: numero di avvisi; attributo `elenco` (per esempio "potenza Toshiba non numerica da 2 ore", "HA disconnesso").
- `button.ecm_engine_avvia_prova` e `switch.ecm_engine_prove_automatiche`.

Le frasi per Luca sono in italiano semplice, senza codici E (per esempio "Per scaldare adesso conviene il Toshiba a velocità media da solo: circa 450 W").

## Modifiche in Home Assistant (repo di Luca, commit separati)

1. **07 ricambio aria:** `eg_abilitata` ed `en_abilitata` valgono vere solo se l'automazione è accesa **e** `stagione == 'ESTATE'`. In INVERNO il 07 torna a comandare direttamente la ventilazione (fallback già previsto). Corregge lo stop del ricambio dalle 16:04 del 06/11.
2. **09 ECM MANUALE:**
   - nuove opzioni E70–E76, E80–E86, E90–E96 in `input_select.ecm_manuale` (`packages/ecm_helper.yaml`), con etichette nello stile esistente ("E84 - CP ON V2 • HEAT V2");
   - `decina_e` ammessa 0–9;
   - stagione: in ESTATE ammesse decine 0–6 e FREE COOLING; in INVERNO ammesse decine 0 e 7–9 (CP ON = HEAT); le altre combinazioni fuori stagione restano rifiutate con la notifica attuale;
   - Toshiba per decine 7–9: `toshiba_modo` = RISCALDAMENTO, `toshiba_ventilatore` = d − 6, climatizzatore acceso;
   - CP ON/OFF in INVERNO: 09 oggi forza il compressore in COOL spostando `t_estate` rispetto a T10 con `margine_cp_on`/`margine_cp_off`. In INVERNO il verso è opposto: CP ON → `t_estate` sopra T10 di isteresi/2 + margine; CP OFF → sotto T10 di isteresi/2 + margine (WRITE in INVERNO invia `t_estate` senza offset). Al ritorno in AUTO in INVERNO, `t_estate` torna al valore che aveva prima della prova (salvato da 09 all'avvio);
   - le velocità Toshiba reali (`sensor.toshiba_velocita_ventilatore`) vanno verificate sul campo prima di fissare la mappatura del motore (oggi si vede MEDIA);
   - nuovo helper `input_number.ecm_manuale_durata_minuti` (10–60, passo 5, predefinito 20) al posto dei 60 minuti fissi;
   - in INVERNO 09 sospende anche 07 (già in elenco) e non tocca ACS.
3. **ECM v2:** nuova tab "Apprendimento" in `Misc/ha-ecm-v2/ecm_v2.yaml` con sezione "In breve" (frasi, migliori combinazioni, barre di apprendimento, prova proposta con pulsante, interruttore delle prove automatiche, prova in corso) e sezione "Dettaglio" (tabella markdown da `sensor.ecm_engine_dettaglio`, avvisi, stato motore). Deploy via WebSocket `lovelace/config/save` con il token, senza riavvio di HA.

Le modifiche 1 e 2 sono spinte dal server con la deploy key, come i commit precedenti, poi ricaricate (automazioni, input_select, input_number) senza riavvio.

## Gestione errori

- HA irraggiungibile: riconnessione con backoff 5 s → 60 s; nel frattempo nessun campione (il buco interrompe i periodi); avviso pubblicato.
- MQTT irraggiungibile: riconnessione automatica di paho; i calcoli continuano.
- Entità mancante o non numerica: campione non valido con motivo; dopo 30 minuti consecutivi diventa un avviso.
- Eccezione in un ciclo: registrata nel log, il ciclo successivo riparte; il processo non muore.
- Motore fermo: HA non ne risente (entità non disponibili); una prova in corso termina comunque per la durata impostata in 09.

## Test

- Unitari (pytest, nessuna rete): `combo` su tutte le combinazioni e i casi limite; `segmenter` con sequenze sintetiche (buchi, assestamento, campioni non validi); `learner` con dati sintetici a pendenza nota; `proposer` e regole di avvio del `tester` su scenari (notte, energia bassa, zona al limite, ACS attivo, limite giornaliero); formato dei messaggi di discovery.
- Integrazione: avvio contro HA reale in sola lettura per 10 minuti; i campioni nel database devono corrispondere agli stati letti dall'API.
- HA: dopo il deploy, prova reale di una combinazione HEAT di 10 minuti avviata dal pulsante, con verifica di comando, ritorno in AUTO e registrazione nel database.

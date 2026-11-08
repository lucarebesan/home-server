# ECM Engine (motore di apprendimento del clima)

Ultima verifica: 2026-11-08.

## Scopo

Servizio Python nel container `ecm-engine` sul server. Misura quanto consuma e quanto scalda o raffresca ogni combinazione di Nilan CompactP e Toshiba (codici E della numerazione di HA), per scegliere la più economica. Propone ed esegue brevi prove tramite l'automazione `09 - ECM MANUALE`. Fase 1: non comanda il clima, salvo le prove.

Sorgente, spec e piani: repository locale `Misc/ecm-engine/` sul PC di Mattia (`docs/specs/`, `docs/plans/`, `docs/gateway/`).

## Funzionamento

- Ogni 60 s legge da HA (una richiesta `POST /api/template`) e salva un campione in `~/ecm-engine/data/engine.db` (SQLite, conservazione 400 giorni).
- Ogni 15 minuti ricalcola l'apprendimento (circa 3,5 s su 180 mila campioni) e aggiorna le entità.
- Pubblica in HA via MQTT discovery: `sensor.ecm_engine_*` (stato, in breve, migliore caldo/freddo, apprendimento, prova proposta, prova in corso, ultime prove, da misurare, dettaglio, avvisi), `binary_sensor.ecm_engine_prova_avviabile`, `button.ecm_engine_avvia_prova`, `switch.ecm_engine_prove_automatiche`.
- Le entità sono mostrate nella tab "Apprendimento" della dashboard ECM v2.
- "Da misurare" (`sensor.ecm_engine_da_misurare`, max 20 righe) elenca solo i candidati ammessi **adesso**: stagione, fascia di temperatura esterna, zone compatibili, meno di 100 misure. Di notte (fuori `input_datetime.nilan_mattina`–`nilan_serale`, oggi 08:30–20:30) esclude Nilan V4 e Toshiba velocità alta, quindi "Toshiba caldo alta" compare solo di giorno (verificato 08/11/2026 alle 21:00, 14 righe senza velocità alta). Etichetta: "alta", non "alto".
- Token HA in `~/.config/ecm/ha_token` (montato in sola lettura nel container). Mosquitto locale senza autenticazione.

## Prove

- Partono dal pulsante oppure, se l'interruttore "Prove automatiche" è acceso (spento di default), da sole tra le 10 e le 17, al massimo 3 al giorno, con 60 minuti tra una e l'altra.
- Condizioni di avvio: 09 in AUTO, Free Cooling spento, nessun ciclo ACS, SOC ≥ 40% oppure FV ≥ consumo, **00-NILAN WRITE accesa**, temperature delle zone compatibili. Per le prove di caldo la zona più calda deve restare sotto la soglia ESTATE − 1 °C (oggi 23,5 °C).
- Il motore riporta 09 in AUTO se: una zona supera la soglia ESTATE − 0,5 °C, il SOC scende sotto il 25% senza sole, WRITE si spegne, mancano dati per 5 minuti, oppure la prova supera la durata di 3 minuti.
- Senza WRITE accesa gli helper cambiano ma le macchine no: le prove sarebbero inutili e sospenderebbero il ricambio aria, per questo il motore le blocca.

## Dati caricati

- Campioni live dal 07/11/2026 19:49.
- Storico dal recorder di HA (31/10–07/11).
- Storico del datalogger del gateway Higeco (04/07–31/10), con zone ricavate dalle statistiche orarie di HA dal 27/08 e da T10 prima. Dettagli in `Misc/ecm-engine/docs/gateway/import_mapping.md`.
- Backup del database prima dell'ultima sostituzione: `~/engine_pre_replace.db` (da cancellare quando non serve più).

## Gestione

```sh
# deploy (dal PC di Mattia, nella cartella ecm-engine): test + rsync + rebuild
./deploy.sh
# stato e log
ssh hp 'docker ps --filter name=ecm-engine; docker logs --tail 20 ecm-engine'
# fermare
ssh hp 'cd ~/ecm-engine && docker compose down'
```

## Verifica

- `sensor.ecm_engine_stato` = `online`.
- `docker logs ecm-engine` senza `Traceback`; riga di log con la durata dell'apprendimento.
- Campioni recenti in `engine.db` (l'ultimo ha meno di 2 minuti).

## Limiti noti

- Dallo storico i consumi sono attendibili, l'efficacia (°C/ora) poco: osservando passivamente la casa è già regolata e le zone hanno solo medie orarie. Per l'efficacia servono le prove.
- La velocità V1 della Nilan (STEP 1) è registrata con codici propri (u=7 e u=8, per esempio E7, E8), fuori dalla numerazione di HA. Non è mai proposta come prova.

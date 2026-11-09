# Gateway Higeco (Nilan, Toshiba, contatori)

Ultima verifica: 2026-11-09 22:54 (audit in sola lettura nel pannello admin e confronto fra catalogo, HA e manuali CTS602). Documentazione completa del protocollo, catalogo delle 228 grandezze e mappature: `sorgenti/ecm-engine/docs/gateway/` (`acts.md`, `catalogo_grandezze.csv`, `import_mapping.md`).

## Cos'è

- Higeco GWCV4-M1-2ETH, `http://192.168.1.171`, firmware core 25.12.1, impianto "Rebesan-Foletto", collegato al cloud `exrg-data.it`.
- Dispositivi Modbus: Compact P (driver Nilan CTS602, 89 grandezze), Split Toshiba (IntesisBox, 21), modulo I/O iSMA (temperatura EGWK, 21), contatori di energia SDM120 di Compact e Split (9 ciascuno), sanificatore Jonix (20), ingressi della scheda (3).
- HA legge e scrive attraverso `/config/scripts/nilan_sensor.sh` e `nilan_write.sh`, con l'utente di sola lettura predefinito.

## Utenti

- Pannello di controllo → Utenti (cliccare l'icona, non l'etichetta). Gli utenti esistenti sono `admin` (Amministratore) e `user` (Ruolo 15). Ci sono 15 ruoli con permessi a matrice (sistema, interfaccia, periferiche, plugin). Nessun utente è stato aggiunto.
- Le credenziali admin le conosce Mattia: si inseriscono a mano nella pagina, mai in chat, script o repository.
- Con `user` si leggono circa 49 grandezze tramite i plugin proxy (`pluginManager.cgi` `sendCmd`/`sendCommand`, `getShm`). Storico (`dataLogCgi getDataLog`) e lettura diretta (`acqModCgi getShmData`) richiedono admin.

## Confini dell'audit Nilan tramite il gateway

- **Verificato il 09/11 dal catalogo e dal pannello admin:** il driver `NILAN-CTS602_it` del gateway mappa 89 grandezze Compact P, di cui 32 leggibili con `user` e 57 aggiuntive tramite la lettura diretta riservata all'admin. Fra le 89, 46 risultano `RW` nel driver: questa etichetta descrive il registro, non autorizza a scriverlo. Il gateway ha risposto su `192.168.1.171:80`; HA esponeva 39/39 valori del batch Nilan. Nel pannello admin, le grandezze delle schede Temperature, States, Impostazioni, Eventi, Ingressi, Uscite, Avanzate e Resistenza avevano valori aggiornati al 09/11 22:52.
- **Verificato dai manuali Nilan:** CTS602 offre anche funzioni native come programma settimanale, regolazione umidità, ACS e antilegionella, sbrinamento, bypass/raffrescamento e, nelle versioni che lo supportano, Smart Grid. Non tutte compaiono fra le 89 grandezze del driver Higeco. L'admin Higeco dà accesso ai valori e allo storico configurati nel gateway, non all'intero software della centralina né alle opzioni installatore. Riferimenti: [panoramica Compact P](https://www.en.nilan.dk/products/ventilation-with-heating/ventilation-and-hot-water-production/compact-p), [istruzioni CTS602 Compact P](https://www.en.nilan.dk/Files/Files/Engelsk/Downloads/4.%20Software%20instructions/S24_Compact-P_GB.pdf).
- **Audit ripetibile in sola lettura:** accedere manualmente come admin nel pannello Higeco (credenziali mai negli script o nel repository); leggere le 89 grandezze Compact P con `getShmData` e lo storico con `getDataLog`, senza `W*`, set/save/reset; confrontare versione software, accessori e impostazioni di servizio con il pannello Nilan. Registrare separatamente valori osservati, funzioni solo documentate e funzioni non mappate. Le credenziali admin Higeco e il livello installatore CTS602 sono accessi distinti.
- **Fotografia admin del 09/11 22:52–22:54, sola lettura:** modo `Heat`, STEP 3, compressore acceso, resistenza ACS spenta, nessun allarme corrente né negli ultimi 7 giorni. Umidità Compact P 62,42%; CO2 0 ppm. Ventilazione selezionata: immissione livelli 1–4 = 28/40/58/100%, estrazione = 26/38/56/100%; a STEP 3 i due ventilatori leggevano 58/56%. Regolazione umidità: livello basso 1, alto 4, soglia bassa 40%, massimo alta umidità 60 min. `Air exchange mode` = `Comfort`. `CentralHeat.HeatType` = `OFF`, `Tipo postriscaldo` = 0 e uscita postriscaldo = 0%. I tre campi della versione software leggevano `3_`, `6_`, `46`: formato da confermare sul pannello CTS602.
- **Aperto:** disponibilità reale di accessori/contatti Smart Grid, sensore CO2 e postriscaldo; CO2 a 0 e riscaldamento centrale `OFF` sono indizi, non prova definitiva di assenza. Verificare anche se la regolazione nativa dell'umidità è attiva: i parametri sono configurati, ma la sola fotografia non mostra quando è intervenuta. Le opzioni native non mappate (programmi settimanali, antilegionella, Smart Grid) richiedono lettura del pannello Nilan/menù di servizio, senza dedurle dal manuale generico.

## Lettura

- Login: `GET /cgi-bin/userCgi?p=user&u=<utente>&query=[{"act":"getStatus"}]` → cookie `gwc=<k>`. Le risposte sono compresse: usare `curl --compressed`.
- Più letture in una richiesta: più oggetti `sendCommand` nello stesso array `query`. Il gateway le esegue comunque una alla volta (0,2–0,5 s ciascuna; tutte le 60 di HA in 14–29 s).
- `getShm {"idPlugin":1999690}` restituisce in 0,4 s i valori del modulo APP, compresa l'**umidità vera** (il sensore HA su 1999108 Id15 legge un registro non mappato).
- **Solo comandi di lettura**: mai comandi `W*`, né set/save/reset/reboot.

## Lettura da Home Assistant (dall'8/11)

- `/config/scripts/nilan_batch.py`: una login con cookie proprio (`/config/tmp/gwc_batch_cookie.txt`, separato da quello di `nilan_write.sh`), poi una sola richiesta con 30 `sendCommand` e due `getShm` (1999237 per lo split, 1999690 per l'umidità). Stampa un JSON con un valore per unique_id, oppure null.
- In `packages/nilan_sensori.yaml`: il command_line "Nilan Batch" (ogni 20 s, timeout 18 s, dal commit `126230e`; stato = numero di valori validi) e 39 sensori template con gli stessi nomi, unique_id e `entity_id` dei vecchi command_line. `sensor.nilan_batch` è escluso dal recorder (vale dal prossimo riavvio di HA).
- `sensor.compactp_offset_raffrescamento` resta un command_line separato: passando da un template il valore "+4" diventerebbe il numero 4, mentre WRITE si aspetta la stringa.
- Cadenza: il driver del gateway interroga la Nilan ogni 15 s e i valori cambiano entro 10–20 s; la lettura dura 6–9,5 s. Con 20 s il gateway resta libero più di metà del tempo, anche per le scritture di WRITE. Sotto i 15 s il margine non basta.
- Verifica: `sensor.nilan_batch` si aggiorna ogni minuto con 39 valori su 39; nessun errore di command_line o template in `docker logs homeassistant`.
- **Rollback senza fermare HA** (backup in `/config/tmp/backup_nilan_batch/`):
  1. `docker exec homeassistant cp /config/tmp/backup_nilan_batch/nilan_sensori.yaml.bak /config/packages/nilan_sensori.yaml`;
  2. `template.reload`;
  3. togliere dal registro le 39 voci template di quei unique_id con `config/entity_registry/remove` via WebSocket;
  4. `command_line.reload`: i vecchi sensori riprendono gli `entity_id` originali;
  5. se serve, `git revert 9b22cc2` sul repo HA e cancellare `scripts/nilan_batch.py`.

## Storico (datalogger)

- Inizia il 2026-07-04 06:03. Compact P, Split e modulo I/O ogni 60 s; contatori ogni 600 s.
- Richiesta: `POST /cgi-bin/dataLogCgi` con `query=[{"act":"getDataLog","sn":"UG7G8G3CUG7G","DATI":{"idLog":<id dispositivo>,"start":s,"stop":s,"maxNumRecord":100000,"period":60,"zeroTimeOffset":0,"items":[<id grandezze>]}}]`.
- Una settimana di Compact P (28 colonne registrate) richiede circa 17 s e pesa 2,2 MB. Fare una richiesta alla volta, con pause di qualche secondo: HA usa lo stesso gateway.
- Anche `start` e `stop` della richiesta vanno espressi come ora locale scritta come epoch: per le 17:00 italiane si passa `Date.UTC(…, 17, 0)`. Verificato l'8/11: con l'epoch vero la finestra arriva un'ora prima.
- Dal browser con la sessione admin aperta, la richiesta si fa con `fetch("/cgi-bin/dataLogCgi", {method: "POST", body: "query=" + encodeURIComponent(JSON.stringify(q))})`: la password non passa mai dall'agente.
- **Il campo `utc` non è UTC**: è l'ora locale scritta come epoch (+2 h in estate, +1 h in inverno). Il 25/10 il gateway ha cambiato ora alle 07:52, non alle 03:00.
- Export eseguito l'8/11 dalla sessione admin nel browser; file in `sorgenti/ecm-engine/data_gw/` sul PC di Mattia (circa 92 MB, fuori da git).
- Scaricati in seguito, sempre in `data_gw/`: `e90_20261108*.json` (17:00–19:30 dell'8/11), `repair_20261107_08.json` (Compact P e Split dal 07/11 18:00 all'08/11 23:00, usato da `gw_repair`), `getConf_20261108_prima.json` (configurazione completa letta con l'admin prima del tentativo di mappare i kWh; può contenere dati di rete, per questo non è in git).

## Contatori di energia (kWh)

- I misuratori SDM120 hanno "Totale energia importata" (Compact `2002794799`, Split `2002795799`), registrato dal datalogger (Compact ogni 600 s, Split ogni 60 s; risoluzione 1 Wh). Verificato l'8/11: nessun modulo API lo espone, quindi HA non lo legge (`sensor.compactp_potenza_attiva` e `sensor.toshiba_potenza_attiva` sono la potenza istantanea, API-CP1 Id3 e API-T Id13).
- Per esporlo andrebbe mappato in uno slot dei moduli API (libero: API-T Grandezza 15). **Il gateway accetta il salvataggio di un modulo solo da spento** ("Prima di salvare le modifiche spegnere il GWC"): acquisizione, plugin e datalogger fermi per qualche minuto. L'8/11 Mattia ha deciso di non farlo: il motore usa i kWh solo per lo storico.
- Nel pannello admin le voci si aprono cliccando l'icona, non l'etichetta.

## Osservazioni

- Allarme Nilan attivo il 15–17/07 e dal 15/10 al 27/10 (dal datalogger); lo stato di controllo non è mai passato ad ALLARME.
- Buco di 1,6 h il 18/08 su tutti i dispositivi; circa il 3% di letture mancanti sui contatori.

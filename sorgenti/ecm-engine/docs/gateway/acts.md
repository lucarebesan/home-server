# Gateway 192.168.1.171 - protocollo di lettura (esplorazione READ-ONLY, 2026-11-07)

Regola: nessun comando di scrittura. Accesso solo dal server home@192.168.1.100.

## Protocollo noto (da HA: ha_side/nilan_sensor.sh, nilan_write.sh, nilan_sensori.yaml)
- Login: `GET /cgi-bin/userCgi?p=user&u=user&query=[{"act":"getStatus"}]` -> token `.DATI[0].DATI.k`, cookie `gwc=<k>`.
- Lettura: `GET /cgi-bin/pluginManager.cgi?query=[{"act":"sendCmd","pluginId":<ID>,"command":{"act":"<CMD>","arg":1}}]` (curl -g), valore in `.data.commandResult[0].data`.
- Sessione scaduta: `ERR=1, STRERR="Permission Denied"` -> rifare login.
- **SCRITTURA (da evitare)**: stesso endpoint con `act = "W" + IdXX` (es. `WId12`) e `arg = valore` (nilan_write.sh). Quindi ogni act che inizia per `W` scrive.

## Plugin usati da HA (ognuno espone Id1..Id15)
| pluginId | contenuto (dai nomi HA) |
|---|---|
| 1999108 | Toshiba (Id1-13) + EGWK T aria esterna (Id14) + umidita media interna (Id15) |
| 1999752 | "Gestione split" (logica split: auto mode, dew point, offset, orari, set E/I/M, log) |
| 1999494 | CompactP API-CP1 (temperature T1..T12, potenza, stato, modo, ventilazione, setpoint aria) |
| 1999667 | CompactP API-CP2 (setpoint ACS, bypass, serranda, compressore, resistenza, umidita, air exchange) |

Elenco completo comandi HA (60, attivi/commentati): `ha_side/ha_commands.tsv`.

## Gateway identificato (getStatus)
- **Higeco GWC**, SN `UG7G8G3CUG7G`, coreVersion `25.12.1`, coreMobileV `25.9.23`, lingua IT, utente `user` (uid 9450, gruppo g=14, auth=1).
- getStatus restituisce anche `t` (ora locale epoch), `utc`, `timeZoneOffset` (3600), `pg` (`/desk/deskTop.html`).
- Risposte gzip: usare sempre `curl --compressed`.
- UI desktop: `/core/25.12.1/desk/deskTop.html` + js in `/core/25.12.1/desk/js/*.js` (copiati in `ui/`).

## Act di lettura trovati nella UI (ui/*.js) - formato POST `query=<json array>` (anche GET)
Formato generale: `[{"act":"<act>","idReq":<x>,"sn":"<SN>","DATI":{...}}]`
| CGI | act | DATI | scopo |
|---|---|---|---|
| /cgi-bin/plugin.cgi | getAllGr | {} | elenco device e "Grandezze" (tutte le variabili) -> `gwc.devArr` |
| /cgi-bin/acqModCgi | getShmData | {"items":{"<idLog>":[<idGrandezza>,...]}} | valori realtime da shared memory (cache acquisizione) |
| /cgi-bin/dataLogCgi | getDataLog | {"idLog":N,"start":s,"stop":s,"maxNumRecord":100000,"period":p,"zeroTimeOffset":0,"items":[id..]} | **storico datalogger** (grafici) |
| /cgi-bin/opt.cgi? | getConf | {} | configurazione gwc |
| /cgi-bin/serverCgi | getAlrmLog | {"from":0,"to":ms,"id":[],"idAss":1,"statoAlr":"ALRM_ATTIVO"} | allarmi (usato lato server cloud) |
| /cgi-bin/connection.cgi | getInfo / getConfRete / getConfModem | {} | rete (non di interesse) |
| /cgi-bin/handleGwcFiles.cgi | get / getlist | {"dir":..} | file/immagini |
| /cgi-bin/expFile.cgi | (POST name,data) | | solo export lato browser di una tabella gia caricata, non legge dati |
Da NON usare (scrivono): setConfRete, setConfModem, applyConf, sendConfToServer, onOff, del, modApn, cancApn, testSeriale, sendFileToServer, logoutUser (innocuo ma inutile), e sendCmd con act `W*`.

## Risultato chiave: getConf (mainGwcCgi) funziona con utente `user` -> catalogo completo
`POST /cgi-bin/mainGwcCgi query=[{"act":"getConf","idReq":"getConf","sn":"UG7G8G3CUG7G","DATI":{}}]` -> 200 KB JSON (salvato in `raw/getConf.json`).
- Modello: `GWCV4-M1-2ETH` (model PGWC0027, hwType GWC_V4), impianto "Rebesan-Foletto", cloud `www.exrg-data.it` (refresh 300 s, VPN on).
- pkgInfo: core 25.12.1, kernel 25.10.24, systemLib 25.11.18, driverLib 24.12.4, scheduler 24.11.13, plugin gpc-*.
- `getAllGr` su plugin.cgi -> **Permission Denied** per `user` (ma non serve: getConf contiene tutto).
- ID: device = 7 cifre (2xxxxxx), plugin/moduli < 1999999, grandezza = `device*1000 + n` (es. 2001969970 = Compact P / T1). idLog = id/1000.

### Periferiche (perifArr) - variabili Modbus reali
| id | lbl | driver | bus | n var | camp(s) |
|---|---|---|---|---|---|
| 2000920 | GWC M1 (on board, 2 DI) | GWC-V4_M1_2DI | shm | 3 | 600 |
| 2001969 | Compact P | NILAN-CTS602_it (modbus addr 30, 19200 8E1, poll 15) | RS485_01 | 89 | 60 |
| 2002144 | Split | IntesisBox_Toshiba TO-RC-MBS-1 | RS485_02 | 21 | 60 |
| 2002022 | Modulo I/O | iSMA-B-4U40-H (T18 aria esterna EGWK, rele EGWK) | RS485_02 | 21 | 60 |
| 2002794 | Misuratore En.El. Compact | Eastron SDM120-CT | RS485_02 | 9 | 600 |
| 2002795 | Misuratore En.El. Split | Eastron SDM120-CT | RS485_02 | 9 | 60 |
| 2002111 | Sanificatore | JONIX | RS485_02 | 20 | 300 |
Tutte con `abilRec=1` (datalogger attivo); 156 grandezze su 228 hanno abilRec=1.

### Moduli (plugin) - i pluginId usati da HA sono solo PROXY
- 1999494 API-CP1, 1999667 API-CP2, 1999108 API-T, 1999752 API-GestSplit (gpc-596062): `IdN` -> id grandezza (mappa in conf). Es. 1999494 Id1 -> 2001969970 (T1).
  1999108 Id15 NON e' mappato (HA lo chiama "umidita media": restituira' errore/vuoto).
- 1999283 API (gpc-668316): comandi `T1, T10, T11, Ur, CO2, Allarme, Velocita, SetACS, SetAria, T18`.
- Altri: 1999237 Gestione Split (17 var proprie), 1999690 APP V2 (19), 1999204 App (19), 1999251 Gestione EGWK, 1999224 Gestione Sanificatore, scheduler 1999051/1999833/1999863.
Catalogo completo: `catalogo_grandezze.csv` (id, device, Nome, lbl, unita, RW, registro Modbus cmdR, abilRec, quale IdN proxy lo espone).

## Test permessi (utente `user`, g=14)
| act | esito |
|---|---|
| mainGwcCgi getConf | OK (senza cookie: Permission Denied) |
| plugin.cgi getAllGr | Permission Denied |
| acqModCgi getShmData (device 2001969 e plugin 1999237) | Permission Denied |
| dataLogCgi getDataLog (2001969970, ultima ora) | Permission Denied |
| pluginManager.cgi sendCmd 1999283 | `No Plugin Found` (modulo 1999283 "API" e' disabilitato, abil=0) |
| pluginManager.cgi sendCmd 1999494 Id1 | OK `18.34` |
=> con l'utente `user` l'unico canale dati e' pluginManager.cgi (proxy API). Storico (dataLogCgi) e realtime diretto (acqModCgi) richiedono un utente di livello superiore (installatore/admin), che non abbiamo.

## Batching su pluginManager.cgi
- `sendCmd` con `command` = array -> `No Command Result` (non supportato).
- `sendCmd` con 2 oggetti nell'array query -> esegue solo il PRIMO.
- `sendCommand` (act usato dalla UI pluginManager/items.js), POST `query=[{"act":"sendCommand","idReq":"a","DATI":{"idPlugin":1999494,"command":[{"act":"Id1","arg":1}]}}]`:
  - command array con 2 elementi -> esegue solo il primo;
  - **piu' oggetti sendCommand nello stesso array query -> TUTTI eseguiti** (3 oggetti, 2 plugin: OK, 6655 ms in quel caso).

## Sweep Id1..Id16 su 1999494/1999667/1999108/1999752 (64 GET sendCmd, 0.35 s pausa)
- Ogni plugin risponde Id1..Id15; Id16 -> `err:1 "No Action"` (fine lista).
- `["done"]` (err 0) = IdN non mappato o grandezza sorgente vuota: 1999108 Id15 (umidita media, non configurata), 1999752 Id12/Id13 (SetE/SetI di Gestione Split, vuote ora).
- Tempo per comando: tipico 280-350 ms, picchi 0.8-1.5 s, un caso 6.1 s (1999108 Id11 tensione SDM120 Split).
- Risultati: `variabili_<plugin>.csv` (+ grandezza sorgente, registro Modbus, nome HA, usato in HA).

## Batching misurato (POST sendCommand, N oggetti nell'array query)
| richiesta | durata |
|---|---|
| 3 oggetti (2 plugin) | 6.7 s (primo test) |
| 15 oggetti 1999494 | 2.8 s |
| 60 oggetti (4 plugin x Id1..15) run 1 | 28.8 s |
| 60 oggetti run 2 | 13.9 s |
Tutti 60 OK, nessun errore. Il gateway esegue in serie (~0.2-0.5 s/comando): il batch evita overhead HTTP ma non accorcia molto. Lettura completa delle 60 variabili proxy: 14-30 s.

## Act di lettura aggiuntivi su pluginManager.cgi (da ui/pluginManager/pluginStats.js) - FUNZIONANO con `user`
POST `/cgi-bin/pluginManager.cgi` `query=[...]`, piu' oggetti per richiesta ammessi.
| act | DATI | esito |
|---|---|---|
| getStatistics | {} | OK 84 ms: per ogni modulo Executions, LastExec, ExecTimeInMillis, RunPeriodInSecs |
| **getShm** | {"idPlugin":<modulo>} | **OK: tutte le grandezze proprie del modulo con Valore, unit, Stato, LinkStatus, Timestamp** |
| getNonVolatile | {"idPlugin":<modulo>} | OK: memoria persistente del modulo (es. Gestione Split: FunzionamentoManuale, ModoSalvato...; scheduler: nvLog tentativi) |
| getShm su device (2001969) | | `No Plugin Found` (solo moduli) |
Da NON usare: resetStatistics, savePlugin, sendCommand/sendCmd con act `W*`.

**Batch getShm+getNonVolatile su tutti gli 11 moduli abilitati = 1 richiesta, 371 ms, 37 valori** (raw/shm_all.json).
Valori utili che arrivano solo cosi' (non esposti dai proxy IdN):
- 1999690.humidity = Rh Compact P (76.98 %) -> HA lo cerca su 1999108 Id15 che non e' mappato.
- 1999690.co2 (0 ppm, sensore probabilmente assente), 1999690.alrmState = Alarm_status, 1999690.Tint = TempRoom (sensore di riferimento).
- 1999237.*: Uspec (umidita specifica g/kg), DewPoint, TRif, SetM, fanControl, Log, Ingresso (DI1 forzatura manuale split).

## Copertura: cosa e' leggibile con l'utente `user`
`catalogo_grandezze.csv` colonna `readable_by_user`: delle 172 variabili dei device solo **49** sono raggiungibili (44 via proxy IdN, 5 solo via getShm modulo). Le altre ~123 (vedi CSV, valore `NO`) sono leggibili solo con getShmData/getDataLog, negati a `user`.
Non raggiungibili ma interessanti:
- Compact P: T3 aria estratta, T7 immissione dopo postriscaldo, T8 esterna, T9 batteria idronica, T0/T15/T16, Input_defrost (termostato sbrinamento), mode_act, velocita ventilatori estrazione/immissione %, Air_heater_capacity, OutputCprCap (capacita compressore %), four_way_valve, Alarm + Alarm_Lis_ID1..3, SoftwareVersion1-3, tutti i parametri (velocita livelli 1-4, soglie CO2/umidita, min/max temp, CentralHeat*).
  Nota: il driver NILAN-CTS602_it configurato NON ha ore compressore, ore filtro, contatori sbrinamento.
- Split Toshiba: RunningHoursCompressor (h), UnitOperationTime, CompressorCurrent, TOtemperature (esterna), THS dissipatore, temperatura liquido, UnitAlarmStatus, setpoint attuale U.I.
- SDM120 Compact e Split: **Totale energia importata/esportata kWh**, potenza reattiva, frequenza (Compact anche tensione).
- Modulo I/O: ingressi temp 2-4, 0-10V, DI, uscite (Pompa EGWK).

## Storico / log
- dataLogCgi getDataLog -> Permission Denied per `user` (il datalogger esiste: abilRec=1 su 156 grandezze, camp. 60 s Compact P / 600 s SDM Compact; idLog = device id).
- getAlrmLog e' su serverCgi lato cloud (exrg-data.it), non provato.
- Nessun CSV/export lato gateway: expFile.cgi esporta solo tabelle gia caricate nel browser.
- Per avere lo storico serve un utente installatore (o accesso al portale exrg-data.it).

## Conteggio richieste di questa esplorazione
~100 richieste dati (64 sweep + ~35 test) + ~30 file statici UI. Nessuna scrittura (nessun act W*, nessun set/save/reset).

## Raccomandazione per il bulk reader
1. Login una volta (userCgi getStatus), cookie riusato; rifare login su `Permission Denied` con ERR=1 a livello radice.
2. Ciclo veloce (ogni 30-60 s): 1 POST pluginManager.cgi con `getShm` per 1999690, 1999237 (+ getStatistics come health check) -> ~0.4 s.
3. Ciclo proxy: 1 POST con N oggetti `sendCommand` (Id1..Id15 di 1999494, 1999667, 1999108, 1999752 = 60 letture) -> 14-30 s; saltare i mappati vuoti (1999108 Id15, 1999752 Id12/13) e i duplicati gia presi da getShm. Una sola richiesta in volo alla volta (il gateway serializza e HA interroga in parallelo).
4. Valori: `commandResult[0].data` stringa numerica; `["done"]` = non disponibile; `err:1 No Action` = Id inesistente.
5. Per le ~123 variabili mancanti e lo storico: serve un utente di livello superiore (getShmData/getDataLog) oppure aggiungere mappature IdN nei moduli API (modifica di configurazione = scrittura, solo con ok esplicito).

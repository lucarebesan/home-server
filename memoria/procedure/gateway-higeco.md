# Gateway Higeco (Nilan, Toshiba, contatori)

Ultima verifica: 2026-11-27 13:32 (configurazione server identica al backup, opzione VPN attiva ma `getServerStatus.successo=0`; Exrg non operativa, HA locale 40 valori). Documentazione completa del protocollo, catalogo delle 228 grandezze e mappature: `sorgenti/ecm-engine/docs/gateway/` (`acts.md`, `catalogo_grandezze.csv`, `import_mapping.md`).

## Cos'è

- Higeco GWCV4-M1-2ETH, `http://192.168.1.171`, firmware core 25.12.1, impianto "Rebesan-Foletto", collegato al cloud `exrg-data.it`.
- Dispositivi Modbus: Compact P (driver Nilan CTS602, 89 grandezze), Split Toshiba (IntesisBox, 21), modulo I/O iSMA (temperatura EGWK, 21), contatori di energia SDM120 di Compact e Split (9 ciascuno), sanificatore Jonix (20), ingressi della scheda (3).
- HA legge e scrive attraverso `/config/scripts/nilan_batch.py`, `nilan_sensor.sh` e `nilan_write.sh`, con l'utente `user`. La pausa temporanea del 27/11 è stata rimossa su richiesta di Luca; i guasti sono ora regolati dall'attesa condivisa descritta sotto.

## Connessione Exrg e VPN (verifica del 27/11)

- Nel primo slot di `serverCgi/getServerConf` il collegamento Exrg è abilitato
  (`abilServer=1`), VPN abilitata (`abilVpn=1`) e tunnel SSH disabilitato
  (`abilTun=0`); gli altri tre slot sono spenti. `getServerStatus` riporta
  `successo=1` quando il gateway è connesso al server. Il dispositivo ha anche
  un'interfaccia `hig-vpn` con indirizzo privato, osservata prima della prova.
- Il pannello firmware 25.12.1 usa `serverCgi/saveServerConf` per salvare un
  array dei quattro slot. **Attenzione:** `confServer` è il nome del server
  configurato, mentre `server` può essere l'indirizzo operativo risolto. In
  una prima prova, inviare l'array letto tale e quale cambiando solo `abilVpn`
  ha sostituito `confServer` con `server` e ha causato una breve riconnessione.
  Per conservare il nome configurato, prima del salvataggio assegnare al campo
  `server` il valore di `confServer`. Il backup privato pre-prova è in
  `/home/home/.local/state/higeco-password/vpn-test-before.json` (permessi 600);
  non copiarlo nel repository.
- Una prova temporanea di due minuti con `abilVpn=0` ha mantenuto
  `abilServer=1` e `getServerStatus.successo=1`; alla fine la VPN è stata
  riattivata e l'intera configurazione è tornata identica al backup, con
  `successo=1`. Questo verifica il collegamento gateway–server **senza VPN**,
  ma da solo non prova che l'app Exrg fuori casa continui a mostrare dati
  aggiornati né identifica chi possiede un account Exrg.
- **Seconda prova del 27/11:** su autorizzazione di Luca è stata spenta la
  sola VPN (`abilVpn=0`) lasciando il server abilitato. Da iPhone su rete
  cellulare l'app Exrg si apriva, ma mostrava valori fermi e i comandi non
  rispondevano. Quindi per l'uso remoto di questo impianto la VPN risulta
  necessaria. Durante la prova nuovi login admin sono stati rifiutati con
  `auth=-1`; anche il tentativo di ripristino e il timer di riserva hanno
  fallito. Il gateway potrebbe aver bloccato temporaneamente le nuove
  sessioni dopo troppi accessi; la causa e la durata non sono verificate.
  La VPN è rimasta spenta fino al recupero riportato sotto. Non fare login
  ripetuti per diagnosticarla. Il cookie `user` di HA era ancora accettato per
  `getStatus`, ma non ha i permessi per `serverCgi/getServerConf` (`ERR=2`).
- **Recupero riuscito alle 13:03 locali del 27/11:** dopo circa 30 minuti
  senza togliere corrente, Luca ha segnalato che i nuovi accessi erano tornati.
  `recover_vpn.py now` ha fatto un solo login admin, riattivato `abilVpn=1`,
  verificato il nome server originario e `getServerStatus.successo=1`, poi
  chiuso la sessione. Stato persistente: `complete=True`, `attempts=1`,
  notifica non pendente; Luca ha ricevuto l'avviso sull'iPhone. **Exrg rimaneva
  però bloccata nell'app**: toccare i comandi non produceva effetti. Il solo
  `successo=1` non certifica il funzionamento dell'app o del server cloud.
  Su richiesta di Luca, non fare altre richieste admin a `.171` per ora.
- **Audit singolo autorizzato alle 13:31:** Luca ha autorizzato un solo
  accesso admin per controllare le modifiche e chiudere la sessione al
  termine. `sorgenti/higeco-password/audit_vpn.py` ha letto nella stessa
  sessione `getServerConf` e `getServerStatus`, confrontato tutti e quattro
  gli slot con il backup pre prova e fatto logout. **Nessuna differenza,
  neanche nei campi operativi**; `abilVpn=1`. Tuttavia il gateway riportava
  **`successo=0`**: in quel momento non risultava connesso al server Exrg.
  Il valore `successo=1` letto alle 13:03 non è rimasto stabile. Questo
  spiega i dati vuoti nel portale, mentre HA legge sulla LAN. La causa della
  disconnessione remota resta aperta; non attribuirla a una modifica della
  configurazione, che è identica al backup. Nessuna scrittura al gateway
  nell'audit e nessun altro login admin pianificato.
- Sorgente del recupero `sorgenti/higeco-password/recover_vpn.py`, copia sul
  mini PC `/home/home/higeco-password/recover_vpn.py`, backup privato sopra.
  La riga cron temporanea `HIGECO_VPN_RECOVERY` è stata rimossa dopo il
  successo, con backup del crontab in
  `~/.local/state/higeco-password/crontab.after-vpn-recovery`. Restano le
  due righe distinte `HIGECO_PASSWORD` per il rinnovo bimestrale. Per leggere
  lo stato senza login: `python3 /home/home/higeco-password/recover_vpn.py status`.
- Luca può togliere da remoto la corrente all'intera centrale termica,
  probabilmente anche al gateway. Non è stato fatto: fermerebbe più
  apparecchi e non è verificato che cancelli il blocco login.
- Higeco descrive separatamente [dashboard cloud e gestione utenti](https://www.higeco.com/en/cloud-services/)
  e [Page creator sul datalogger](https://www.higeco.com/en/software/).
  La schermata Exrg può quindi avere componenti locali e cloud. Nel portale
  dell'impianto la pagina APP V2 è una pagina personalizzata del plugin
  `gpc-exrgapp`, versione 26.5.20, con grafica SVG `home.svg`; questo conferma
  che la grafica attuale è una pagina custom. Non sono ancora verificati i
  permessi di modifica dell'account né come distribuire una nuova versione.
- Alle 13:24 del 27/11, dal mini PC DNS di `exrg-data.it` risolveva e
  `https://exrg-data.it/cns3/login` rispondeva `HTTP 200`; HA riportava
  40 valori Nilan aggiornati. Questo restringe il guasto osservato al
  percorso portale/account/app dopo la pagina di login, senza identificarne
  la causa. Con autorizzazione di Luca, il portale è stato aperto in sola
  lettura: APP V2 mostrava solo `---` e la pagina API-CP1 rimaneva con lo
  spinner. La console del browser registrava un errore nel visualizzatore
  (`Cannot read properties of null (reading 'itemCfg')`) dopo una richiesta
  remota fallita. **Inferenza:** il portale non riceve la configurazione/dati
  necessari per renderizzare il plugin; non è un problema limitato all'app
  iPhone. La causa precisa del fallimento remoto resta aperta. Nessuna
  modifica al portale e nessun ulteriore accesso admin a `.171`.

## Utenti

- Pannello di controllo → Utenti (cliccare l'icona, non l'etichetta). Gli utenti esistenti sono `admin` (Amministratore) e `user` (Ruolo 15). Ci sono 15 ruoli con permessi a matrice (sistema, interfaccia, periferiche, plugin). Nessun utente è stato aggiunto.
- Le credenziali di `admin` e `user` sono state inserite da Luca sul mini PC tramite prompt nascosto e sono conservate solo in `/home/home/.config/higeco-password/credentials.json` (permessi `600`), fuori dal repository. Non mostrarle in chat o nei log.
- Con `user` si leggono circa 49 grandezze tramite i plugin proxy (`pluginManager.cgi` `sendCmd`/`sendCommand`, `getShm`). Storico (`dataLogCgi getDataLog`) e lettura diretta (`acqModCgi getShmData`) richiedono admin.

### Rinnovo automatico delle password (attivo dal 27/11)

- `sorgenti/higeco-password/renew.py` è la fonte di verità; copia installata in `/home/home/higeco-password/renew.py` (cartella `700`, file `600`). Flusso e ripristino nel [README](../../sorgenti/higeco-password/README.md). Il gateway usa HTTP sulla LAN e risposte gzip. Lo script usa `/cgi-bin/userCgi`: login con `getStatus` e cookie `gwc`, `getUser`, `getPasswordRules`, `setPasswordRules`, `modPass`.
- Nella stessa sessione admin salva le regole originali, disabilita temporaneamente cinque requisiti opzionali, risalva le stesse password di `user` e `admin`, ripristina e rilegge le regole, poi verifica i due login. Il file di recupero `~/.local/state/higeco-password/restore-rules.json` permette di ripristinare le regole dopo un'interruzione; un errore invia una notifica iPhone tramite HA. Sei test con gateway simulato coprono anche il ritentativo della notifica di successo.
- **Prova reale del 27/11 riuscita:** `--check` ha autenticato entrambi; `--renew` ha rinnovato `user` e `admin`, ripristinato tutte le regole originali e verificato i login. `restore-rules.json` assente, `last_success=2026-11-27`. HA mostrava `sensor.nilan_batch=40` prima e dopo, con aggiornamento recente. Una successiva richiesta admin ha trovato `passExpire=120`, impostato da Luca il 26/11; su sua richiesta è stato portato a **90 giorni**, conservando gli altri sette campi. Backup delle regole precedenti in `~/.local/state/higeco-password/password-rules-before-90.json`. Un altro `--check` è riuscito e il batch HA è rimasto a 40 valori recenti.
- Nel crontab di `home` sono attive due righe marcate `HIGECO_PASSWORD`: controllo alle 03:15 ogni giorno e 120 secondi dopo il boot. Il codice rinnova solo se manca un successo dal primo dei mesi dispari, a partire dal **1° gennaio 2027**; dopo una data saltata ritenta al controllo successivo. Le righe preesistenti del crontab sono state confrontate col backup `~/.local/state/higeco-password/crontab.before-higeco` e risultano invariate. `Linger=no` per `home`, perciò si usa cron anziché un timer utente.
- Dopo ogni successo il programma chiede a HA di inviare una notifica a `notify.mobile_app_iphone_luca`; se HA non la accetta, conserva la notifica pendente e ritenta al controllo giornaliero. La notifica per la prova del 27/11 è stata accettata da HA e Luca ne ha confermato la ricezione sull'iPhone. **Da verificare nel tempo:** la prima esecuzione automatica del 1° gennaio e il recupero reale dopo un riavvio o una notifica fallita.
- Dopo la prova VPN, `renew.py` è stato corretto per inviare `logoutUser`
  dopo i login di verifica e alla fine dell'esecuzione; prima lasciava
  sessioni aperte. Sei test offline con gateway simulato sono riusciti.
  Nessun nuovo login reale è stato eseguito durante il blocco.

## Confini dell'audit Nilan tramite il gateway

- **Verificato il 09/11 dal catalogo e dal pannello admin:** il driver `NILAN-CTS602_it` del gateway mappa 89 grandezze Compact P, di cui 32 leggibili con `user` e 57 aggiuntive tramite la lettura diretta riservata all'admin. Fra le 89, 46 risultano `RW` nel driver: questa etichetta descrive il registro, non autorizza a scriverlo. Il gateway ha risposto su `192.168.1.171:80`; HA esponeva 39/39 valori del batch Nilan. Nel pannello admin, le grandezze delle schede Temperature, States, Impostazioni, Eventi, Ingressi, Uscite, Avanzate e Resistenza avevano valori aggiornati al 09/11 22:52.
- **Verificato dai manuali Nilan:** CTS602 offre anche funzioni native come programma settimanale, regolazione umidità, ACS e antilegionella, sbrinamento, bypass/raffrescamento e, nelle versioni che lo supportano, Smart Grid. Non tutte compaiono fra le 89 grandezze del driver Higeco. L'admin Higeco dà accesso ai valori e allo storico configurati nel gateway, non all'intero software della centralina né alle opzioni installatore. Riferimenti: [panoramica Compact P](https://www.en.nilan.dk/products/ventilation-with-heating/ventilation-and-hot-water-production/compact-p), [istruzioni CTS602 Compact P](https://www.en.nilan.dk/Files/Files/Engelsk/Downloads/4.%20Software%20instructions/S24_Compact-P_GB.pdf).
- **Audit ripetibile in sola lettura:** accedere come admin nel pannello Higeco senza mostrare le credenziali in chat o nel repository; leggere le 89 grandezze Compact P con `getShmData` e lo storico con `getDataLog`, senza `W*`, set/save/reset; confrontare versione software, accessori e impostazioni di servizio con il pannello Nilan. Registrare separatamente valori osservati, funzioni solo documentate e funzioni non mappate. Le credenziali admin Higeco e il livello installatore CTS602 sono accessi distinti.
- **Fotografia admin del 09/11 22:52–22:54, sola lettura:** modo `Heat`, STEP 3, compressore acceso, resistenza ACS spenta, nessun allarme corrente né negli ultimi 7 giorni. Umidità Compact P 62,42%; CO2 0 ppm. Ventilazione selezionata: immissione livelli 1–4 = 28/40/58/100%, estrazione = 26/38/56/100%; a STEP 3 i due ventilatori leggevano 58/56%. Regolazione umidità: livello basso 1, alto 4, soglia bassa 40%, massimo alta umidità 60 min. `Air exchange mode` = `Comfort`. `CentralHeat.HeatType` = `OFF`, `Tipo postriscaldo` = 0 e uscita postriscaldo = 0%. I tre campi della versione software leggevano `3_`, `6_`, `46`: formato da confermare sul pannello CTS602.
- **Energy, analisi senza comando alla macchina (09/11):** nel manuale Compact P [CTS602 versione 5.40 del 10/02/2026](https://www.en.nilan.dk/Files/Files/Engelsk/Downloads/4.%20Software%20instructions/S24_Compact-P_GB.pdf), `Air exchange mode = Energy` regola il ventilatore d'immissione in funzione di T5, temperatura del condensatore: sotto la soglia bassa lavora al minimo (livello 1), fra le soglie sale, sopra la soglia alta arriva al massimo (livello 4). Le soglie predefinite del manuale sono 35/50 °C; `Comfort`, valore letto qui, mantiene il ricambio bilanciato. Una query mirata dello storico HA di T5 nelle ultime 24 ore ha restituito 954 valori numerici, minimo 16,9, mediana 22,65 e massimo 34,4 °C: **tutti sotto 35 °C**. **Inferenza condizionata:** con le soglie predefinite, `Energy` avrebbe chiesto quasi sempre l'immissione minima nel periodo osservato; al livello 1 la calibrazione letta è 28% contro il 58% del livello 3 visto alle 22:52. Le percentuali ventilatore non equivalgono direttamente a portate in m³/h. Le due soglie effettive e la modalità non sono registrate nello storico del driver Higeco (`abilRec=0` per `AirFlowAirExchMode`; le soglie non sono mappate); il manuale 5.40 può differire dalla versione installata indicata dai campi `3_`/`6_`/`46`. Perciò non è stimabile dai soli dati quanto cambierebbero m³/h, pressione e consumo, e il conteggio dei volumi della `07` richiederebbe ricalibrazione se si adottasse `Energy`.
- **Aperto:** disponibilità reale di accessori/contatti Smart Grid, sensore CO2 e postriscaldo; CO2 a 0 e riscaldamento centrale `OFF` sono indizi, non prova definitiva di assenza. Verificare anche se la regolazione nativa dell'umidità è attiva: i parametri sono configurati, ma la sola fotografia non mostra quando è intervenuta. Le opzioni native non mappate (programmi settimanali, antilegionella, Smart Grid) richiedono lettura del pannello Nilan/menù di servizio, senza dedurle dal manuale generico.

## Lettura

- Login: `GET /cgi-bin/userCgi?p=user&u=<utente>&query=[{"act":"getStatus"}]` → cookie `gwc=<k>`. Le risposte sono compresse: usare `curl --compressed`.
- Più letture in una richiesta: più oggetti `sendCommand` nello stesso array `query`. Il gateway le esegue comunque una alla volta (0,2–0,5 s ciascuna; tutte le 60 di HA in 14–29 s).
- `getShm {"idPlugin":1999690}` restituisce in 0,4 s i valori del modulo APP, compresa l'**umidità vera** (il sensore HA su 1999108 Id15 legge un registro non mappato).
- **Solo comandi di lettura**: mai comandi `W*`, né set/save/reset/reboot.

## Lettura da Home Assistant (dall'8/11)

**Pausa temporanea del 27/11, conclusa:** su richiesta di Luca era stata
creata `/config/tmp/nilan_gateway_paused`. La sentinella fa uscire i quattro
script HA prima di qualsiasi richiesta a `.171` (commit `9426e1a`, `a25c787`).
Luca ha chiesto di riprendere HA dopo il ritorno degli accessi; la sentinella
è stata rimossa e verificata assente. Rimane disponibile per un fermo manuale
futuro. Backup degli script di quella fase in
`/config/tmp/backup_nilan_gateway_pause_20261127`.

- `/config/scripts/nilan_batch.py`: una sola sessione `user` condivisa con offset e scritture (`/config/tmp/gwc_batch_cookie.txt`), poi una richiesta con 31 `sendCommand` e due `getShm` (1999237 per lo split, 1999690 per l'umidità). Stampa un JSON con un valore per unique_id, oppure null. Dal commit HA `cf449de` include la sonda ambiente Toshiba `1999108 Id1`.
- In `packages/nilan_sensori.yaml`: il command_line "Nilan Batch" (ogni 20 s, timeout 18 s, dal commit `126230e`; stato = numero di valori validi) e 40 sensori template. La sonda nuova è esposta stabilmente come `sensor.ecm_toshiba_sonda_ambiente`; una vecchia entità ripristinata con nome Toshiba può restare `unavailable` fino a riavvio e non è usata dalla logica. `sensor.nilan_batch` è escluso dal recorder (vale dal prossimo riavvio di HA).
- `sensor.compactp_offset_raffrescamento` resta un command_line separato: passando da un template il valore "+4" diventerebbe il numero 4, mentre WRITE si aspetta la stringa.
- Cadenza: il driver del gateway interroga la Nilan ogni 15 s e i valori cambiano entro 10–20 s; la lettura dura 6–9,5 s. Con 20 s il gateway resta libero più di metà del tempo, anche per le scritture di WRITE. Sotto i 15 s il margine non basta.
- L'attesa di 5 minuti per il solo batch/offset introdotta il 26/11 è stata
  sostituita il 27/11 dalla gestione comune sotto. Il vecchio file
  `nilan_letture_attesa` viene rimosso dal batch dopo una lettura riuscita;
  `nilan_offset_attesa` resta per i guasti limitati al solo offset. Backup
  pre-intervento del 26/11: `/config/tmp/backup_nilan_attesa_mdxc88xx/`.
- Protezione storica (repo HA, 04/09): `4a8ad19` applicava ai sensori che usavano lo script condiviso una pausa di 30 s dopo tre errori di trasporto in 30 s e un intervallo minimo di 60 s fra nuovi login. `78167f9` aggiungeva l'uscita `NILAN_UNAVAILABLE` su `Permission Denied` conservando il cookie, senza rifare il login. `0493b6a` ha ripristinato lo script precedente e rimosso queste protezioni. Il batch introdotto in `9b22cc2` ha ereditato il nuovo login dopo un rifiuto. L'attesa introdotta il 26/11 ha un comportamento diverso dalla regola storica.
- Verifica: `sensor.nilan_batch` ha restituito 40 valori validi; il 17/11 il proxy ha seguito la sonda Toshiba fra 21,5 e 24,5 °C durante i test. Il registro setpoint `1999108 Id6` ha accettato e restituito 28,5 e 28 °C a macchina accesa, poi 29 °C di ripristino.
- **Rollback senza fermare HA** (backup in `/config/tmp/backup_nilan_batch/`):
  1. `docker exec homeassistant cp /config/tmp/backup_nilan_batch/nilan_sensori.yaml.bak /config/packages/nilan_sensori.yaml`;
  2. `template.reload`;
  3. togliere dal registro le 40 voci template di quei unique_id con `config/entity_registry/remove` via WebSocket;
  4. `command_line.reload`: i vecchi sensori riprendono gli `entity_id` originali;
  5. se serve, `git revert 9b22cc2` sul repo HA e cancellare `scripts/nilan_batch.py`.

## Gestione dei guasti delle chiamate HA (attiva dal 27/11)

Commit HA `09aa04a`. Il batch, l'offset e le due scritture usano la stessa
sessione `user` in `/config/tmp/gwc_batch_cookie.txt`. **Solo il batch** può
fare un nuovo login `user`, massimo uno per tentativo; nessuno di questi
script usa `admin`. Il file condiviso
`/config/tmp/nilan_gateway_health.json` conserva numero di fallimenti,
motivo e scadenza della prossima prova anche se HA viene riavviato.

| Evento | Comportamento implementato |
| --- | --- |
| Batch con almeno un valore valido, altri dati assenti | I singoli dati assenti restano `unavailable`; il circuito rimane aperto alle letture e scritture ordinarie. |
| Batch senza alcun valore valido o interrotto dal timeout HA | Tutti e quattro gli script sospendono le richieste a `.171` per **5 minuti**. |
| Prima prova dopo 5 minuti ancora fallita | Attesa di **30 minuti**. Le successive prove restano una ogni 30 minuti, senza ciclo ogni 5. |
| Prova periodica durante il guasto | Prima TCP porta 80, poi **una sola grandezza** Compact P (`1999494 Id1`) con cookie `user`; se non è valida non parte il batch completo. Se il cookie è negato, il batch può fare un solo nuovo login `user`. |
| Prova valida | Esegue il batch completo; se arriva almeno un valore valido rimuove lo stato di guasto e offset/scritture riprendono. |

Il lock `/config/tmp/nilan_gateway_batch.lock` impedisce due batch
contemporanei. Il marcatore `nilan_gateway_batch_inflight` riconosce un batch
ucciso dal timeout di HA, evitando tentativi ogni 20 secondi. Durante un
guasto `nilan_sensor.sh` restituisce `NILAN_UNAVAILABLE`, le scritture
restituiscono `GATEWAY_WAITING`; se manca il cookie restituiscono
`NO_USER_SESSION` senza creare sessioni. Il batch conserva il cookie fra
tentativi e lo sostituisce in modo atomico dopo un login valido. Guasti
limitati all'offset hanno ancora la propria attesa di 5 minuti.

**Verifica del deploy:** tre test simulati nel container HA (timeout, attesa
5/30 minuti, singola prova leggera), sintassi Python/shell e `check_config`
riusciti. Dopo il deploy `sensor.nilan_batch=40`, offset `+4` con
`last_reported` recente; nessun file di guasto o pausa presente. Non è stato
provocato un guasto reale né comandata una scrittura alla macchina per test.
Verificare nel tempo il comportamento in un guasto reale e l'eventuale
necessità di una notifica iPhone per guasto prolungato. Le scritture fallite
da sole non aprono il circuito finché il batch continua a leggere.

**Ripristino:** backup immediatamente precedente in
`/config/tmp/backup_nilan_gateway_retries_20261127`. Mettere prima la
sentinella `/config/tmp/nilan_gateway_paused`, copiare i quattro script dal
backup con i permessi originali (batch/write/split `644`, sensor `755`),
controllare sintassi e `check_config`, poi rimuovere la sentinella. Un deploy
GitHub richiede anche il revert del commit `09aa04a` nel repo HA.

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

# Relè Dingtian e ponte `dtbridge`

Ultima verifica: 2026-11-08. Documentazione completa, sorgenti, backup e piedinatura
sono sul server in `~/dingtian/` (vedi `~/dingtian/README.md`).

## I relè

Nove relè WiFi Dingtian DT-R008 (8 uscite e 8 ingressi ciascuno), hardware V3.6J, basati
su ESP32 classico. Sono in WiFi sul 2,4 GHz (`Rebesan_ILIAD`), su quadri e alimentatori
diversi.

| Nome in HA / MQTT | IP | Firmware | Ripristino stato dopo riavvio |
|---|---|---|---|
| 1_Giorno-relay48065 | 192.168.1.51 | V3.1.4323A | No |
| 2_Giorno-relay48068 | 192.168.1.52 | V3.1.4323A | Sì |
| 3_Giorno-relay46029 | 192.168.1.53 | V3.1.4239A | Sì |
| 4_Sottotetto-relay48064 | 192.168.1.54 | V3.1.4323A | No |
| 5_Notte-relay48066 | 192.168.1.55 | V3.1.4323A | Sì |
| 6_Giorno-relay40220 | 192.168.1.56 | V3.1.3541A | Sì |
| 7_Notte-relay48069 | 192.168.1.57 | V3.1.4323A | Sì |
| 8_Notte-relay48067 | 192.168.1.58 | V3.1.4323A | Sì |
| 9_Giardino-relay82404 | 192.168.1.29 | V3.1.6236A | No |

Con ripristino stato su "No" (`power_failure_recovery`), un relè che si riavvia riparte
con tutte le uscite spente, quindi le luci accese si spengono. Il 2026-11-08 Mattia ha
deciso di **lasciarlo così**: non cambiarlo senza chiedere.

I pulsanti a muro sono gestiti dal relè stesso (ingresso → uscita) e funzionano anche
senza rete. Esempio: "Piatti" è Giorno3 **R6** (non R3), comandato dall'ingresso i6 e da
Alexa.

## Il problema (fatti verificati)

- I relè **si riavviano**, non perdono soltanto la rete. Prova: dopo una semplice
  riconnessione la porta sorgente TCP verso mosquitto sale di +1; dopo un riavvio è
  casuale. Su 605 riconnessioni in 72 ore (4–7/11), 596 erano riavvii. Script:
  `~/dingtian/analisi/porte_riavvii.py`.
- I riavvii arrivano a **ondate**: un breve buco sulla rete a 2,4 GHz, poi i relè con
  MQTT acceso si riavviano, alcuni subito e gli altri circa 120 s dopo (keepalive MQTT).
  Un riavvio dura 30–80 s. Gli altri dispositivi WiFi (tapparelle, Yi cam) reggono lo
  stesso buco.
- Escluse come causa: alimentazione (quadri diversi), tensione di rete, comandi di Home
  Assistant, riavvio programmato (`auto_reboot` spento), IP watchdog (spento), canale
  WiFi e risparmio energetico del box (cambiati senza effetto).

## La soluzione adottata: il ponte `dtbridge` (dal 2026-11-07)

Su tutti e 9 i relè MQTT è spento (`mqtt_protocol` = None). Il container `dtbridge` sul
server:
- legge lo stato via **Modbus-TCP** (porta 502, holding register: reg0 = numero uscite,
  reg1 = maschera uscite, reg10 = maschera ingressi invertita);
- comanda le uscite via **HTTP** (`relay_cgi.cgi`);
- pubblica sugli **stessi topic MQTT** che usava il relè (`/<zona>/relayNNNNN/out/rN`,
  `out/iN`, `out/lwt_availability`) e riceve i comandi su `in/rN`.

Home Assistant, Alexa e le automazioni non sono cambiati: le entità sono le stesse.

Esito: il 07/11, nelle 7 ondate successive all'esperimento, il relè sul ponte non si è
mai riavviato, mentre gli altri 8 hanno totalizzato 32 riavvii. Dopo la migrazione di
tutti i relè i riavvii sono **diminuiti ma non spariti**: l'08/11 alle 20:29, dopo un
buco di rete di 3–4 s, se ne sono riavviati 3 (Sottotetto4, Notte8, Giardino9). Dalle
20:35 dell'08/11 il ponte apre e chiude una connessione Modbus a ogni lettura
(`MB_SHORT=1`), per verificare se il socket sempre aperto contribuiva. Esito al 09/11:
i buchi lunghi continuano (circa uno ogni 1–1,5 ore) anche con il server in ethernet,
quindi né il socket né la WiFi del server ne sono la causa (dettagli in
`diario/2026-11.md`, 09/11 sera).

### Gestione del ponte

```sh
cd ~/dingtian/dtbridge
docker compose -p dtbridge up -d --build   # avvio o aggiornamento
docker logs -f dtbridge                    # log: "lettura fallita", "BUCO LUNGO"
```

Relè gestiti: variabile `RELAYS` in `compose.yaml` (`prefisso=ip`, separati da virgola).

### Diagnostica in Home Assistant

Il ponte pubblica via discovery, sotto ogni dispositivo Dingtian: "Ponte: raggiungibile",
"Ponte: buchi lunghi 24h (oltre 30 s)", "Ponte: buchi brevi 24h", "Ponte: ultimo buco
lungo", "Ponte: ultimo buco". C'è anche un dispositivo "Dingtian ponte", con relè
raggiungibili (N/9), buchi lunghi nelle 24 ore di tutti i relè e l'ultimo relè coinvolto.

Come leggerla:
- molti relè giù **nello stesso momento** = buco di rete o ondata;
- un solo relè = problema di quel relè o della sua copertura.

Un buco lungo può essere un riavvio o una perdita di WiFi: senza MQTT non si
distinguono. Il contatore delle 24 ore include anche i buchi dovuti al server stesso
(per esempio quando l'HP perde la WiFi).

Il container `dtdiag` (costruito da un altro agente come test) legge il log di
mosquitto: dopo la migrazione i suoi contatori di riavvii e ondate restano a zero e non
sono più significativi. Raggiungibilità e latenza restano valide.

## Protocolli dei relè (ricavati, firmware Dingtian chiuso)

- **Interfaccia web:** login `GET /login.cgi?user=…&passwd=…&`, che imposta il cookie
  `session`. Le credenziali sono quelle di fabbrica (non riportate qui).
- **Chiamate sicure (sola lettura):** `main.cgi`, `relay_load.cgi`, `ip_watchdog.cgi`,
  `relay_cgi_load.cgi`.
- **Da non chiamare mai a mano:** `reboot.cgi`, `default.cgi` (reset di fabbrica),
  `self_destruct.cgi`, `userset.cgi`, `mainset.cgi`.
- **Comando di un'uscita:** `GET /relay_cgi.cgi?type=0&relay=<0..7>&on=<0|1>&time=0&pwd=<password
  relè>&`. **Funziona senza login** e la password relè è quella di default: chiunque sulla
  WiFi di casa può comandare le luci. **Questione aperta:** impostare una password relè su
  ogni scheda e passarla al ponte (`RELAY_PWD`).
- **Configurazione:** `relay_save.cgi` (POST binario) riceve i byte 2..277 della risposta
  di `relay_load.cgi`; l'offset 268 è `mqtt_protocol`. Giardino9 (V3.1.6236A) usa un
  formato diverso, descritto in `~/dingtian/README.md`.
- **Modbus-TCP:** solo lettura (le scritture 06/16 non rispondono).
- **Aggiornamento firmware:** `upgrade.cgi` riceve un URL da cui il relè scarica il file.

## Ripristino (tornare a MQTT)

Per ogni relè:
1. rimandare a `relay_save.cgi` la configurazione originale, salvata in
   `~/dingtian/backup/relayNN_relay_load_20261107.bin` (byte 2..277; per Giardino9 vedi il
   README);
2. togliere il relè da `RELAYS`.

Per tornare del tutto a MQTT: `docker compose -p dtbridge down`.

## Alternative valutate

- **Firmware ESPHome** (le schede sono ESP32 e Dingtian pubblica la piedinatura in
  `github.com/dtlzp/relay_dev_demo`): **sospeso**. Non c'è accesso fisico alle schede,
  quindi non è possibile flashare via seriale né fare il backup della flash. Resterebbe
  solo l'OTA dalla pagina di aggiornamento, con il rischio di bloccare una scheda.
  Ricerca del 09/11 (solo GitHub, la ricerca web non era disponibile):
  - **Fatto (fonte esterna):** `github.com/kecajtop/dtr0xx_io` contiene componenti
    ESPHome per i DT-R00x (`dtr0xx_io`, e `dtr008v2io` per il layout 8CH_V2 come il
    nostro) che gestiscono 74HC595 e 74HC165 insieme. Il suo autore scrive che la
    scheda DT-R008 V3.6.13 "came with the locked chip" e che ha **sostituito l'ESP32**
    (ESP32-D0WD-V3) per poterla flashare.
  - Dingtian vende a parte una "Development Board" (README di `relay_dev_demo`: va
    chiesta esplicitamente al venditore), segno che le schede normali sono bloccate.
    `relay_dev_demo` non contiene OTA né tabella delle partizioni.
  - Altre configurazioni: `misevcik/esphome-templates` (DT-R008.yaml) e
    `dotdoom/esphome` (heating-og.yaml, DT-R008 rev 3.6.9 flashato via seriale con IO0 a
    GND). Nessuno ha documentato un passaggio via `upgrade.cgi`.
  - **Ipotesi:** se il chip ha il secure boot, l'OTA di un'immagine ESPHome non firmata
    verrebbe rifiutato. Un rifiuto è innocuo se il firmware usa le API OTA standard di
    ESP-IDF, ma non è verificabile senza provarci. La flash cifrata da sola non
    impedirebbe l'OTA.
  - **Verificato il 09/11 (fonti web):** la scheda di ESPHome Devices per la DT-R016 e il
    thread "Has anyone used Dingtian 8ch Ethernet Relay?" sul forum di HA dicono che senza
    "test/dev firmware" chiesto all'ordine l'ESP32 arriva **bloccato** (secure boot: eFuse
    `ABS_DONE_0/1`). Nessuno riporta uno sblocco via OTA o tramite il supporto. Un utente
    descrive il firmware originale come "buggy (random reboots, drop connection)".
  - **Verificato il 09/11:** i firmware ufficiali (`dingtian-tech.com/sdk/relay_upgrade_tool.zip`,
    `.dtf` fino a 4897 e `.dtf2` fino a **V3.1.6991** del 25/09/2026) sono cifrati: non
    hanno l'intestazione delle immagini ESP32. `upgrade.cgi` accetta quindi solo immagini
    Dingtian, e **un'immagine ESPHome via OTA non è possibile**. Percorso di aggiornamento
    ufficiale: sotto 4897 prima `v3_1_4897_8ch.dtf`, poi la `.dtf2`.
  - ChangeLog: nessuna voce sui riavvii dopo una WiFi persa. Voci utili per noi: 5312
    (con "Power Failure Recovery" su Yes un'alimentazione instabile riportava la
    configurazione a quella di fabbrica), 5975 ("HTTP Auth"). Giardino9 è già alla 6236 e
    ha comunque buchi lunghi: aggiornare il firmware non basta.
  - Strade concrete: Development Board Dingtian (stesso formato e morsetti) flashate al
    banco con ESPHome e sostituite nel quadro, oppure cambio del chip.
- **Copertura WiFi:** se i buchi lunghi isolati restano frequenti sui relè con segnale
  debole (Notte7 −74, Notte8 −72, Sottotetto4 −68 dBm), conviene migliorare il 2,4 GHz in
  zona notte e nel sottotetto.

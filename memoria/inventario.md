# Inventario home server

Ultima verifica: 2026-11-25 (ricambio invernale, avvio Toshiba e nuovo Nextcloud; gli altri stati restano alle date indicate sotto).

**Dal 09/11 alle 16:04 il server è il mini PC.** L'HP (`hp-homeassistant`) è spento con i
container fermati apposta: è la copia di riserva. Migrazione, ripristino e
dettagli in `procedure/migrazione-minipc.md`.

- Nome host: `minipc`.
- Indirizzo SSH: `192.168.1.100` (ethernet), porta 22. Host key SSH copiate dall'HP:
  chi conosceva l'HP non vede avvisi.
- Utenti: `home` (operativo, gruppo docker, solo chiave SSH, niente sudo) e `minipc`
  (amministratore, sudo con password). Un comando privilegiato va consegnato all'utente
  come `ssh -t minipc@192.168.1.100 'sudo …'`.
- Alias SSH `hp`: dove esiste punta a `.100`, ma non è configurato su tutti i PC (mancava sul Mac di Mattia il 09/11). La documentazione usa `home@192.168.1.100`. Senza alias, il nome `minipc` via mDNS si risolve a `192.168.1.25` (WiFi di riserva): host sconosciuto a `known_hosts`, quindi "Host key verification failed" in modalità non interattiva. Alias consigliato in `~/.ssh/config`: `Host minipc hp` → `HostName 192.168.1.100`, `User home` (messo sul Mac di Mattia il 09/11).
- Macchina: mini PC AMD Ryzen 7 5825U (8 core, 16 thread), 14 GiB di RAM, SSD BIWIN 477 GB (ext4 su `/dev/sda2`, EFI su `/dev/sda1`).
- Sistema: Ubuntu Server 26.04.1 LTS, kernel `7.0.0-43-generic`, fuso Europe/Rome. Docker CE dal repository ufficiale, store immagini containerd.
- Bluetooth: adattatore Realtek `hci0` `44:90:BA:32:32:BE`, configurato in HA dal 09/11.
- Docker e SSH sono attivi. Home Assistant, MQTT (mosquitto), nginx, Portainer e altri servizi sono in container Docker. Per i nomi aggiornati usare `docker ps -a`.
- Per spegnere il server **non** fermare i singoli container: con `restart: unless-stopped` non ripartirebbero al boot. Usare `poweroff`.

## Codex (20/11)

- Codex CLI `0.170.0` installato per l'utente `home` con l'installer ufficiale in
  `/home/home/.local/bin/codex`; pacchetto in `~/.codex/packages/standalone/`.
  La shell di login trova il comando e `codex app-server --help` risponde.
- `codex login status` indica `Logged in using ChatGPT` dopo l'accesso con
  codice dispositivo autorizzato da Luca. Non è stata usata una chiave API.
- `codex remote-control start --json` ha avviato il daemon gestito con stato
  `connected`; il daemon si è poi aggiornato automaticamente da `0.170.0` a
  `0.171.0`. Le app del PC di lavoro e del telefono mostrano `minipc` tra i
  dispositivi connessi. Il collegamento diretto è sperimentale su Linux.
- Nel crontab di `home` è presente una riga `@reboot` marcata
  `CODEX_REMOTE_CONTROL`: dopo 30 secondi avvia `codex remote-control start`,
  con al massimo cinque tentativi. La presenza della riga è verificata;
  l'esecuzione dopo un riavvio non è ancora stata provata.
- Il repository `home-server` è clonato in `/home/home/home-server` e salvato
  nell'app del PC di lavoro come progetto remoto `HOME-SERVER` su `minipc`.
  I tentativi di trasferire le chat `Gestisci mail via SSH` ed `ECM` dal PC
  ponte sono stati bloccati dal limite Codex sulle chat paginate; gli originali
  e l'automazione posta restano sul PC ponte.

## Rete

- Ethernet `enp2s0` (`68:1d:ef:66:29:75`) con prenotazione DHCP `.100` sul box (voce
  "hp-homeassistant", MAC aggiornato il 09/11). WiFi `wlp1s0` (`44:90:ba:32:32:bd`, `.25`)
  di riserva: networkd preferisce l'ethernet (metrica 100 contro 600). Se il cavo
  manca il server resta raggiungibile solo su `.25`. Config in `/etc/netplan/`.
- Box Iliad `192.168.1.254` (router e DHCP): `Rebesan_ILIAD` a 2,4 GHz sul canale 11 dal 7/11, `Rebesan_ILIAD5` a 5 GHz.
- Router EOLO `192.168.1.253`: secondo access point con gli stessi nomi di rete, DHCP spento.
- Accesso esterno: `https://ha.lrhub.duckdns.org` e, dal 25/11, `https://cloud.lrhub.duckdns.org` per Nextcloud (nginx con certificato Let's Encrypt wildcard).
- Dettagli in `procedure/rete-wifi.md` e `procedure/duckdns-certificato.md`.

## Container (9/11)

- `homeassistant` (2026.11.0 dal 09/11; l'immagine precedente resta con il tag `2026.9.3`), `mosquitto`, `nginx`, `duckdns`, `letsencrypt`, `opt-portainer-1`, `crosschex-webapi` (Anviz), `hassconfigurator`.
- Dal 25/11 lo stack `/home/home/nextcloud/compose.yaml` aggiunge `nextcloud-app` (Nextcloud 35.0.3), PostgreSQL, Redis e cron; dati e database in volumi Docker `nextcloud_html` e `nextcloud_db`. Procedura in `procedure/box-mega-nextcloud.md`.
- `ecm-engine`: vedi `procedure/ecm-engine.md`.
- Dal 09/11 il motore pubblica anche la resa ACS osservata per combinazione CP HEAT/SPLIT; conserva i dati sorgente, filtra periodi incerti e non usa questa stima per comandare le macchine.
- `dtbridge`: ponte tra i relè Dingtian e MQTT, che dal 7/11 serve tutti e 9 i relè (`~/dingtian/dtbridge`). Vedi `procedure/dingtian-ponte.md`.
- `dtdiag`: diagnostica dei Dingtian costruita come test da un altro agente (`~/dingtian/dtdiag`). Dopo la migrazione al ponte è superata in parte.
- Fermi di proposito: `grott`, `matter-hub`, `adguard`. `reolink-tv` è fermo dal 3/11 (non si sa se è voluto).
- Gli stack Portainer sono in `/var/lib/docker/volumes/opt_data/_data/compose/<n>/`; per leggerli servono i privilegi di root.

## Dispositivi in rete

- Gateway Higeco di Nilan e Toshiba: `192.168.1.171` (vedi `procedure/gateway-higeco.md`).
- Relè luci Dingtian DT-R008 (ESP32, in WiFi a 2,4 GHz): `.51`–`.58` e `.29`, in HA tramite `dtbridge`.
- Sonoff MINI `Albero` (ID eWeLink `1000b62fe2`, già `NATALE`): in HA è
  `switch.sonoff_1000b62fe2`. Nome e disponibilità verificati dopo il reload
  dell'integrazione Sonoff il 20/11. Il 21/11 è tornato disponibile anche il
  Sonoff MINI `NATALE INGRESSO` (ID `1000e48846`, già `INGRESSO NATALE`,
  `switch.sonoff_1000e48846`) e il Sonoff MINI `NATALE ESTERNO`
  (ID `1000b5ed90`, già `ESTERNO NATALE`, `switch.sonoff_1000b5ed90`).
- Inverter Growatt, via l'integrazione `solax_modbus`; TV LG.
- Terminale Anviz: `.218`, non ancora montato al 7/11.

## Attività pianificate

- Crontab di `home`: rinnovo del certificato alle 04:17 (vedi `procedure/duckdns-certificato.md`).
- `ecm-engine`: un campione ogni 60 s, apprendimento ogni 15 minuti; dal 09/11 campiona anche bollitore alto/basso e marcatore della prova ACS indiretta. Dal 10/11 pubblica stime W separate CP/SPLIT; la resa termica delle coppie resta da misurare. Prove automatiche verificate spente il 10/11.
- Dal 14/11 è armata una **campagna automatica consumi delle sei coppie CP HEAT/SPLIT HEAT**, con cron separato e ripresa persistente. È indipendente dall'interruttore "Prove automatiche" del motore, che resta spento. Stato, soglie, percorsi e disattivazione dopo sei acquisizioni in `procedure/ecm-engine.md`, sezione "Campagna automatica consumi"; prima di un comando climatico controllare se esiste un tentativo attivo.
- HA: `00-NILAN WRITE` è accesa in modalità isolata ACS, ricambio minimo e
  riscaldamento ambiente invernale (commit HA `4b1dff7`); il vecchio ramo ECM
  generale resta escluso. Arbitra la Compact P fra ACSe, ricambio e richiesta
  ambiente della `10`, e inoltra allo SPLIT la richiesta ambiente separata.
  `07-ECM RICAMBIO ARIA MINIMO` è accesa: sceglie automaticamente V2/V3/V4 di giorno,
  soltanto V2/V3 di notte, mai V1; decide CP HEAT/OFF dalla temperatura esterna e può
  acquisirla con un campionamento preventivo V2. L'obiettivo invernale è 2 volumi
  per finestra di 8 ore, ridotti a 1 con riserva batteria insufficiente e senza
  FV utile. Criterio e verifica in `procedure/config-home-assistant.md`.
  `06-ECM HUMIDITY OVERRIDE`, aggiornata
  nel commit HA `a25c615`, è attiva: sopra il 75% avvia autonomamente un blocco
  continuo fino a 90 minuti, V4 di giorno e V3 di sera/notte, con arresto sotto il
  70%; dopo 2 ore può fare richiami continui di 60 minuti, poi distanziati di 3 ore.
  Il ricambio `07` resta prioritario e autonomo: se ventila durante una pausa, quel
  lavoro rinvia il blocco umidità successivo senza alterare tempi o velocità della `07`.
  Il rientro sotto il 70% azzera la sequenza per un nuovo episodio; non esiste
  più lo stop fisso delle 17:30. Non usa mai V1. Dettagli e ripristino in
  `procedure/config-home-assistant.md`.
  `05-ECM ACS MANAGER`
  resta accesa; le altre automazioni decisionali ECM generali, salvo `10`, restano spente.
- HA: `10 - ECM INVERNO` accesa dal 10/11 e aggiornata fino al commit HA
  `1df11ac` del 25/11. Curva di assenza, anticipo serale e avvio in V1 in
  `procedure/config-home-assistant.md`.
  In AUTO usa le medie zona a 10 minuti e la matrice relativa a
  `input_number.t_min_inverno` (20,5 °C alla verifica): in fascia GIORNO zona
  giorno da T min a T min +0,5 e zona notte da T min −0,5 a T min; in fascia
  NOTTE zona giorno da T min −1 a T min −0,5 e zona notte da T min −1,5 a
  T min −1. Ogni zona mantiene separatamente il proprio recupero.
  Con energia favorevole può continuare fino al massimo comune modificabile
  `input_number.ecm_inverno_massimo_accumulo` (23,5 °C); il recupero sotto il
  minimo prevale sul budget energetico. Per il calore ambiente comanda solo
  Toshiba HEAT, lasciando a zero la richiesta CP ambiente: CP HEAT resta alle
  richieste indipendenti di ACS, umidità e ricambio. La velocità Split deriva
  dalle combinazioni E70/E80/E90 apprese, usa i trend separati 20/30/60 minuti,
  resta invariata almeno 15 minuti ed è limitata a V2 di notte. Il setpoint
  Toshiba parte dalla sonda ambiente +0,5 °C, viene controllato ogni minuto e
  può cambiare di 0,5 °C soltanto dopo finestre termiche di 30 minuti; massimo
  29 °C. Se la sonda manca all'avvio usa 29 °C solo come ripiego e si aggancia
  alla sonda quando torna; perdite successive della lettura non azzerano
  setpoint o apprendimento del ciclo. Prove automatiche del motore ancora spente.
- HA: il deploy da GitHub e il sync "GitHub Live" sono spenti dal 3/11, per decisione di Luca.
- HA: `automation.natale_tre_sonoff` è attiva dal 20/11 per la stagione
  2026–27; controlla `Albero`, `NATALE INGRESSO` e `NATALE ESTERNO`.
  Dal 7 gennaio 2027 non invia più
  comandi. Regole e verifica in `procedure/config-home-assistant.md`.
- HA: dal 22/11 sono attive le due automazioni di protezione della luce
  centrale termica: durata massima e avviso su iPhone per accensione senza
  pulsante rilevato. Entità, funzionamento e ripristino in
  `procedure/config-home-assistant.md`, sezione dedicata.

## Segreti (solo posizione)

- Token API di HA: `~/.config/ecm/ha_token` sul server (permessi 600).
- Deploy key GitHub del repo HA: `/config/.ssh/github_homeassistant` nel container.
- Token DuckDNS: nel compose dello stack Portainer "server" (variabili `TOKEN` e `DUCKDNS_TOKEN`).
- Password per le app Gmail: `~/.config/gmail-imap/app-password` di `home`
  sul mini PC (permessi `600`); il valore non è nel repository.
- Credenziali rclone per Box e MEGA: `/home/home/.config/rclone/rclone.conf` (permessi `600`).
- Segreti iniziali dello stack Nextcloud: `/home/home/nextcloud/.env` (permessi `600`); la password dell'account è stata cambiata dall'utente dopo l'installazione.

La fotografia e le procedure di diagnosi sono in `procedure/monitoraggio-server.md`. Interventi recenti: `diario/2026-11-03_08-interventi.md` (server, ECM, Nilan) e `diario/2026-11.md` (rete, Dingtian, crollo del 7/11). Questi valori sono una fotografia, non uno stato in tempo reale.

L'accesso SSH da questo PC come `home@192.168.1.100` è stato verificato il 17 novembre
2026: il server ha risposto come `minipc`, utente `home`.

## Posta (17/11/2026)

- Da questa chat si raggiunge il mini PC via SSH; da lì l'accesso IMAP TLS
  a `ing.rebesan@gmail.com` su `imap.gmail.com:993` è stato verificato
  dopo la rimozione del programma. Per la pulizia manuale si usa solo la
  Posta in arrivo e si sposta in `SVUOTA`; vedi `procedure/mail-svuota.md`.
- Il 17/11 il programma `/home/home/mail-svuota/`, il suo stato locale,
  il cron `MAIL_SVUOTA_DRY`, il container `mail-ollama`, il suo volume e
  l'immagine sono stati rimossi dal mini PC su richiesta di Luca. Il
  codice in `sorgenti/mail-svuota/` è storico e non è installato.
- Automazione Codex locale `pulizia-gmail-via-ssh` attiva in questa chat:
  controlli alle ore pari 00:00–22:00 Europe/Rome quando il PC è acceso. Non esiste
  un timer posta sul mini PC. La prima pulizia manuale ha spostato 18
  email a `SVUOTA`, tutte verificate con flag invariate; INBOX 830 e
  SVUOTA 61 alla verifica del 17/11.

# Inventario home server

Ultima verifica: 2026-11-10 15:07 (gestione ECM inverno corretta e attiva; macchina e rete restano alla verifica del 09/11).

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

## Rete

- Ethernet `enp2s0` (`68:1d:ef:66:29:75`) con prenotazione DHCP `.100` sul box (voce
  "hp-homeassistant", MAC aggiornato il 09/11). WiFi `wlp1s0` (`44:90:ba:32:32:bd`, `.25`)
  di riserva: networkd preferisce l'ethernet (metrica 100 contro 600). Se il cavo
  manca il server resta raggiungibile solo su `.25`. Config in `/etc/netplan/`.
- Box Iliad `192.168.1.254` (router e DHCP): `Rebesan_ILIAD` a 2,4 GHz sul canale 11 dal 7/11, `Rebesan_ILIAD5` a 5 GHz.
- Router EOLO `192.168.1.253`: secondo access point con gli stessi nomi di rete, DHCP spento.
- Accesso esterno: `https://ha.lrhub.duckdns.org` (nginx con certificato Let's Encrypt).
- Dettagli in `procedure/rete-wifi.md` e `procedure/duckdns-certificato.md`.

## Container (9/11)

- `homeassistant` (2026.11.0 dal 09/11; l'immagine precedente resta con il tag `2026.9.3`), `mosquitto`, `nginx`, `duckdns`, `letsencrypt`, `opt-portainer-1`, `crosschex-webapi` (Anviz), `hassconfigurator`.
- `ecm-engine`: vedi `procedure/ecm-engine.md`.
- Dal 09/11 il motore pubblica anche la resa ACS osservata per combinazione CP HEAT/SPLIT; conserva i dati sorgente, filtra periodi incerti e non usa questa stima per comandare le macchine.
- `dtbridge`: ponte tra i relè Dingtian e MQTT, che dal 7/11 serve tutti e 9 i relè (`~/dingtian/dtbridge`). Vedi `procedure/dingtian-ponte.md`.
- `dtdiag`: diagnostica dei Dingtian costruita come test da un altro agente (`~/dingtian/dtdiag`). Dopo la migrazione al ponte è superata in parte.
- Fermi di proposito: `grott`, `matter-hub`, `adguard`. `reolink-tv` è fermo dal 3/11 (non si sa se è voluto).
- Gli stack Portainer sono in `/var/lib/docker/volumes/opt_data/_data/compose/<n>/`; per leggerli servono i privilegi di root.

## Dispositivi in rete

- Gateway Higeco di Nilan e Toshiba: `192.168.1.171` (vedi `procedure/gateway-higeco.md`).
- Relè luci Dingtian DT-R008 (ESP32, in WiFi a 2,4 GHz): `.51`–`.58` e `.29`, in HA tramite `dtbridge`.
- Inverter Growatt, via l'integrazione `solax_modbus`; TV LG.
- Terminale Anviz: `.218`, non ancora montato al 7/11.

## Attività pianificate

- Crontab di `home`: rinnovo del certificato alle 04:17 (vedi `procedure/duckdns-certificato.md`).
- `ecm-engine`: un campione ogni 60 s, apprendimento ogni 15 minuti; dal 09/11 campiona anche bollitore alto/basso e marcatore della prova ACS indiretta. Dal 10/11 pubblica stime W separate CP/SPLIT; la resa termica delle coppie resta da misurare. Prove automatiche verificate spente il 10/11.
- HA: `00-NILAN WRITE` è accesa in modalità isolata ACS, ricambio minimo e
  riscaldamento ambiente invernale (commit HA `4b1dff7`); il vecchio ramo ECM
  generale resta escluso. Arbitra la Compact P fra ACSe, ricambio e richiesta
  ambiente della `10`, e inoltra allo SPLIT la richiesta ambiente separata.
  `07-ECM RICAMBIO ARIA MINIMO` è accesa: sceglie automaticamente V2/V3/V4 di giorno,
  soltanto V2/V3 di notte, mai V1; decide CP HEAT/OFF dalla temperatura esterna e può
  acquisirla con un campionamento preventivo V2. `06-ECM HUMIDITY OVERRIDE`, aggiornata
  nel commit HA `534cf90`, è attiva dal 09/11 alle 22:46: garantisce
  almeno 90 minuti e poi continua di giorno se il FV copre il carico con batteria buona
  (soglia iniziale 40%), oppure la sera/notte se la proiezione lascia almeno il 15% al
  mattino; altrimenti passa ai richiami di 15 minuti a inizio ora. `05-ECM ACS MANAGER`
  resta accesa; le altre automazioni decisionali ECM generali, salvo `10`, restano spente.
- HA: `10 - ECM INVERNO` corretta nel commit HA `d29a722` e accesa dal 10/11.
  In AUTO usa le medie zona a 10 minuti: di giorno il minimo è
  `input_number.t_min_inverno` (20 °C alla verifica) per entrambe; nella fascia
  climatica NOTTE il minimo della sola zona notte è un grado più basso. Ogni
  zona scesa sotto il proprio minimo resta in recupero fino a minimo +0,5 °C.
  Con energia favorevole può continuare fino al massimo comune modificabile
  `input_number.ecm_inverno_massimo_accumulo` (23,5 °C); il recupero sotto il
  minimo prevale sul budget energetico. Per il calore ambiente comanda solo
  Toshiba HEAT, lasciando a zero la richiesta CP ambiente: CP HEAT resta alle
  richieste indipendenti di ACS, umidità e ricambio. La velocità Split deriva
  dalle combinazioni E70/E80/E90 apprese, usa i trend separati 20/30/60 minuti,
  resta invariata almeno 15 minuti ed è limitata a V2 di notte. Alle 15:05 non
  chiedeva calore (zone 20,87/20,56 °C, SOC 10%, FV circa 72 W); Toshiba era
  spento e CP HEAT V2 lavorava soltanto per il ricambio. Prove automatiche del
  motore ancora spente.
- HA: il deploy da GitHub e il sync "GitHub Live" sono spenti dal 3/11, per decisione di Luca.

## Segreti (solo posizione)

- Token API di HA: `~/.config/ecm/ha_token` sul server (permessi 600).
- Deploy key GitHub del repo HA: `/config/.ssh/github_homeassistant` nel container.
- Token DuckDNS: nel compose dello stack Portainer "server" (variabili `TOKEN` e `DUCKDNS_TOKEN`).

La fotografia e le procedure di diagnosi sono in `procedure/monitoraggio-server.md`. Interventi recenti: `diario/2026-11-03_08-interventi.md` (server, ECM, Nilan) e `diario/2026-11.md` (rete, Dingtian, crollo del 7/11). Questi valori sono una fotografia, non uno stato in tempo reale.

L'accesso SSH è stato verificato da questo PC l'8 novembre 2026. La rete e i permessi disponibili possono variare tra sessioni e ambienti.

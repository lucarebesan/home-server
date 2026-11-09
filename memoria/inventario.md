# Inventario home server

Ultima verifica: 2026-11-09 (sezione ECM/ACS; le altre sezioni restano alla verifica precedente).

> **Migrazione in corso (09/11):** il nuovo server `minipc` (ethernet `.76`, WiFi `.25`) è
> pronto con i container creati ma non avviati. Fino al cutover i servizi girano
> sull'HP descritto qui sotto. Vedi `procedure/migrazione-minipc.md`.

- Nome host: `hp-homeassistant`.
- Sistema operativo: Linux.
- Indirizzo SSH: `192.168.1.100`, porta 22.
- Utente SSH: `home`.
- Alias SSH configurato su questo PC: `hp` (comando `ssh hp`).
- Macchina: HP Pavilion x360 Convertible, Intel Core i3-7100U (2 core, 4 CPU logiche), circa 3,2 GiB di RAM utilizzabile e 3,9 GiB di swap.
- Sistema rilevato: Ubuntu 26.04.1 LTS, kernel `7.0.0-42-generic`, architettura x86-64.
- Disco: HGST `HTS545050A7E680`, circa 466 GiB; filesystem principale ext4 su `/dev/sda3`, partizione EFI su `/dev/sda2`.
- Docker e SSH sono attivi. Home Assistant, MQTT (mosquitto), nginx, Portainer e altri servizi sono in container Docker. Per i nomi aggiornati usare `docker ps -a`.
- Per spegnere il server **non** fermare i singoli container: con `restart: unless-stopped` non ripartirebbero al boot. Usare `poweroff`.

## Rete

- Solo WiFi: 5 GHz `Rebesan_ILIAD5`, bloccata sul BSSID del box `3A:07:16:65:98:B0` (dall'8/11). La porta ethernet non è usata.
- Box Iliad `192.168.1.254` (router e DHCP): `Rebesan_ILIAD` a 2,4 GHz sul canale 11 dal 7/11, `Rebesan_ILIAD5` a 5 GHz.
- Router EOLO `192.168.1.253`: secondo access point con gli stessi nomi di rete, DHCP spento.
- Accesso esterno: `https://ha.lrhub.duckdns.org` (nginx con certificato Let's Encrypt).
- Dettagli in `procedure/rete-wifi.md` e `procedure/duckdns-certificato.md`.

## Container (8/11)

- `homeassistant` (versione tenuta apposta a 2026.9.3), `mosquitto`, `nginx`, `duckdns`, `letsencrypt`, `opt-portainer-1`, `crosschex-webapi` (Anviz), `hassconfigurator`.
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
- `ecm-engine`: un campione ogni 60 s, apprendimento ogni 15 minuti; dal 09/11 campiona anche bollitore alto/basso e marcatore della prova ACS indiretta. Prove automatiche verificate spente il 09/11.
- HA: `00-NILAN WRITE` è accesa dal 09/11 in modalità temporanea **solo ACS**, ora per INVERNO ed ESTATE; il vecchio ramo generale termina senza eseguire comandi. `05-ECM ACS MANAGER` resta accesa e prepara l'ACS serale. In inverno la guardia CP HEAT e il mantenimento del bollitore basso a 25 °C sono attivi. Le automazioni decisionali ECM generali, incluso `07` ricambio aria, sono spente per isolamento ACS. Vedi `diario/2026-11.md` per elenco e ripristino.
- HA: `10 - ECM INVERNO` ogni 5 minuti, solo in INVERNO (creata e spenta l'8/11, in attesa dell'ok di Luca).
- HA: il deploy da GitHub e il sync "GitHub Live" sono spenti dal 3/11, per decisione di Luca.

## Segreti (solo posizione)

- Token API di HA: `~/.config/ecm/ha_token` sul server (permessi 600).
- Deploy key GitHub del repo HA: `/config/.ssh/github_homeassistant` nel container.
- Token DuckDNS: nel compose dello stack Portainer "server" (variabili `TOKEN` e `DUCKDNS_TOKEN`).

La fotografia e le procedure di diagnosi sono in `procedure/monitoraggio-server.md`. Interventi recenti: `diario/2026-11-03_08-interventi.md` (server, ECM, Nilan) e `diario/2026-11.md` (rete, Dingtian, crollo del 7/11). Questi valori sono una fotografia, non uno stato in tempo reale.

L'accesso SSH è stato verificato da questo PC l'8 novembre 2026. La rete e i permessi disponibili possono variare tra sessioni e ambienti.

# Inventario home server

Ultima verifica: 2026-11-08.

- Nome host: `hp-homeassistant`.
- Sistema operativo: Linux.
- Indirizzo SSH: `192.168.1.100`, porta 22.
- Utente SSH: `home`.
- Alias SSH configurato su questo PC: `hp` (comando `ssh hp`).
- Macchina: HP Pavilion x360 Convertible, Intel Core i3-7100U (2 core, 4 CPU logiche), circa 3,2 GiB di RAM utilizzabile e 3,9 GiB di swap.
- Sistema rilevato: Ubuntu 26.04.1 LTS, kernel `7.0.0-42-generic`, architettura x86-64.
- Disco: HGST `HTS545050A7E680`, circa 466 GiB; filesystem principale ext4 su `/dev/sda3`, partizione EFI su `/dev/sda2`.
- Docker e SSH sono attivi. Home Assistant, MQTT (mosquitto), nginx, Portainer e altri servizi sono in container Docker. Per i nomi aggiornati usare `docker ps -a`.

## Container (8/11)

`homeassistant`, `mosquitto`, `nginx`, `duckdns`, `letsencrypt`, `opt-portainer-1`, `crosschex-webapi`, `hassconfigurator`, `ecm-engine` (vedi `procedure/ecm-engine.md`), `dtbridge` (esperimento sui relè dingtian), `dtdiag`. `reolink-tv` è fermo dal 3/11.

## Dispositivi in rete

- Gateway Higeco di Nilan e Toshiba: `192.168.1.171` (vedi `procedure/gateway-higeco.md`).
- Box Iliad: `192.168.1.254`, WiFi `Rebesan_ILIAD` (2,4 GHz sul canale 11 dal 7/11).
- Relè luci dingtian (ESP32, in WiFi): `.51`–`.58` e `.29`.
- Terminale Anviz: `.218` (non ancora montato al 7/11).

## Attività pianificate

- Crontab di `home`: rinnovo del certificato alle 04:17 (vedi `procedure/certificato-duckdns.md`).
- `ecm-engine`: campione ogni 60 s, apprendimento ogni 15 minuti, prove automatiche spente.
- HA: `00-NILAN WRITE` ogni 5 minuti (spenta dal 7/11), `07` ricambio aria con finestre 01/09/17.

## Segreti (solo posizione)

- Token API di HA: `~/.config/ecm/ha_token` sul server (permessi 600).
- Deploy key GitHub del repo HA: `/config/.ssh/github_homeassistant` nel container.

## Rete

- Solo WiFi: 5 GHz `Rebesan_ILIAD5`, bloccata sul BSSID del box `3A:07:16:65:98:B0`
  (dall'08/11). La porta ethernet non è usata.
- iliadbox `192.168.1.254` (router e DHCP); router EOLO `192.168.1.253`, usato come secondo
  access point con il DHCP spento. Dettagli in `procedure/rete-wifi.md`.
- Accesso esterno: `https://ha.lrhub.duckdns.org` (nginx + certificato Let's Encrypt).
  Vedi `procedure/duckdns-certificato.md`.

## Container principali (08/11)

- `homeassistant` (versione bloccata a 2026.9.3), `mosquitto`, `nginx`, `letsencrypt`,
  `duckdns`, `opt-portainer-1`, `crosschex-webapi` (Anviz), `hassconfigurator`.
- `dtbridge`: ponte tra i relè Dingtian e MQTT (`~/dingtian/dtbridge`). Vedi
  `procedure/dingtian-ponte.md`.
- `dtdiag`: diagnostica dei Dingtian costruita come test da un altro agente
  (`~/dingtian/dtdiag`); dopo la migrazione al ponte è in parte superata.
- `ecm-engine`: servizio di Mattia per la logica ECM (Nilan, ACS). Non documentato qui.
- Fermi di proposito: `grott`, `matter-hub`, `adguard`. `reolink-tv` è fermo dal 03/11.
- Gli stack Portainer stanno in `/var/lib/docker/volumes/opt_data/_data/compose/<n>/`
  (servono privilegi di root per leggerli).

## Dispositivi gestiti

- 9 relè WiFi Dingtian DT-R008 (luci), `192.168.1.51`–`58` e `.29`, in HA tramite
  `dtbridge`.
- Gateway Nilan/Higeco `192.168.1.171`; inverter Growatt via `solax_modbus`; TV LG; Anviz
  C2 `192.168.1.218` (non ancora montato).

## Altro

- La configurazione di Home Assistant è nel repository GitHub `home-assistant-config` di
  Luca. Il deploy da GitHub e il sync "GitHub Live" sono spenti dal 03/11 per decisione
  di Luca.
- Crontab di `home`: rinnovo del certificato alle 04:17 (vedi la procedura).
- Per spegnere il server **non** fermare i singoli container: con
  `restart: unless-stopped` non ripartirebbero al boot.

La fotografia e le procedure di diagnosi sono in `procedure/monitoraggio-server.md`. Interventi recenti: `diario/2026-11-03_08-interventi.md`. Questi valori sono una fotografia, non uno stato in tempo reale.

L'accesso SSH è stato verificato da questo PC l'8 novembre 2026. La rete e i permessi disponibili possono variare tra sessioni e ambienti.

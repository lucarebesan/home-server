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

La fotografia e le procedure di diagnosi sono in `procedure/monitoraggio-server.md`. Questi valori sono una fotografia, non uno stato in tempo reale.

L'accesso SSH è stato verificato da questo PC l'8 novembre 2026. La rete e i permessi disponibili possono variare tra sessioni e ambienti.

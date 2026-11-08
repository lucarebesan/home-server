---
name: check-server
description: Controllo generale in sola lettura del server di casa hp-homeassistant (Home Assistant, container, relè luci, rete, DuckDNS, certificato). Usala per "check", "come sta il server", "è ripartito tutto?", dopo un crollo di rete o un riavvio.
---

# Check del server

Controllo **in sola lettura**: non riavviare, non modificare, non cancellare niente. Se trovi
un problema, descrivilo e proponi l'intervento; agisci solo con l'ok esplicito
dell'utente.

Accesso: `ssh hp`, oppure `ssh home@192.168.1.100` se l'alias non c'è. `home` non ha sudo
senza password: un comando che richiede sudo va consegnato all'utente come one-liner
`ssh -t hp '…'`.

## Passi

1. **Sistema:** comandi della sezione "Controllo rapido" di
   `memoria/procedure/monitoraggio-server.md`. Aggiungi `journalctl --list-boots | tail -3`
   per vedere eventuali riavvii.
2. **Riavvio recente?** Se il boot è recente, guarda come si è chiuso il precedente con
   `journalctl -b -1 -n 30`: `systemd-reboot` e una chiusura ordinata indicano un riavvio
   richiesto (anche dal menu del desktop GNOME, che compare come `gnome-session` /
   `endSessionDialog`).
3. **Container:** `docker ps -a`. Devono risultare attivi `homeassistant`, `mosquitto`,
   `nginx`, `duckdns`, `letsencrypt`, `dtbridge`, `ecm-engine`, `crosschex-webapi`,
   `opt-portainer-1`. Quelli fermi di proposito sono elencati in `memoria/inventario.md`.
4. **Home Assistant:** `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8123/`
   deve dare 200.
5. **Relè luci:** stato del ponte, che deve dare `9/9` raggiungibili:
   `docker exec mosquitto mosquitto_sub -h 127.0.0.1 -t dtbridge_diag/global/state -C 1`.
   Se non sono 9/9, oppure se i buchi lunghi sono molti, usa la skill `luci-dingtian`.
6. **WiFi del server:** `iw dev wlo1 link` deve mostrare il BSSID `3a:07:16:65:98:b0`
   (il box) con segnale migliore di −60 dBm. Prova anche `ping -c 10 192.168.1.254`
   (normale: meno di 5 ms). Se è anomalo, usa la skill `rete-wifi`.
7. **Accesso esterno:** `docker logs --tail 3 duckdns` deve dire "successful" (non "KO").
   Verifica anche la scadenza del certificato servito:
   `echo | openssl s_client -connect 127.0.0.1:443 -servername ha.lrhub.duckdns.org 2>/dev/null | openssl x509 -noout -enddate`.
   Se mancano meno di 20 giorni, usa la skill `certificato-duckdns`.
8. **Risorse:** pressione I/O e memoria con `cat /proc/pressure/io /proc/pressure/memory`.
   Il disco è meccanico e lento: avg300 "some" sotto il 10% è normale.

## Rapporto

Rispondi con una tabella "Funziona / Da guardare". Per ogni anomalia indica il dato
osservato e l'ipotesi, tenendoli separati. Chiudi con le azioni proposte e chiedi
quale eseguire. Se emerge qualcosa di nuovo e utile, registralo con la skill
`aggiorna-memoria`.

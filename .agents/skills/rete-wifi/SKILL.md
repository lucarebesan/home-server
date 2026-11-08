---
name: rete-wifi
description: Diagnosi della rete di casa (iliadbox, router EOLO usato come access point, WiFi del server). Usala per "è crollata la rete", dispositivi che cadono tutti insieme, server lento o irraggiungibile, modifiche a canali e WiFi.
---

# Rete e WiFi

Riferimento: `memoria/procedure/rete-wifi.md` (apparati, configurazione attuale,
lezioni, accesso alle interfacce).

## Regole

- Le modifiche al box o al router EOLO cambiano la rete di tutta la casa: proponile e
  aspetta l'ok. Annota l'ora di ogni modifica, per poterla separare dagli effetti.
- **Non portare il 5 GHz del box a 80 MHz** e non cambiare impostazioni che riavviano il
  5 GHz senza motivo: l'HP ha un collegamento pessimo su alcuni canali, e durante un
  riavvio del 5 GHz finiva sull'EOLO debole. Ora è bloccato sul BSSID del box.
- Il DHCP del router EOLO deve restare **spento**. Due server DHCP in rete fanno crollare
  tutto.
- Le password non si leggono e non si annotano.

## Diagnosi di un crollo

1. **Dal server:**
   - `journalctl --since "<ora>" -u NetworkManager` e `journalctl -k | grep wlo1`: cerca
     `deauthenticated`, `authentication timed out`, molti `missed beacons`;
   - `nmcli -f SSID,BSSID,CHAN,SIGNAL dev wifi list` per vedere gli access point visibili;
   - `nmcli -f DHCP4 dev show wlo1` per vedere chi ha dato l'indirizzo (deve essere
     `192.168.1.254`).
2. **Dal box** (serve il login dell'utente sulla pagina `http://192.168.1.254`): l'API
   `/api/v16/system/` dà l'uptime (un riavvio recente fa perdere il registro),
   `/api/v16/connection/logs/`, `/api/v16/wifi/ap/` (canali), `/api/v16/wifi/ap/0/stations/`
   (dispositivi a 2,4 GHz, segnale, da quanto sono agganciati).
3. **Dal ponte dei relè:** i buchi di tutti i relè nello stesso momento datano il
   crollo (`docker logs dtbridge`).
4. Ricostruisci una cronologia (ora → evento → fonte) e distingui tra causa accertata
   e ipotesi.

## Accesso alle pagine web con un browser controllato da agente

Se il Chrome dell'agente è già occupato da un'altra sessione, avvia un'istanza separata:
`--user-data-dir=/tmp/chrome-box --remote-debugging-port=9333 --remote-debugging-address=127.0.0.1`.
L'utente fa il login e la pagina si legge via DevTools Protocol. Non chiudere il
browser di altre sessioni.

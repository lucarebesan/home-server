# Rete e WiFi di casa

Ultima verifica: 2026-11-08 (apparati); 2026-11-09 per il server, ora mini PC.

## Apparati

| Apparato | IP | Ruolo | Note |
|---|---|---|---|
| iliadbox (r1, fw 4.12.4) | 192.168.1.254 | router, DHCP, WiFi principale | 2,4 GHz `Rebesan_ILIAD`, canale **11 fisso**, 20 MHz; 5 GHz `Rebesan_ILIAD5`, canale automatico, 160 MHz con DFS; sicurezza WPA2/WPA3 transition; risparmio energetico WiFi **spento** (dal 07/11) |
| Router EOLO ADB VE4412 | 192.168.1.253 (statico) | secondo access point "tipo mesh", via cavo | WAN scollegata, **DHCP spento**, stessi SSID del box, sicurezza **WPA3-Personal-Transition** (dall'08/11), 2,4 GHz canale automatico, 5 GHz canale 36 a 80 MHz, mesh EOLO acceso |
| Server mini PC (`minipc`, dal 09/11) | 192.168.1.100 ethernet, 192.168.1.25 WiFi | Home Assistant e servizi | **ethernet `enp2s0` principale** (metrica 100); WiFi `wlp1s0` di riserva (metrica 600) su `Rebesan_ILIAD5`; rete gestita da netplan + systemd-networkd, **niente NetworkManager** |
| Server HP (spento, riserva) | — | ex server | solo WiFi a 5 GHz, bloccato sul BSSID del box (vedi sotto) |

Il router EOLO non forma un vero mesh con il box: il suo mesh funziona solo tra
apparecchi EOLO. Ripete soltanto gli stessi nomi di rete. Dal suo pannello non si può
spegnere né rinominare solo il 5 GHz (un solo SSID e un solo interruttore per tutto il
WiFi). Per disattivare il mesh EOLO il router chiede un riavvio: l'08/11 si è deciso di
lasciarlo acceso.

Dispositivi a 2,4 GHz importanti: 9 relè Dingtian, ~12 tapparelle e frangisole, meter,
Echo, Yi cam. Al controllo dell'08/11 i 9 relè erano tutti agganciati al box.

## Server bloccato sul box

**Mini PC (09/11):** **nessun blocco sul BSSID.** `/etc/netplan/00-installer-config.yaml`
ha solo `Rebesan_ILIAD5` con password e DHCP; `60-ethernet.yaml` mette l'ethernet a metrica
100. Il WiFi di riserva risultava agganciato al 5 GHz del box (`3a:07:16:65:98:b0`,
`networkctl status wlp1s0`), ma può passare all'EOLO. Con l'ethernet collegata pesa poco;
se il server dovesse restare solo in WiFi, valutare `bssid:` sotto l'access point in netplan.
I file netplan sono leggibili solo da root; senza sudo si leggono in sola lettura con
`docker run --rm -v /etc/netplan:/n:ro alpine cat /n/00-installer-config.yaml` (contiene la
password WiFi: non copiarla).

**HP (storico, valido se si torna all'HP):** dall'08/11 la connessione `Rebesan_ILIAD5` dell'HP ha
`802-11-wireless.bssid = 3A:07:16:65:98:B0` (5 GHz del box). Motivo: quando il 5 GHz del
box si riavvia (riavvio, cambio canale, DFS), l'HP si agganciava all'EOLO, che dalla sua
posizione ha un segnale pessimo (fino a −87 dBm).

- Verifica: `nmcli -g 802-11-wireless.bssid connection show Rebesan_ILIAD5` e
  `iw dev wlo1 link`.
- Ripristino, con sudo: `nmcli connection modify Rebesan_ILIAD5 802-11-wireless.bssid ""`.
- **Se si sostituisce il box** l'HP non si collega finché non si toglie il blocco.

## Lezioni (fatti osservati)

- **Non portare il 5 GHz del box a 80 MHz.** L'08/11 ci si è provato per evitare la
  sovrapposizione con il canale 36 dell'EOLO: il box è passato al canale 100 e l'HP ha
  avuto un collegamento pessimo (ping 400–1500 ms, ricezione a 6,5 Mbit/s). Il ponte
  perdeva 20–40 letture al minuto. Ripristinato 160 MHz dopo 7 minuti.
- **Canale 2,4 GHz e risparmio energetico del box** cambiati l'07/11 (da 6 a 11; risparmio
  spento): i riavvii dei relè non sono cambiati.
- **Sicurezza diversa tra box ed EOLO** (WPA2 contro WPA2/WPA3): il 07/11 l'HP veniva
  rifiutato dall'EOLO con codice 30. Allineata l'08/11.

## Accesso alle interfacce

- **iliadbox OS:** `http://192.168.1.254`. Il nome `myiliadbox.iliad.it` ha un certificato di
  una CA privata Iliad che i browser rifiutano. Dopo il login l'API `/api/v16/...` (per
  esempio `wifi/ap/`, `wifi/ap/0/stations/`, `system/`, `connection/logs/`) si può leggere
  con `fetch` dalla pagina. Il registro delle connessioni riparte da zero a ogni riavvio
  del box.
- **Router EOLO:** `http://192.168.1.253`; le credenziali sono sull'etichetta. Le
  impostazioni Wi-Fi si applicano con il pulsante "Applica"; la sessione scade dopo pochi
  minuti.
- **Dal mini PC** (niente NetworkManager, niente `nmcli`): `networkctl status enp2s0 wlp1s0`
  (stato, access point, DHCP), `ip route` (da quale interfaccia esce),
  `journalctl --since "<ora>" -u systemd-networkd -u netplan-wpa-wlp1s0` e
  `journalctl -k | grep -E 'enp2s0|wlp1s0'`. `wpa_cli` e la scansione degli access point
  richiedono sudo.
- **Dall'HP** (spento, riserva): `nmcli -f SSID,BSSID,CHAN,SIGNAL dev wifi list` (la scansione forzata
  richiede privilegi) e `iw dev wlo1 station dump` (ritrasmissioni, bitrate).

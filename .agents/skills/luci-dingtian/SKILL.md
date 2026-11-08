---
name: luci-dingtian
description: Diagnosi dei relè luci Dingtian e del ponte dtbridge (luci che si spengono da sole, relè non disponibili in HA, buchi lunghi, riavvii a ondate, pulsanti che non aggiornano HA). Usala per qualsiasi problema alle luci o ai relè.
---

# Luci e relè Dingtian

Prima di agire leggi `memoria/procedure/dingtian-ponte.md`: contiene la tabella dei
relè, il funzionamento del ponte, i protocolli e il ripristino. Documentazione
completa, sorgenti e backup sono sul server in `~/dingtian/`.

## Regole (obbligatorie)

- Sui relè sono ammesse solo letture: `main.cgi`, `relay_load.cgi`, `relay_cgi_load.cgi`,
  `ip_watchdog.cgi`, Modbus in lettura.
- **Mai** `reboot.cgi`, `default.cgi`, `self_destruct.cgi`, `userset.cgi`, `mainset.cgi`.
- `relay_save.cgi` e i comandi alle uscite (accendere o spegnere luci) solo con l'ok
  esplicito dell'utente. Prima di modificare una configurazione salva il backup di
  `relay_load.cgi`.
- **Non cambiare `power_failure_recovery`**: l'utente ha deciso di lasciarlo così
  (2026-11-08).
- Non modificare la configurazione di Home Assistant (è nel repo di Luca) per
  "riparare" i relè.

## Diagnosi

1. **Stato del ponte:** `docker logs --since 30m dtbridge | grep -E "BUCO|OFFLINE|fallita"`
   e i sensori `dtbridge_diag/#` su MQTT (in HA: dispositivo "Dingtian ponte").
2. **Tutti insieme o uno solo?** Molti relè giù nello stesso secondo indicano la rete o il
   server: controlla `iw dev wlo1 link` e `ping 192.168.1.254`, poi usa la skill
   `rete-wifi`. Un solo relè indica il relè o la sua copertura.
3. **Riavvio o WiFi persa?** Dalla pagina del box, una nuova associazione appena
   avvenuta dopo il buco indica un riavvio (vedi `memoria/procedure/rete-wifi.md`).
   Un riavvio dura 30–80 s. I relè con ripristino stato su "No" (Giorno1, Sottotetto4,
   Giardino9) dopo un riavvio spengono le loro luci.
4. **Una luce cambia da sola?** Nel database del recorder di HA (in sola lettura: aprilo
   con `?mode=ro` e interroga una sola entità alla volta, perché il DB è grande e il disco
   è lento) guarda l'ingresso `binary_sensor.<relè>_iN` nei 2 s prima del cambio (cioè il
   pulsante a muro), oppure gli eventi `call_service` (`homeassistant.turn_off` senza
   utente indica Alexa/emulated_hue).
5. **Il ponte non risponde:** `docker ps` e `docker logs --tail 50 dtbridge`. Per
   riavviarlo (`cd ~/dingtian/dtbridge && docker compose -p dtbridge up -d`) chiedi
   prima all'utente.

Riporta i fatti (orari, relè coinvolti, durate) separati dalle ipotesi. Aggiorna la
memoria con la skill `aggiorna-memoria` se scopri qualcosa di nuovo.

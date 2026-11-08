---
name: config-home-assistant
description: Modificare la configurazione di Home Assistant del server (automazioni, package, template, script in /opt/homeassistant/config) e ricaricarla senza riavviare. Usala per cambiare un'automazione, correggere errori nel log di HA o aggiungere entità YAML.
---

# Configurazione di Home Assistant

Procedura dettagliata: `memoria/procedure/config-home-assistant.md`.

## Regole

- La configurazione è il repository git `lucarebesan/home-assistant-config` (branch `main`),
  in `/opt/homeassistant/config` (`/config` nel container). I file sono di root: si
  modificano con `docker cp`/`docker exec` nel container `homeassistant`, come
  descritto nella procedura.
- Ogni modifica va anche **committata e pushata** su quel repository (deploy key nel
  container: `/config/.ssh/github_homeassistant`), altrimenti un futuro deploy da GitHub
  la cancella. Nel working tree ci sono aggiornamenti HACS mai committati
  (`custom_components/`): non includerli nei commit.
- Il deploy da GitHub e il sync "GitHub Live" sono **spenti dal 3/11 per decisione di
  Luca**: non riaccenderli senza chiedere. Stessa cosa per le automazioni spente a mano
  (per esempio `00-NILAN WRITE`, `luci_*`).
- Prima di ricaricare lancia sempre `check_config`. Ricarica il dominio interessato via
  API (`automation/reload`, ecc.) invece di riavviare. Il riavvio completo dura minuti e
  va concordato.
- Il token API di HA (`~/.config/ecm/ha_token`) non va mai stampato né copiato: usalo
  solo dentro i comandi remoti come `$(cat ~/.config/ecm/ha_token)`.
- Il database del recorder (~3 GB) sta su disco meccanico: solo query in sola lettura
  (`?mode=ro`), per singola entità e con un `timeout`.

## Dopo

Verifica gli errori nel log (`/opt/homeassistant/config/home-assistant.log`, ripulendo i
codici colore) e registra l'intervento con la skill `aggiorna-memoria`.

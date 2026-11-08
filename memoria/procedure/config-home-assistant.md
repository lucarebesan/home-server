# Modificare la configurazione di Home Assistant

Ultima verifica: 2026-11-08.

## Prerequisiti

- Accesso `ssh hp` (utente `home`). L'utente non ha sudo senza password.
- La configurazione è in `/opt/homeassistant/config`, montata nel container `homeassistant` come `/config`. È un repository git (`lucarebesan/home-assistant-config`, branch `main`).
- I file sono di root: `home` non li può modificare direttamente.
- Token API di HA (long-lived) in `~/.config/ecm/ha_token` sul server, permessi 600. Non stamparlo e non copiarlo altrove: usarlo solo come `$(cat ~/.config/ecm/ha_token)` dentro i comandi remoti.

## Passaggi

1. Copiare il file sul PC, modificarlo e ricopiarlo nel container:
   ```sh
   scp hp:/opt/homeassistant/config/automations/nilan/07_ecm_ricambio_aria_minimo.yaml .
   # modifica locale
   scp 07_ecm_ricambio_aria_minimo.yaml hp:/tmp/
   ssh hp 'docker cp /tmp/07_ecm_ricambio_aria_minimo.yaml homeassistant:/config/automations/nilan/ && docker exec homeassistant chown 0:0 /config/automations/nilan/07_ecm_ricambio_aria_minimo.yaml'
   ```
   Mantenere i permessi 644.
2. Controllare la configurazione:
   ```sh
   ssh hp 'docker exec homeassistant python -m homeassistant --script check_config -c /config'
   ```
3. Ricaricare senza riavviare (sostituire il servizio secondo il caso: `automation/reload`, `input_select/reload`, `input_number/reload`, `template/reload`, `command_line/reload`):
   ```sh
   ssh hp 'curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $(cat ~/.config/ecm/ha_token)" http://127.0.0.1:8123/api/services/automation/reload'
   ```
4. Commit e push **dall'interno del container**: lì c'è la deploy key. Il quoting inline si rompe, quindi conviene uno script passato da stdin.
   ```sh
   cat > /tmp/commit.sh <<'EOF'
   cd /config
   G="git -c safe.directory=/config -c user.name=NOME -c user.email=EMAIL"
   $G add automations/nilan/07_ecm_ricambio_aria_minimo.yaml
   $G commit -m "messaggio"
   GIT_SSH_COMMAND="ssh -i /config/.ssh/github_homeassistant -o UserKnownHostsFile=/config/.ssh/known_hosts -o StrictHostKeyChecking=yes" $G push origin main
   EOF
   ssh hp 'docker exec -i homeassistant sh -s' < /tmp/commit.sh
   ```
   - Nel container l'identità git non è configurata: passarla con `-c` (per esempio quella dell'ultimo commit, `git log -1 --format='%an %ae'`).
   - Senza `GIT_SSH_COMMAND` il push fallisce con "Host key verification failed".
   - **Aggiungere solo i file modificati.** In `custom_components/` ci sono aggiornamenti HACS mai committati (alexa_media, solax_modbus, sonoff): non vanno inclusi.

## Verifica

- Leggere lo stato delle entità interessate via API: `GET /api/states/<entity_id>`.
- `docker logs --since 10m homeassistant` senza nuovi errori.

## Attenzioni

- **Mai `docker stop` su HA prima di spegnere il server**: dopo il riavvio il container resta fermo. Per spegnere usare `poweroff`; per riavviare HA usare `docker restart homeassistant`.
- Il database del recorder (`/config/home-assistant_v2.db`, circa 3 GB su HDD lento) va interrogato solo in sola lettura (`file:...?mode=ro`), un'entità alla volta, senza `COUNT(*)` né scansioni complete: fanno salire l'I/O di tutto il server.
- Lo storico del recorder dura 7 giorni; le statistiche orarie (`statistics`) restano più a lungo.
- Le dashboard storage si possono aggiornare senza riavvio via WebSocket `lovelace/config/save`: vedi `dashboard-ecm-v2.md`.

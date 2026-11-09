# Modificare la configurazione di Home Assistant

Ultima verifica: 2026-11-09 (isolamento ACS; commit HA `249e12e`).

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

## Isolamento ACS temporaneo dal 09/11

Il commit HA `8e156b3` lascia attiva `00-NILAN WRITE` con un blocco iniziale che
scrive solo ACS e, durante una prova temporizzata, CP HEAT; il vecchio ramo
ECM è irraggiungibile. `05 ECM ACS MANAGER` gestisce anche la copertura
serale con resistenza; `packages/ecm_acs_prova_caldo.yaml` contiene guardia
e helper. Le altre automazioni decisionali ECM restano spente: l'elenco e i
risultati della prima prova sono nel diario del 09/11.

Dal commit HA `423b2da` il blocco ACS della WRITE opera in entrambe le
stagioni. In INVERNO inoltra il setpoint tecnico 20 °C per escludere l'ACS
dedicata, il setpoint della resistenza e CP HEAT solo nei cicli sorvegliati.
In ESTATE inoltra il setpoint ACS dedicata limitato a 25–50 °C e usa
ventilazione V1 solo quando il bollitore basso è sotto quel setpoint e le
zone non sono in protezione freddo. Con protezione freddo usa 25 °C,
ventilazione OFF e consente la resistenza solo dopo aver verificato la CP
dedicata al minimo e il ventilatore fermo. I comandi climatici ECM generali
restano esclusi. La WRITE non inoltra riscaldamenti se il bollitore alto o
basso è a 60 °C; se la resistenza è ancora alta e la parte alta raggiunge
60 °C, invia il setpoint di base 38 °C. Il limite macchina letto da HA era
80 °C il 09/11: la soglia software non garantisce assenza di inerzia termica.

Per il **minimo invernale del bollitore basso**, la nuova automazione avvia
CP HEAT V2 sotto 25 °C solo con compressore e ventilatore fermi, ACS dedicata
a 20 °C, resistenza a 38 °C, zone sotto 23,5 °C e sensori validi. Ogni ciclo
dura almeno 15 e al massimo 20 minuti (dal commit HA `249e12e`, per evitare
cicli brevi del compressore): la guardia lo ferma a 25 °C solo dopo 15 minuti,
mentre gli stop di sicurezza restano immediati (aria immessa fredda rispetto alle medie delle zone o per dati invalidi.
Una nuova prova attende almeno 30 minuti dopo la scadenza del ciclo
precedente. Verificare `input_boolean.ecm_acs_minimo_t12_attivo`, inizio/fine
del ciclo, ventilazione V2, bollitore basso e motivo di arresto nel logbook.
Questa soglia è un tentativo di recupero, non una garanzia fisica di 25 °C
in ogni condizione.

Per controllare la preparazione serale, leggere in HA
`input_number.ecm_acs_ora_uso_appresa` (ore decimali),
`input_number.ecm_acs_campioni_appresi`, bollitore alto/basso e
`input_number.ecm_acs_resa_t11_resistenza`. La scadenza della `05` è
30 minuti prima dell'ora appresa se ci sono almeno tre eventi validi;
in caso contrario vale 17:10. L'avvio effettivo è anticipato in base ai
gradi mancanti e alla resa conservativa della resistenza. Verificare il
comando `input_number.acs_r_set` e il setpoint reale della CP, poi la
temperatura del bollitore alto alla scadenza. Il ramo FV/batteria può
riscaldare prima dell'avvio di copertura.

Dal commit HA `ad17e6f` la copertura invernale usa il bollitore basso per
scegliere l'obiettivo del bollitore alto: **50 °C** con basso <30 °C,
**47 °C** con basso da 30 a <35 °C, **44 °C** con basso ≥35 °C (anche
oltre 40 °C, per scelta esplicita di Luca). Il setpoint della resistenza
coincide con l'obiettivo: 50/47/44 °C (corretto nel commit HA `a60d704`); al raggiungimento
dell'obiettivo torna al valore di base 38 °C. La scadenza resta 30 minuti
prima dell'ora di utilizzo appresa.

Dal commit HA `249e12e` (richiesta di Luca) la preparazione serale si fa **una volta
al giorno**: raggiunto l'obiettivo, la `05` scrive l'ora in
`input_datetime.ecm_acs_backup_sera_completato` e la resistenza resta a 38 °C fino
al giorno dopo. Unica eccezione: bollitore alto sotto 38 °C, recupero con resistenza
fino a 42 °C a qualsiasi ora, anche dalla rete (`input_boolean.ecm_acs_recupero_38_attivo`),
poi di nuovo 38 °C. L'accumulo con FV/batteria nella finestra 10:00–17:30 resta
possibile anche dopo. Il controllo "completata oggi" usa `>` mezzanotte: un helper
appena creato vale oggi alle 00:00 e non deve contare.

**Setpoint aria della Compact P (dal commit HA `249e12e`).** La Nilan salva ogni
scrittura, quindi la WRITE scrive il setpoint aria solo quando serve. A riposo è
fisso a **17 °C** (in riscaldamento il compressore non parte) e viene scritto una
volta sola. Durante una prova CP HEAT si scrive all'inizio (sensore ambiente CP +
metà isteresi + 0,1 °C) e poi solo se il compressore spento non potrebbe partire o
quello acceso sta per fermarsi (termostato: acceso sotto setpoint − isteresi/2,
spento sopra setpoint + isteresi/2). Anche la guardia, quando ferma, scrive 17 °C.

Prima di un'altra prova, verificare stagione INVERNO, setpoint reale ACS
compressore 20 °C, resistenza non attiva, ventilazione CP spenta, sensori
bollitore/aria/zone validi, `09 ECM MANUALE` e prove automatiche del motore
spenti. Impostare gli helper `input_datetime.ecm_acs_prova_caldo_inizio`
e `_fine`, poi accendere `input_boolean.ecm_acs_prova_caldo_attiva`. La WRITE
usa velocità `input_number.ecm_acs_prova_caldo_velocita` (V2 predefinita) e
la formula di setpoint/isteresi di `09`; la guardia ferma dopo la scadenza
o se l'aria immessa resta sotto le medie delle zone. Verificare dopo lo stop
compressore OFF, ventilazione OFF e setpoint aria di arresto.

Per sospendere subito la gestione automatica, spegnere prima
`automation.nilan_write` via API HA e verificare le macchine. Prima di
ripristinare la vecchia WRITE generale, lasciare l'automazione spenta,
ripristinare i file dal commit precedente `7ba3f03` in una copia di lavoro,
eseguire `check_config` e `automation.reload`, poi decidere esplicitamente
quali decisori ECM riaccendere. Non riaccendere la vecchia WRITE con tutte
le automazioni ECM ancora in stato sconosciuto.

# Dashboard ECM v2

Ultima verifica: 2026-11-09 17:16 (deploy del restyling e della tab Albero).

## Scopo

Dashboard storage separata dalla Overview, `url_path` `ecm-v2`. Tab: Stato, Albero, Impostazioni, Diagnostica, Apprendimento (dal 09/11 sera; prima senza Albero). La vista ECM della Overview (`lovelace.lovelace`) resta intatta.

## Sorgente

`sorgenti/ha-ecm-v2/ecm_v2.yaml` in questo repository (fonte di verità). `build.py` (richiede `node` e PyYAML: `uv run --with pyyaml python build.py`) lo converte in JSON e controlla i template JavaScript; i template Jinja vanno provati a parte con `POST /api/template`.

File generati (`lovelace.ecm_v2`, `entities_v2.txt`) e backup locali (`*.bak*`, dump Lovelace) sono esclusi da git.

## Deploy senza riavvio

`sorgenti/ha-ecm-v2/deploy_ws.py` gira dentro il container `homeassistant` (che ha aiohttp) e ha tre modi: `list`, `backup`, `save <file>`. Usa il token in `~/.config/ecm/ha_token`, letto sul server. Prima di ogni salvataggio fa un backup in `~/backup-ecm-v2-<data>.json` sul server.

Le istruzioni d'uso sono nell'intestazione dello script. In sintesi: copiare JSON e script sul server, poi `docker exec -i -e TOKEN="$(cat ~/.config/ecm/ha_token)" homeassistant python3 - ... < deploy_ws.py`.

Prima di salvare, confrontare la build con il backup appena fatto (vista per vista): se il live è stato modificato a mano dopo l'ultima build, il salvataggio lo sovrascrive. Se differiscono parti che non si stanno toccando, allineare prima il sorgente, oppure partire dal backup e sostituire solo le card cambiate.

## Verifica

Aprire `/ecm-v2/stato`, `/ecm-v2/albero` e le altre tab e controllare che le card si vedano (anche da telefono). Il risultato del salvataggio deve essere `"success": true`.

## Ripristino

Salvare via WebSocket il JSON di backup più recente.

## Note

- La card "Da misurare" (tab Apprendimento) divide le righe per l'attributo `sezione` pubblicato da `ecm-engine` (vedi `ecm-engine.md`).
- Nella stessa tab la card "Modalità ACS inverno" mantiene separate le finalità ACS
  dalle combinazioni climatiche: `ACSr` è la resistenza del bollitore; `ACSe V1`–
  `ACSe V4` sono le richieste empiriche `CP HEAT V1`–`CP HEAT V4`. Lo stato dello
  SPLIT non fa parte del nome ACSe.

- Nei blocchi markdown con tabelle usare `|-` in YAML: con `>-` le righe si uniscono e la tabella si rompe.
- button-card con `tap_action: none` marca la card `disabled` e le dà
  `pointer-events: none`: nessun tocco arriva all'HTML dei `custom_fields` (in JS con
  `.click()` sembra funzionare, con il dito no). Se servono tocchi interni aggiungere
  `pointer-events: auto` in `styles.card`. button-card inoltre fa `preventDefault` sui clic:
  `<details>` non si apre da solo, quindi il `<summary>` dell'Albero lo apre in un
  `onclick` e ricorda lo stato in `window.__ecmAlberoAperti` (la card si ridisegna a ogni
  cambio di stato).
- In HA una card si può nascondere solo in base allo stato di un'entità, non a un attributo: per questo il motore pubblica `binary_sensor.ecm_engine_prova_avviabile`.

## Com'è organizzata (dal 09/11 sera)

- **Stato**: solo letture. In cima una riga di chip Mushroom (stagione, fascia, chi comanda,
  WRITE, reale/obiettivo, ACS), poi la card "Modalità ECM" e un rimando all'Albero. I comandi
  (stagione, setpoint, accensione split) sono in Impostazioni. Alcuni chip hanno il tocco
  disattivato o portano all'Albero apposta: il more-info di `input_select.stagione` o di
  un'automazione conterrebbe un comando.
- **Albero**: albero decisionale in una `button-card` (JS in `custom_fields.albero`) più
  una card `logbook` "Ultime decisioni" su 12 ore. In cima il "Percorso attuale" (una
  etichetta per passaggio, mappa `BREVE` nel JS); sotto i nodi chiusi (domanda e valore),
  che si aprono al tocco; restano aperti di default solo quelli con attenzione o problema.
  Il tocco **non** apre il more-info: per le automazioni mostrerebbe l'interruttore e
  "Esegui azioni". Sostituisce la card markdown "Perché ECM
  sta facendo questo?" (`perche_ecm.j2` resta nel repository solo come riferimento storico:
  conteneva errori, vedi diario 09/11 sera).
- **Impostazioni**: controlli Mushroom a pulsanti e select; bottoni stagione con conferma;
  gruppo "Avanzate" separato (isteresi CP, cambio stagione, coefficienti).
- **Diagnostica**: riepilogo salute (problemi, avvisi), freschezza dei dati, ecm-engine e
  gateway (`sensor.nilan_batch`, aggiornato ogni 20 s), tutte le automazioni ECM con stato
  e ultima esecuzione, senza interruttori.
- **Apprendimento**: sezione "Adesso" in cima (prova, avvisi), tabelle corte su telefono e
  complete solo da 1024 px in su (`visibility` con condizione `screen`).

## Logica scritta nella plancia: cosa aggiornare quando cambiano le automazioni

La plancia ricostruisce la logica delle automazioni: non la legge da un'unica entità. Quando
si modifica un'automazione ECM, aggiornare anche:

1. **Albero**: all'inizio del JS ci sono `AUT` (entity_id delle automazioni),
   `WRITE_ACS_ISOLATA` e l'array dichiarativo `RAMI` (un nodo per voce: `id, domanda,
   entita, valore, soglia, esito, attivo`). `WRITE_ACS_ISOLATA = true` riflette lo `stop`
   senza condizioni "Modalita temporanea ACS isolata" in `00_nilan_write.yaml` (non
   rilevabile da uno stato): rimetterlo a `false` quando torna la WRITE completa.
2. **Stato**: la logica "chi comanda" è scritta tre volte (chip Jinja, card Modalità ECM e
   card di rimando all'Albero, in JS).
3. **Diagnostica**: l'elenco delle automazioni "spente per scelta" è scritto nei template
   (riepilogo e righe). Se Luca ne riaccende o ne spegne una apposta, aggiornarlo.
4. **Impostazioni**: gli avvisi "automazione spenta" leggono `09_ecm_manuale`,
   `00_nilan_cambio_stagione_automatico_t10`, `01_ecm_fc_estate`, `05_ecm_acs_manager`.

Fonti dei nodi dell'Albero:

| Nodo | Fonte |
|---|---|
| write, writeIsolata | `automation.nilan_write`, `00_nilan_write.yaml` |
| manuale | `input_select.ecm_manuale`, `automation.09_ecm_manuale`, `input_number.ecm_manuale_durata_minuti` |
| stagione | `input_select.stagione`, T10, `commutazione_estate_inverno` + isteresi, `automation.00_nilan_cambio_stagione_automatico_t10` |
| fc | `input_select.free_cooling`, `automation.01_ecm_fc_estate` |
| fascia, gestore | `sensor.ecm_fascia_climatica_attiva`, orari `nilan_*`, `automation.01_ecm_eg_estate_fascia_giorno` / `01_ecm_en_estate_fascia_notturna` |
| banda, livello | temperatura zona attiva, limiti e target ECM, `input_number.livello_emc`, `sensor.ecm_configurazione_reale` |
| inverno10 | `automation.10_ecm_inverno` |
| nilan | `sensor.compactp_setpoint_aria`, `compactp_isteresi_nz`, T10, modo, compressore |
| toshiba | `sensor.toshiba_on_off_unita`, `input_boolean.toshiba_climatizzatore`, `input_select.toshiba_modo` |
| vent, contributi | ventilazione reale contro il `fan_target` della WRITE; 10, 07, 06, parte ACS della WRITE |
| acs05, acsModo, acsSoglie | `automation.05_ecm_acs_manager`, package `ecm_acs_prova_caldo`, `automation.ecm_acs_minimo_bollitore_basso_cp_heat_v2`, `input_datetime.ecm_acs_backup_sera_completato` |
| allineato | formule della WRITE contro i setpoint letti dal Nilan |

Evoluzione possibile (non fatta): un'unica entità, per esempio un template sensor
`sensor.ecm_decisione` con i nodi come attributo, oppure le automazioni che scrivono il
ramo scelto (es. `input_text.ecm_ramo`), usata da Albero, chip e card. Richiede modifiche
alla configurazione HA e l'ok di Luca.

## Strumenti di lavoro sulla plancia

Per lavorare su una vista alla volta si può dividere `ecm_v2.yaml` sulle righe
`  # ─── NOME ───` / `  - title:`, modificare il pezzo e riunire nell'ordine header, Stato,
Albero, Impostazioni, Diagnostica, Apprendimento prima di `build.py`. Le righe delle
automazioni in Diagnostica usano un'ancora YAML (`&aut` / `<<:`): non separarle.


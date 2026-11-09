# ECM Engine (motore di apprendimento del clima)

Ultima verifica: 2026-11-09 (09 ripristina solo le automazioni accese prima; colonne aria e termometri installate e verificate; campionamento ACS; riparazioni che conservano le colonne ACS; guida all'installazione, non ancora eseguita con questa procedura).

## Scopo

Servizio Python nel container `ecm-engine` sul server. Misura quanto consuma e quanto scalda o raffresca ogni combinazione di Nilan CompactP e Toshiba (codici E della numerazione di HA), per scegliere la più economica. Propone ed esegue brevi prove tramite l'automazione `09 - ECM MANUALE`. Fase 1: non comanda il clima, salvo le prove.

Sorgente, spec e piani: `sorgenti/ecm-engine/` in questo repository (`docs/specs/`, `docs/plans/`, `docs/gateway/`), fonte di verità. Importato l'8/11 con `git subtree` insieme ai 43 commit del vecchio repository locale. `.venv/`, `data/` e `data_gw/` restano fuori da git (`.gitignore` della cartella).

## Funzionamento

- Ogni 60 s legge da HA (una richiesta `POST /api/template`) e salva un campione in `~/ecm-engine/data/engine.db` (SQLite, conservazione 400 giorni). Dal 09/11 salva anche temperatura del bollitore alto/basso (`t11`, `t12`) e marcatore della prova ACS indiretta (`acs_heat_test`); per i campioni precedenti queste colonne restano vuote. Potenza CP/SPLIT, aria immessa, zone e temperatura esterna erano già registrate. **Dal 09/11 16:56 (commit `70ff339`):** T1 dopo EGWK e T4 dopo lo scambiatore passivo (`t1`, `t4`), bypass apre/chiude e serranda (`bypass_apre`, `bypass_chiude`, `serranda`, 0/1) e i termometri MIJA di soggiorno, studio, matrimoniale, Ale, Leo e bagno (`t_<stanza>`, `bat_<stanza>`, `age_<stanza>` = secondi dall'ultima lettura ricevuta, `ok_<stanza>` = valido come nel package HA: valore e batteria numerici, batteria ≥ 10%; l'età è registrata ma non entra nella validità), più `u_bagno`. Chiavi stanza: `sogg`, `studio`, `matr`, `ale`, `leo`, `bagno`. L'età ha la grana del ciclo di pubblicazione di ble_monitor (il 09/11 tutte le stanze avevano la stessa età).
- Le due temperature del bollitore sono salvate in **ogni** campione, con il codice della combinazione CP/SPLIT quando classificabile: valgono anche per CP HEAT V3 + SPLIT HEAT V1 e per il normale riscaldamento, non soltanto per le prove marcate `acs_heat_test`. Per il nuovo calcolo della resa ACS e i suoi filtri vedere la sezione dedicata più sotto. La tabella `samples` conserva una riga per timestamp: i nuovi minuti si aggiungono, mentre import o riparazioni dello stesso minuto possono sostituire quella riga (`INSERT OR REPLACE`). Le colonne che il datalogger non conosce (`t11`, `t12`, `acs_heat_test`, `acs_source_ok` e le colonne aria/termometri, elenco `LIVE_ONLY_COLS` in `store.py`) vengono conservate da `gw_repair` e da `gw_import --replace-before`: una colonna aggiunta al campionamento dal vivo va inserita anche in quell'elenco.
- Ogni 15 minuti ricalcola l'apprendimento (circa 3,5 s su 180 mila campioni) e aggiorna le entità.
- Pubblica in HA via MQTT discovery: `sensor.ecm_engine_*` (stato, in breve, migliore caldo/freddo, apprendimento, prova proposta, prova in corso, ultime prove, da misurare, dettaglio, avvisi), `binary_sensor.ecm_engine_prova_avviabile`, `button.ecm_engine_avvia_prova`, `switch.ecm_engine_prove_automatiche`.
- Le entità sono mostrate nella tab "Apprendimento" della dashboard ECM v2.
- "Da misurare" (`sensor.ecm_engine_da_misurare`) elenca **tutte** le combinazioni della stagione (inverno 28, estate 49; V1 esclusa) in tre sezioni, attributo `sezione` di ogni riga: "Provabili adesso" (nell'ordine in cui il motore le proporrebbe), "Non provabili adesso" (con `motivo`), "Già misurate" (100%). Lo stato è il numero di combinazioni ancora da misurare. Di notte (fuori `input_datetime.nilan_mattina`–`nilan_serale`, oggi 08:30–20:30) le prove con Nilan V4 o Toshiba velocità alta non si possono fare: finiscono in "Non provabili adesso". Le etichette dicono "caldo alta", non "alto".
- `apprendimento_caldo`/`apprendimento_freddo` (%) contano tutte le combinazioni della stagione, giorno o notte (fino all'08/11 la percentuale cambiava tra giorno e notte).
- **Resistenza ACS (dall'8/11):** il minuto resta valido con la combinazione dell'aria (motivo `resistenza ACS` come marcatore). Il segmenter (`correct_acs`) toglie la resistenza dal contatore Nilan: base = consumo dei 10 minuti vicini senza resistenza, separata per compressore acceso/spento; resistenza dell'episodio = mediana dell'eccesso (≈ 1310–1370 W misurati); copre anche i 3 minuti di ritardo del contatore. Verificato su E4 il 05/11: 1840 W → circa 470 W, come prima della resistenza. L'ACS col compressore (`cp_stato ACS`) resta esclusa.
- Per stimare la resa ACS della **sola resistenza**, usare incremento del bollitore alto/basso, durata e potenza aggiuntiva: aria immessa e temperatura esterna, pur presenti nel campione globale per il clima, non sono variabili della resa della resistenza. Nelle prove **CP HEAT** registrarle invece per valutare aria portata in casa ed efficienza della CP.
- **Stati tenuti 3 minuti:** se un sensore di stato (Nilan o Toshiba) è `unavailable`, il motore usa l'ultimo valore noto fino a 180 s (`hold_states`), così un buco di lettura non spezza la misura.
- **Temperatura esterna (dall'8/11):** la sonda "aria esterna prima EGWK" sta nel condotto della Compact e con la Compact ferma legge aria ferma (in media +2,2 °C, fino a +5 °C). Nelle statistiche (`fix_text` nel segmenter) vale solo dopo 10 minuti di ventilazione continua; negli altri minuti si usa l'interpolazione tra la lettura buona prima e quella dopo (entro 12 ore), oppure l'ultima buona per al più 6 ore, altrimenti il valore grezzo. Circa il 30% dei minuti risulta stimato, con una correzione mediana di −1,7 °C. Per la fascia attuale il motore usa `sensor.ecm_temperatura_esterna_affidabile` (package HA `ecm_temperatura_esterna.yaml`: stessa regola dei 10 minuti, tiene l'ultimo valore buono, attributi `ultima_lettura` ed `eta_minuti`), con ripiego sulla sonda grezza. **Regola decisa da Luca il 09/11, non ancora implementata:** il riuso dell'ultima lettura buona non basta a classificare i periodi in cui lo SPLIT riscalda o raffresca; quando la lettura non è attuale una lettura con più di 60 minuti non è attuale e, quando qualcosa di attivo la richiede, si acquisisce: con la sola ventilazione se esterno e interno sono vicini, altrimenti con CP HEAT V2 (inverno, esterno più freddo) o CP COOL V2 (estate, esterno più caldo), mai con ventilazione che porti aria sfavorevole in casa; la CP si avvia e si ferma tramite setpoint aria e isteresi; l'acquisizione finisce quando la sonda resta stabile entro ±0,2 °C per almeno 1 minuto. Dettagli e dati da campionare nel diario `2026-11.md` (09/11 sera).
- Le statistiche sono per **fascia di temperatura esterna** (<5, 5–10, 10–15, 15–20, …): "Da misurare" e "Dettaglio" mostrano la fascia attuale. Esempio: le prove E90 del 06/11 e dell'08/11 (Compact ferma, sonda a 15,3 °C) dopo la correzione della temperatura contano in 10–15.
- Token HA in `~/.config/ecm/ha_token` (montato in sola lettura nel container). Mosquitto locale senza autenticazione.

## Prove

- Partono dal pulsante oppure, se l'interruttore "Prove automatiche" è acceso (spento di default), da sole tra le 10 e le 17, al massimo 3 al giorno, con 60 minuti tra una e l'altra.
- Condizioni di avvio: 09 in AUTO, Free Cooling spento, nessun ciclo ACS, SOC ≥ 40% oppure FV ≥ consumo, **00-NILAN WRITE accesa**, temperature delle zone compatibili. Per le prove di caldo la zona più calda deve restare sotto la soglia ESTATE − 1 °C (oggi 23,5 °C).
- Il motore riporta 09 in AUTO se: una zona supera la soglia ESTATE − 0,5 °C, il SOC scende sotto il 25% senza sole, WRITE si spegne, mancano dati per 5 minuti, oppure la prova supera la durata di 3 minuti. Al ritorno in AUTO la 09 riaccende solo le automazioni ECM che erano accese prima della prova (salvate in `input_text.ecm_manuale_automazioni_da_ripristinare`, dal commit HA `183c35a`).
- Senza WRITE accesa gli helper cambiano ma le macchine no: le prove sarebbero inutili e sospenderebbero il ricambio aria, per questo il motore le blocca.

## Dati caricati

- Campioni live dal 07/11/2026 19:49.
- Storico dal recorder di HA (31/10–07/11).
- Storico del datalogger del gateway Higeco (04/07–31/10), con zone ricavate dalle statistiche orarie di HA dal 27/08 e da T10 prima. Dettagli in `sorgenti/ecm-engine/docs/gateway/import_mapping.md`.
- 08/11: riparati con `gw_repair` 4548 campioni scartati (stati illeggibili o resistenza ACS) usando gli stati del datalogger e le misure già salvate. Risultato: validi da 169 040 a 171 184, minuti utili nei periodi da 141 281 a 144 364. Non recuperabili: 04–05/07 (lo Split nel datalogger parte dal 05/07 alle 09:11).
- 08/11: consumo Compact dello storico da datalogger (fino al 31/10 21:00, dove il contatore era registrato solo ogni 10 minuti) ricalcolato con `gw_repair --energia-cp` dalla differenza del contatore di energia importata (risoluzione 1 Wh): 167 533 campioni (differenza media +1,7 W, p90 68 W, dove il compressore ciclava) e 1331 minuti "dato mancante p_cp" recuperati. Periodi da 2354 a 2223 (più lunghi), minuti utili da 144 364 a 147 057.
- Backup del database: `~/engine_pre_replace.db` (sostituzione precedente) `~/ecm-engine/data/engine_pre_repair_20261108.db` (prima della riparazione dell'8/11) e `~/ecm-engine/data/engine_pre_energia_20261108.db` (prima dei consumi da kWh). Da cancellare quando non servono più.

## Gestione

```sh
# primo uso su una macchina nuova (il venv non è nel repository)
cd sorgenti/ecm-engine && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# deploy: vedi "Installare una nuova versione sul server" qui sotto
# stato e log
ssh home@192.168.1.100 'docker ps --filter name=ecm-engine; docker logs --tail 20 ecm-engine'
# fermare
ssh home@192.168.1.100 'cd ~/ecm-engine && docker compose down'
```

## Installare una nuova versione sul server

Il sorgente in questo repository è la fonte di verità; sul server `~/ecm-engine` è solo
la copia che `deploy.sh` sincronizza (non è un repository git). Riavviare il container
richiede l'ok di Luca (vedi `AGENTS.md`).

1. **Allineare il repository**, dalla radice: `git fetch && git status`, poi
   `git pull --ff-only`. `deploy.sh` copia la cartella così com'è, comprese eventuali
   modifiche non committate: se `git status` ne mostra in `sorgenti/ecm-engine`, chiarire
   di chi sono prima di procedere. Annotare il commit che si installa
   (`git log --oneline -1 -- sorgenti/ecm-engine`) e quello installato prima (dal diario),
   per poter tornare indietro.
2. **Leggere cosa cambia**: `git log --oneline <installato>..HEAD -- sorgenti/ecm-engine`
   e il diario del giorno. Fare attenzione alle modifiche dello schema di `samples` in
   `store.py`: sono aggiunte di colonne (`ALTER TABLE`) e restano anche tornando indietro.
3. **Test in locale**: `cd sorgenti/ecm-engine && .venv/bin/pytest -q` (al primo uso
   creare il venv, vedi sopra). Se un test fallisce ci si ferma.
4. **Backup coerente del database**, senza fermare il motore:
   ```sh
   ssh home@192.168.1.100 'docker exec ecm-engine python3 -c "import sqlite3; s=sqlite3.connect(\"/data/engine.db\"); d=sqlite3.connect(\"/data/engine_pre_<motivo>_<aaaammgg>.db\"); s.backup(d); d.close(); print(s.execute(\"pragma quick_check\").fetchone())"'
   ```
   Deve stampare `('ok',)`. Il file si trova poi in `~/ecm-engine/data/` sul server.
5. **Installare**, con l'ok di Luca: `./deploy.sh` da `sorgenti/ecm-engine`. Lo script
   rilancia i test, sincronizza i file (esclusi `data`, `.env`, `.venv`), ricostruisce
   l'immagine e ricrea **solo** il container `ecm-engine`, poi mostra le ultime righe di log.
6. **Verificare**: sezione "Verifica" più sotto, più quanto indicato nel diario per quella
   versione. Il primo apprendimento parte all'avvio: nel log cercare la riga
   `apprendimento: … in N s`.
7. **Registrare** nel diario: commit installato, ora, nome del backup ed esito delle verifiche.

**Tornare indietro**, dalla radice del repository: riportare la cartella alla versione
precedente con `git checkout <commit precedente> -- sorgenti/ecm-engine`, lanciare
`./deploy.sh`, poi rimettere il repository com'era con `git checkout HEAD -- sorgenti/ecm-engine`.
Le colonne aggiunte al database restano e il codice precedente le ignora. Il backup serve
solo se una versione ha rovinato i dati: fermare il container, sostituire `data/engine.db`
con il backup e riavviare.

## Riparare campioni dal datalogger

Quando HA ha perso letture di stato (minuti `cp non classificato` / `toshiba non classificato`) o le regole di classificazione cambiano:

1. Scaricare dal datalogger Compact P (2001969) e Split (2002144) per il periodo, con la sessione admin aperta a mano nel browser (vedi `gateway-higeco.md`). Salvare in `sorgenti/ecm-engine/data_gw/` come lista di `{dev, s, e, body}`.
2. Backup del DB nel container (`sqlite3` `backup` verso `/data/engine_pre_<motivo>.db`).
3. Copiare i file nel container e lanciare a secco: `docker exec -w /tmp/gwrep -e PYTHONPATH=/app ecm-engine python3 -m ecm_engine.gw_repair <file>...` (opzioni `--from`/`--to`). Mostra quanti campioni cambierebbero e come.
4. Se il riepilogo torna, ripetere con `--apply`, poi `docker restart ecm-engine` per ricalcolare subito (oppure attendere il ricalcolo dei 15 minuti).
5. Consumo Compact dai kWh: aggiungere i file del Misuratore Compact (`dev_2002794.json`) e l'opzione `--energia-cp` (con `--to` al confine dei dati da datalogger). Tocca solo i campioni il cui `p_cp` coincide con la potenza registrata dal datalogger.
6. Prima, provarlo su una copia locale del DB con `DB_PATH=<copia> .venv/bin/python -m ecm_engine.gw_repair ...`.

## Verifica

- `sensor.ecm_engine_stato` = `online`.
- `docker logs ecm-engine` senza `Traceback`; riga di log con la durata dell'apprendimento.
- Campioni recenti in `engine.db` (l'ultimo ha meno di 2 minuti).

## Apprendimento ACS per combinazione (09/11)

Implementato in `ecm_engine/acs_learner.py`, pubblicazione MQTT nel sensore
`sensor.ecm_engine_resa_acs`. Attivo dal 09/11 alle 11:52 dopo consenso di Luca
al riavvio del solo ecm-engine. Usa CP HEAT V1–V4 con ogni combinazione SPLIT,
compreso SPLIT OFF, da funzionamento normale e prove. Ogni riga riporta fascia
iniziale del bollitore basso (5 °C), pendenza netta mediana in °C/h, finestre,
minuti, origine prova/normale, potenze CP/SPLIT separate e dispersione delle rese.
Non è un COP e non misura un contributo causale dello SPLIT all'acqua.

Richiede dati numerici, CP in HEAT con compressore acceso e resistenza spenta;
il nuovo marcatore persistente `acs_source_ok` è calcolato prima di recuperare
eventuali stati vecchi. Campioni precedenti privi del marcatore restano esclusi.
**Il codice attualmente distribuito**, non ancora allineato alla decisione successiva di
Luca, attende 8 minuti dopo avvio, cambio combinazione, dati mancanti o variazione
rapida del bollitore (calo >0,3 °C/min circa o salto >2 °C per campione), poi
misura finestre non sovrapposte di almeno 10 minuti. Questa regola 8+10 non è una
regola valida concordata per ACSe e non va usata per giudicare le prove: per ACSe la
temperatura esterna e il suo assestamento sono irrilevanti. La regola da implementare
per una prova controllata di 20 minuti è al massimo 5 minuti iniziali di avvio e i
successivi 15 minuti considerati integralmente. Conserva rese nulle e negative.
Piccoli prelievi non rilevati e stratificazione possono ancora influire: dati
osservativi, supporto iniziale sotto cinque finestre, nessun comando ACS basato
automaticamente su questa stima. Nessun uso della temperatura esterna per ACS.

Il calcolo condivide con la segmentazione del clima un'unica lettura del database
(prima erano due, e il ciclo dei 15 minuti era passato da 3,5 a 8,1 s). Gli attributi
del sensore restano sotto 15 000 byte, perché il recorder di HA non salva quelli oltre
16 384: se la tabella è più grande si tengono le righe con più finestre, e
`righe_omesse` dice quante ne mancano.

## Limiti delle misure climatiche

- Dallo storico i consumi sono attendibili, l'efficacia (°C/ora) poco: osservando passivamente la casa è già regolata e le zone hanno solo medie orarie. Per l'efficacia servono le prove.
- La velocità V1 della Nilan (STEP 1) è registrata con codici propri (u=7 e u=8, per esempio E7, E8), fuori dalla numerazione di HA. Non è mai proposta come prova.

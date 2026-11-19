# Modificare la configurazione di Home Assistant

Ultima verifica: 2026-11-19 (curva delle soglie invernali durante l'assenza).

## Prerequisiti

- Accesso `ssh home@192.168.1.100`. `home` non ha sudo: i comandi privilegiati passano dall'utente `minipc` (`ssh -t minipc@192.168.1.100 'sudo …'`).
- La configurazione è in `/opt/homeassistant/config`, montata nel container `homeassistant` come `/config`. È un repository git (`lucarebesan/home-assistant-config`, branch `main`).
- I file sono di root: `home` non li può modificare direttamente.
- Token API di HA (long-lived) in `~/.config/ecm/ha_token` sul server, permessi 600. Non stamparlo e non copiarlo altrove: usarlo solo come `$(cat ~/.config/ecm/ha_token)` dentro i comandi remoti.

## Passaggi

1. Copiare il file sul PC, modificarlo e ricopiarlo nel container:
   ```sh
   scp home@192.168.1.100:/opt/homeassistant/config/automations/nilan/07_ecm_ricambio_aria_minimo.yaml .
   # modifica locale
   scp 07_ecm_ricambio_aria_minimo.yaml home@192.168.1.100:/tmp/
   ssh home@192.168.1.100 'docker cp /tmp/07_ecm_ricambio_aria_minimo.yaml homeassistant:/config/automations/nilan/ && docker exec homeassistant chown 0:0 /config/automations/nilan/07_ecm_ricambio_aria_minimo.yaml'
   ```
   Mantenere i permessi 644.
2. Controllare la configurazione:
   ```sh
   ssh home@192.168.1.100 'docker exec homeassistant python -m homeassistant --script check_config -c /config'
   ```
3. Ricaricare senza riavviare (sostituire il servizio secondo il caso: `automation/reload`, `input_select/reload`, `input_number/reload`, `template/reload`, `command_line/reload`):
   ```sh
   ssh home@192.168.1.100 'curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $(cat ~/.config/ecm/ha_token)" http://127.0.0.1:8123/api/services/automation/reload'
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
   ssh home@192.168.1.100 'docker exec -i homeassistant sh -s' < /tmp/commit.sh
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

## Spegnimento luci con la sicurezza assenza delle chiusure

Dal commit HA `ce934d3`, l'automazione
`automation.chiusure_meteo_assenza_casa` richiama
`script.chiusure_spegni_luci_assenza` subito dopo avere forzato o riaffermato
`input_select.meteo` su `PIOGGIA` per assenza di Luca e Alice senza ospiti. I
richiami da conservare sono tre: prima attivazione, sicurezza assenza già attiva
e scadenza della deroga ospiti con casa ancora vuota.

La lista esplicita delle 60 uscite approvate è nel package
`packages/chiusure_ospiti.yaml`; la classificazione e le esclusioni fanno fede
nel diario di novembre 2026. Lo script comanda solo le uscite che risultano ON e
scrive nel logbook l'esito dopo due secondi. Non eseguirlo manualmente durante
un controllo ordinario: spegnerebbe realmente le luci incluse. Verificare invece
che l'entità esista, sia OFF e che `last_triggered` cambi soltanto in
corrispondenza di una reale forzatura assenza.

Questa logica non mantiene le luci bloccate su OFF: le spegne puntualmente nei
tre percorsi sopra indicati. Un eventuale blocco continuo durante le ferie
lontane richiede una decisione separata sulle eccezioni manuali ed emergenza.
Il backup precedente al deploy è in
`/tmp/backup_chiusure_luci_assenza_20261116_2205/`.

## Aperture per riscaldamento solare, anche in inverno

Dal 17/11, commit HA `c0b608d` e `5c6e833`, le tre automazioni in
`automations/chiusure/chiusure_meteo_sole_azimut.yaml`,
`chiusure_meteo_pioggia.yaml` e `chiusure_riscaldamento_sole_richiesta.yaml`
gestiscono il guadagno solare in entrambe le stagioni.

- **INVERNO:** SOLE+AZIMUT può aprire le sole chiusure raggiunte dal sole con
  richiesta termica della zona attiva. La richiesta si attiva sotto il limite
  superiore ECM e termina da limite +0,5 °C, come prima. Il ramo invernale si
  ferma prima delle azioni estive di ombreggiamento.
- **ESTATE:** la richiesta si attiva sotto il limite inferiore ECM e mantiene
  l'isteresi di 0,5 °C; è comunque bloccata al limite superiore, durante una
  richiesta/attività di COOL o DRY Toshiba, CP in raffrescamento, Free Cooling
  ATTIVATO/PREPARAZIONE o selezione manuale COOL/DRY. Richiede temperatura
  esterna affidabile numerica, età 0–60 minuti e non oltre 0,5 °C sopra la
  temperatura della singola zona. Con dati esterni mancanti o vecchi non apre
  per scaldare. Le normali azioni estive di ombreggiamento restano operative.
- **Assenza:** PIOGGIA forzata con pre-assenza SOLE permette le stesse aperture
  selettive anche in INVERNO; PIOGGIA esenta dalla richiusura soltanto le
  facciate al sole con consenso termico attivo. Cambio di richiesta e azimut
  usano il ramo di controllo già periodico a 2 minuti; alla perdita del
  consenso o del sole l'eccezione cessa. PIOGGIA senza pre-assenza SOLE non
  riceve eccezioni.

Azimut e orari precedenti conservati: lavanderia 60–110°, studio/divano
90–180°, cucina/matrimoniale/sottotetto 160–280°, Leo/scala 240–300°.
Finestra ordinaria da `nilan_mattina +15 minuti` a 100 minuti prima del
crepuscolo; lavanderia anticipata dopo l'alba nella propria fascia di azimut.
Serve sole sopra l'orizzonte. ALE e bagno non entrano nel riscaldamento solare.
Le azioni sono sulle tapparelle/frangisole, non sull'apertura dei serramenti.

**Verifica:** i quattro booleani `riscaldamento_sole_*` devono seguire le
temperature e, d'estate, i consensi sopra descritti. Non forzare le condizioni
per collaudare le chiusure: attendere i normali azimut e controllare posizioni
e `last_triggered`. Il 17/11 sono passati 19 controlli sintetici su estate,
inverno, dati mancanti, raffrescamento, pioggia e instradamento dei trigger;
`check_config` riuscito e reload automation senza cambi ON/OFF preesistenti.
La sequenza completa sul campo attraverso tutti gli azimut non è ancora
stata osservata.

**Ripristino:** originali in `/config/tmp/backup_sole_inverno_20261117/` nel
container HA. Ripristinare i soli tre file, eseguire `check_config` e
`automation.reload`; conservare gli stati ON/OFF e rivalutare la richiesta
solare solo se la relativa automazione è abilitata.

## Umidità lavanderia a blocchi lunghi dal 14/11

La `06-ECM HUMIDITY OVERRIDE` del commit HA `a25c615` sostituisce i richiami di
15 minuti a inizio ora, che facevano scendere l'umidità solo temporaneamente.
Con sensore lavanderia valido (batteria almeno 10%), il superamento stabile del
75% avvia da solo un primo blocco continuo: V4 nella fascia giorno
`nilan_mattina`–`nilan_serale`, V3 fuori fascia, mai V1. Il blocco termina sotto
il 70% oppure dopo 90 minuti. Dopo la fine attende almeno 120 minuti; se serve
ancora, avvia un blocco di 60 minuti. I richiami successivi sono separati da
almeno 180 minuti. Un cambio di fascia durante il blocco adegua V4/V3 al minuto
successivo.

La `06` pubblica solo `emc_richiesta_ventilazione_umidita` e la velocità
richiesta. La `07` conserva la priorità operativa e arbitra con il massimo tra
ricambio e umidità. Se la `07` ventila mentre la `06` è in pausa, la `06` non
parte né modifica la velocità: aggiorna la fine del lavoro utile e ricomincia la
propria pausa dalla cessazione del ricambio. In questo modo il ricambio conta
anche come trattamento dell'umidità e non viene duplicato.

Helper aggiunti in `packages/ecm_helper.yaml`:
`input_boolean.ecm_umidita_richiamo_lungo_eseguito` distingue la pausa iniziale
da quella ricorrente; `input_datetime.ecm_umidita_ultimo_blocco_fine` conserva
la fine dell'ultimo blocco o dell'ultima ventilazione `07` conteggiata. Il
rientro sotto il 70% azzera ciclo e richiami, così un nuovo superamento del 75%
riceve un nuovo blocco iniziale. Non esiste un azzeramento a orario fisso.
CP HEAT/OFF e l'eventuale campionamento della temperatura esterna restano
responsabilità della `07`.

**Verifica:** con umidità sotto soglia devono risultare `06`, `07` e WRITE ON,
richiesta umidità OFF, velocità umidità 0 e primo ciclo non esaurito. Dopo una
doccia controllare nel logbook la partenza autonoma della `06`, V4 di giorno o
V3 di notte, CP HEAT/OFF scelto dalla `07`, durata reale e andamento
dell'umidità. Non avviare manualmente la ventilazione durante la prova.

**Ripristino:** i file precedenti sono in
`/config/tmp/backup_umidita_blocchi_20261114_1720/`. Copiare nel container
`06_ecm_humidity_override.yaml` e `ecm_helper.yaml`, eseguire `check_config`,
ricaricare nell'ordine `input_boolean`, `input_datetime`, `automation` e
verificare le richieste prima di lasciare la `06` attiva.

## Isolamento ACS temporaneo dal 09/11

Il commit HA `8e156b3` lascia attiva `00-NILAN WRITE` con un blocco iniziale che
scrive ACS e, durante una prova temporizzata, CP HEAT; il vecchio ramo
ECM è irraggiungibile. Dal 09/11 il ramo isolato accetta anche il ricambio
invernale della `07`, e dal 10/11 il riscaldamento ambiente della `10`.
`05 ECM ACS MANAGER` gestisce anche la copertura
serale con resistenza; `packages/ecm_acs_prova_caldo.yaml` contiene guardia
e helper. Le altre automazioni decisionali ECM, salvo `06`, `07` e `10`,
restano spente: l'elenco e i
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

Per sospendere subito tutte le scritture automatiche, spegnere prima
`automation.nilan_write` via API HA e verificare le macchine. Prima di
ripristinare la vecchia WRITE generale, lasciare l'automazione spenta,
ripristinare i file dal commit precedente `7ba3f03` in una copia di lavoro,
eseguire `check_config` e `automation.reload`, poi decidere esplicitamente
quali decisori ECM riaccendere. Non riaccendere la vecchia WRITE con tutte
le automazioni ECM ancora in stato sconosciuto.

## Riscaldamento ambiente invernale dal 10/11

Il primo commit HA `4b1dff7` è stato sostituito lo stesso giorno perché applicava
al riscaldamento soglie generiche non concordate (20/21,2 °C), un'eccedenza FV
fissa di 1000 W e CP HEAT come fonte ambiente. La versione vigente è il commit
HA `d29a722`, poi aggiornata nella matrice dal commit HA `335b878` e nella
modulazione Toshiba dai commit `cf449de`, `06edcf8` e `0f4b9ef`; i file sono
`10_ecm_inverno.yaml` e `packages/ecm_helper.yaml`. Il ramo WRITE accetta ora
il setpoint Toshiba dinamico a passi di 0,5 °C.

La `10` è accesa, gira ogni minuto solo in INVERNO e con `ecm_manuale` in AUTO e
usa le medie zona a 10 minuti. Tutte le soglie derivano dinamicamente da
`input_number.t_min_inverno`, impostato a 20,5 °C alla verifica. La matrice base è:

| Fascia | Zona | Avvio sotto | Recupero fino a | Con T min 20,5 °C |
|---|---|---:|---:|---:|
| GIORNO | giorno | T min | T min + 0,5 | 20,5 → 21,0 °C |
| GIORNO | notte | T min − 0,5 | T min | 20,0 → 20,5 °C |
| NOTTE | giorno | T min − 1,0 | T min − 0,5 | 19,5 → 20,0 °C |
| NOTTE | notte | T min − 1,5 | T min − 1,0 | 19,0 → 19,5 °C |

Ogni zona ha una memoria di recupero distinta; basta una zona sotto il proprio
limite per chiedere calore e il suo recupero resta attivo fino alla soglia della
quarta colonna.

### Riduzione dei minimi durante l'assenza

Dal commit HA `48d1e29`, se `zone.chiusure_casa` (raggio 250 m) non contiene
né Luca né Alice per almeno due minuti e `input_select.ospiti_a_casa` vale
`Nessun ospite`, l'automazione `ECM - Gestione assenza temperatura` attiva
`input_boolean.ecm_assenza_attiva` e conserva l'inizio in
`input_datetime.ecm_assenza_inizio`. L'offset pubblicato da
`sensor.ecm_offset_temperatura_assenza` è:

| Assenza continuativa | Riduzione dei limiti inferiori |
|---|---:|
| da 0 a meno di 3 ore | 0 °C |
| da 3 a meno di 12 ore | −0,5 °C |
| da 12 a meno di 24 ore | −1,0 °C |
| da 24 a meno di 36 ore | −1,5 °C |
| da 36 ore in poi | −2,0 °C |

Scaglioni aggiornati il 19/11 nel commit HA `8181ab9`. Il calcolo usa
il tempo trascorso dall'inizio dell'assenza confermata. Lo stato
pubblica il valore positivo da sottrarre. L'attributo `livello` usa lo stesso
tempo non arrotondato del calcolo.
Per ripristinare la curva operativa precedente usare
`/config/tmp/backup_ecm_curva_assenza_20261119/ecm_helper_precedente_attivo.yaml`,
quindi eseguire `check_config` e ricaricare template e automazioni.

La `10` sottrae questo valore a `T min` solo per calcolare avvio e recupero di
entrambe le zone nelle fasce GIORNO e NOTTE; non modifica l'helper impostato
dall'utente. Il massimo di accumulo resta quello di
`input_number.ecm_inverno_massimo_accumulo` (23,5 °C alla verifica), quindi
FV o batteria favorevoli possono accumulare calore anche a casa vuota.

Quando almeno una persona rientra nella zona da 250 m o viene attivata la
deroga ospiti, l'offset torna subito a zero. Stati zona/ospiti `unknown` o
`unavailable` non dichiarano la casa vuota. Booleano e ora di inizio sono
persistenti per conservare lo scaglione dopo un riavvio; questo recupero non è
stato provato con un riavvio reale durante un'assenza. Per verificare leggere
anche `sensor.ecm_ore_assenza`; a casa occupata deve valere 0 insieme all'offset.
Il backup precedente al deploy è in `/tmp/backup_ecm_assenza_20261116/` sul
mini PC.

#### Rientro da oltre 50 km

Dal commit HA `f85f019` esistono anche le zone storage `zone.25km` e
`zone.50km`, concentriche a `zone.home`; il registro precedente è salvato in
`/tmp/backup_ecm_rientro_lontano_20261116/zone`. Quando entrambi risultano
oltre 50 km, l'assenza è attiva e non ci sono ospiti, dopo due minuti si arma
`input_boolean.ecm_ferie_lontane_attive`.

Il primo ingresso di almeno una persona nella zona da 50 km apre una finestra
di rientro di sei ore (`input_boolean.ecm_rientro_lontano_attivo` e
`input_datetime.ecm_rientro_lontano_inizio`). Se l'assenza ha già superato
36 ore, l'offset viene anticipato così:

| Posizione durante il rientro | Offset applicato |
|---|---:|
| entro 50 km, ma fuori da 25 km | −1,0 °C |
| entro 25 km, ma fuori da 10 km | −0,5 °C |
| entro 10 km | 0 °C |

La rampa vale soltanto entro sei ore dall'ingresso nella zona da 50 km; dopo
torna l'offset ordinario di assenza. Il rientro nella zona da 250 m o la deroga
ospiti azzerano assenza, ferie e rientro. Alla verifica subito dopo la creazione,
i centri 25/50 km coincidevano geometricamente con `zone.home` e le posizioni
di Luca e Alice erano all'interno, ma i contatori delle due nuove zone erano
ancora 0 in attesa di una rivalutazione dei tracker: verificare il primo
aggiornamento GPS e il primo viaggio reale prima di considerare validata la
sequenza completa.

Sopra il minimo non esiste più il vecchio target 21,2 °C. Se l'energia è
favorevole, l'accumulo può proseguire fino al massimo comune modificabile
`input_number.ecm_inverno_massimo_accumulo`, inizialmente 23,5 °C; raggiungerlo in
una delle due zone arresta subito la richiesta. Di giorno l'avvio usa i consensi
stabili FV/batteria già condivisi con ACS; durante il ciclo verifica importazione
rete, scarica batteria, FV e consumo base. Di notte stima il SOC al mattino con
capacità 20 kWh, profilo orario appreso della casa (se completo), consumo della
combinazione Split e riserva del 15%. `nilan_mattina` resta per ora il ripiego:
l'apprendimento dell'istante in cui il FV torna sopra 400 W è ancora da fare.
Il recupero sotto il minimo prevale sempre sulla disponibilità energetica.

Per il calore ambiente la `10` richiede **solo Toshiba HEAT** e mantiene
`input_number.ecm_ventilazione_riscaldamento_ambiente` a 0. La CP continua a
essere arbitrata separatamente per ACS, umidità e ricambio. I test del 10/11
hanno misurato circa 500/530/600 W aggiuntivi per CP HEAT V2/V3/V4 senza
dimostrare un riscaldamento ambiente sufficiente. Le coppie CP+Split hanno oggi
soltanto W stimati per somma, non una resa incrementale misurata: non sono
selezionabili automaticamente finché prove comparative non dimostrano che il
calore aggiuntivo giustifica quei consumi.

La velocità Toshiba viene scelta fra E70/E80/E90 usando
`sensor.ecm_engine_migliore_caldo` e la tabella appresa (costo termico,
affidabilità e flag da confermare); il ripiego è V3 di giorno e V2 di notte.
Nella fascia NOTTE non supera V2. Una scelta resta attiva almeno 15 minuti, salvo
massimo o sicurezza. Dopo la finestra minima rivaluta ranking e trend separati
20/30/60 minuti delle zone in recupero; due trend non positivi rendono la resa
insufficiente e consentono di salire di velocità entro il limite di fascia.

### Modulazione del setpoint Toshiba dal 17/11

La `10` controlla ogni minuto ma adegua il setpoint per efficacia soltanto dopo
una finestra di 30 minuti. A un nuovo ciclo con
`sensor.ecm_toshiba_sonda_ambiente` valido parte dalla sonda +0,5 °C, arrotondata
al mezzo grado superiore e limitata a 29 °C. Se la sonda non è valida parte a
29 °C e arma `input_boolean.ecm_toshiba_attesa_sonda_iniziale`; al primo valore
valido passa una sola volta a sonda +0,5 °C, salva nuove temperature iniziali e
fa ripartire da zero i 30 minuti. Dopo questo primo aggancio il booleano resta
OFF per tutto il ciclo: una perdita successiva della sonda non cambia setpoint,
margine efficace o conteggio già maturato.

La finestra usa le medie zona a 10 minuti salvate nei due helper
`ecm_toshiba_modulazione_tg_inizio` e `_tn_inizio`. In recupero ogni zona ancora
agganciata deve crescere almeno 0,05 °C; in accumulo basta una delle due. Deve
anche risultare attivo il compressore (RPS > 0 oppure potenza media Toshiba 5
minuti > 150 W). Se la resa non basta, il setpoint sale di 0,5 °C e il nuovo
livello diventa il minimo efficace da non riprovare al ribasso nello stesso
ciclo. Se la resa basta, mantiene per un altro intervallo; solo dopo due
intervalli efficaci consecutivi prova −0,5 °C, senza scendere sotto il minimo
appreso né sotto sonda +0,5 °C. Ogni variazione azzera il conteggio e apre una
nuova finestra di 30 minuti.

`input_number.toshiba_setpoint` è uno storage helper con passo 0,5 °C (ID storage
storico `toschiba_setpoint`); il ramo ambiente della WRITE confronta e inoltra
il valore effettivo invece del vecchio 29 °C fisso. Il batch legge anche il
proxy Toshiba `1999108 Id1`; il template stabile esposto alla `10` è
`sensor.ecm_toshiba_sonda_ambiente`. Verificato a macchina accesa che 28,5 e
28 °C vengono accettati; verificata anche la catena helper → WRITE → gateway e
il ripristino a 29 °C.

La temperatura dell'aria in uscita dallo Split, prima della distribuzione nei
condotti, è il sensore BLE `sensor.toshiba_temperatura_immissione` (unique ID
`t_A4C13834A616`). Il 18/11 è stato rinominato dal vecchio entity ID
`sensor.ble_temperature_mija_garage` tramite il registro ufficiale di HA; i
cinque riferimenti della Overview e quello di ECM v2 sono stati aggiornati.
Il recorder ha migrato senza discontinuità lo stesso `states_meta` 2513 e lo
stesso `statistics_meta` 201 al nuovo ID. Verifica in sola lettura: stati grezzi
dal 11/11 04:12 e statistiche orarie dal 14/12/2025; il nome visibile originale
può ancora contenere `MIJA GARAGE`, ma non è l'identità usata dalle dashboard.
Luca conferma che la sonda è fisicamente sulla mandata Toshiba da almeno circa
sei mesi e ha misurato tutta l'estate 2026: valori vicini a 1–3 °C possono quindi
essere mandata in COOL, non prova della vecchia collocazione in garage. La data
esatta dello spostamento resta da determinare prima di usare il tratto più
antico; ECM Engine non campiona ancora questa grandezza nel proprio database.

La prima osservazione del 17/11 ha evidenziato due casi di collaudo: il reload
degli helper rende temporaneamente indisponibili alcuni sensori e può azzerare
un latch, quindi durante futuri reload di `input_number`, `input_boolean` o
`template` sospendere la sola `10`, attendere il ritorno dei sensori e poi
riattivarla; inoltre una stringa `false` nella valutazione della resa era stata
interpretata male. Il commit `0f4b9ef` forza esplicitamente i booleani: un
intervallo 0,00/−0,02 °C non può più essere classificato efficace.

**Verifica:** leggere stato e `last_triggered` di `10` e WRITE, i tre helper
`ecm_inverno_recupero_*`, `ecm_inverno_accumulo_attivo`, la richiesta ambiente,
la velocità Toshiba e le macchine reali. La richiesta CP ambiente deve restare 0;
una CP attiva deve essere spiegata da ACS, umidità o ricambio. Controllare anche
W/ranking del motore, trend zona e nuovi errori nel log. Alla verifica serale
del 17/11: `10` e WRITE accese, nuovo helper di attesa OFF, richieste ambiente
OFF e Toshiba spento. Il prossimo ciclo naturale deve ancora validare partenza
vicino alla sonda, prima finestra completa, salita se inefficace e successiva
modulazione con condizioni esterne più fredde.

**Ripristino:** spegnere `automation.10_ecm_inverno` e verificare Toshiba OFF;
la `07` e la WRITE continuano ricambio/ACS. Il backup immediatamente precedente
alla modulazione è in `/tmp/backup_toshiba_modulazione_20261117_1748/`; i backup
dell'aggancio sonda e della conversione booleana sono rispettivamente in
`/tmp/backup_toshiba_sonda_ritardata_20261117_2215/` e
`/tmp/backup_toshiba_bool_20261117_2225/`. Il backup precedente della logica
invernale è in `/tmp/backup_ecm_inverno_corretto_20261110/`; quello precedente
al commit `4b1dff7` resta in `/config/tmp/backup_ecm_inverno_20261110/`. Dopo una
copia eseguire `check_config`, ricaricare `input_boolean`, `input_number`,
`input_datetime` e `automation`, lasciando la `10` spenta finché il ripristino
non è verificato.

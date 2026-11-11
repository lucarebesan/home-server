# Decisore ECM – Passo 1: ombra dell'ambiente invernale

Data: 2026-11-11. Decisioni di Luca e Mattia sulla proposta del diario (10/11 17:28) e
sull'analisi successiva: valutatore e arbitro sono un unico componente a pipeline,
l'energia si applica a ogni candidato, le risorse della CP sono modellate in modo
esplicito, il primo passo è soltanto l'ombra dell'ambiente invernale contro la `10`,
con confronto a parità di stato HA. Sequenza e lease controllati da HA, autorità per
dominio e fallback semplice sono previsti nel contratto ma non ancora attivi. Le prove
tramite `09` restano invariate.

## Obiettivo

Ogni minuto il motore calcola che cosa farebbe per il riscaldamento ambiente
invernale (Toshiba spento o HEAT V1/V2/V3, motivo) usando le stesse regole della
`10`, lo confronta con quello che succede davvero e registra divergenze e metriche di
risultato. **Non scrive helper, non comanda macchine, non chiama servizi HA.**

## Fuori ambito

ACS, umidità, ricambio, estate, free cooling, CP come fonte di calore ambiente,
attuazione, helper di autorità e automazioni HA di applicazione o fallback, previsioni
meteo/FV (da aggiungere in HA a parte), controllo predittivo.

## Struttura (`ecm_engine/decisore/`)

| Modulo | Compito |
|---|---|
| `parametri.py` | soglie e costanti; quelle non ancora lette dalla `10` sono marcate `DA VERIFICARE` |
| `tipi.py` | `Contesto`, `Risorsa`, `Candidato`, `Richiesta`, `Stato`, `Piano` (dataclass, nessun I/O) |
| `ambiente.py` | soglie relative a T min per fascia e zona, latch di recupero, accumulo, massimo → `Richiesta` |
| `energia.py` | giudizio energetico di un candidato (giorno: consenso e bilancio istantaneo; notte: SOC previsto al mattino con profilo orario del carico) |
| `arbitro.py` | `decidi(contesto, appresi, stato) -> Piano`: candidati → vincoli rigidi → energia → punteggio a livelli → piano. Funzione pura |
| `ombra.py` | adattatore dalla fotografia HA al `Contesto`, stessi sensori di fascia, medie 10 min e trend della `10`, confronto con lo stato reale, persistenza, metriche |

### Pipeline di `decidi`

1. **Domanda** (`ambiente.py`): aggiorna i latch per zona e produce al più una
   richiesta: `recupero` (livello 3, limite minimo) oppure `accumulo` (livello 6).
2. **Candidati**: Toshiba OFF, HEAT V1, V2, V3 (E0/E70/E80/E90). Richiesta CP ambiente
   sempre 0. Ogni candidato dichiara le risorse usate (`TOSHIBA`; la CP ha
   `CP_COMPRESSORE`, `CP_VENTILATORE`, `CP_RESISTENZA` già modellate per i domini futuri).
3. **Vincoli rigidi**: risorse occupate, notte ≤ V2, massimo raggiunto in una zona →
   solo OFF, permanenza minima 15 minuti dallo stato reale (salvo massimo), dati
   critici non validi → nessun cambio rispetto allo stato reale.
4. **Energia**: ogni candidato acceso riceve un giudizio; per l'accumulo è obbligatorio,
   per il recupero no (il recupero prevale sul budget).
5. **Punteggio a livelli**: prima le domande non servite (per livello), poi la distanza
   dalla velocità preferita, infine i W. La velocità preferita è la più economica fra
   Prima usa `migliore_caldo` se il codice risultante è E70/E80/E90, anche quando è
   ancora da confermare; altrimenti usa la più economica fra E70/E80/E90 con
   affidabilità almeno 0,4 e `da_confermare=false`; in mancanza usa V3 di giorno e V2
   di notte.
   Dopo la permanenza minima, se almeno due dei trend 20/30/60 minuti delle zone in
   recupero non sono positivi, si sale di una velocità entro il limite di fascia.

### Matrice soglie (da `memoria/procedure/config-home-assistant.md`)

| Fascia | Zona | Avvio sotto | Recupero fino a |
|---|---|---|---|
| GIORNO | giorno | T min | T min + 0,5 |
| GIORNO | notte | T min − 0,5 | T min |
| NOTTE | giorno | T min − 1,0 | T min − 0,5 |
| NOTTE | notte | T min − 1,5 | T min − 1,0 |

Accumulo fino a `input_number.ecm_inverno_massimo_accumulo` (23,5 °C); una zona al
massimo arresta subito.

## Parità di stato

Se gli helper HA dei latch (`ecm_inverno_recupero_zona_giorno`,
`ecm_inverno_recupero_zona_notte`, `ecm_inverno_accumulo_attivo`)
sono leggibili, lo stato precedente del decisore li usa (`fonte_stato = "ha"`);
altrimenti usa i propri latch persistiti (`fonte_stato = "proprio"`).
`ecm_inverno_recupero_minimo_attivo` è soltanto l'OR aggregato dei due latch, non un
terzo recupero indipendente. Per il confronto a parità di ingresso il decisore legge
direttamente `sensor.ecm_fascia_climatica_attiva`, le due medie a 10 minuti e i sei
trend 20/30/60 usati dalla `10`.

## Confronto

- Riferimento: lo stato reale Toshiba (spento, oppure RISCALDAMENTO con velocità), cioè
  quello che `10` + WRITE hanno prodotto.
- Non confrontabile: stagione non INVERNO, `09` non in AUTO, prova del motore in corso,
  `automation.10_ecm_inverno` non `on`, Toshiba in un modo diverso da spento/HEAT,
  dati critici non validi.
- Una divergenza conta solo se persiste per 3 cicli consecutivi (ritardi di
  applicazione).

## Metriche di risultato (per giorno)

Minuti sotto la soglia di avvio per zona, kWh Toshiba, kWh importati dalla rete,
cambi di velocità reali, minuti confrontabili, minuti divergenti. Calcolate dal
database ogni 15 minuti.

## Persistenza e pubblicazione

- Tabella `ombra` (una riga per minuto: esito del confronto, velocità Python e reale,
  motivo, fonte stato, zone sotto soglia). Stato del decisore in `settings`
  (`decisore_stato`, JSON versionato).
- `sensor.ecm_engine_ombra_ambiente`: stato `concorde` / `divergente` /
  `non confrontabile`, attributi senza campi che cambiano a ogni minuto (niente
  `seq`/`emesso`), così il recorder scrive solo ai cambi (disco lento).
- `sensor.ecm_engine_ombra_metriche`: metriche del giorno.
- Il piano contiene già `seq`, `emesso`, `valido_fino` per il contratto futuro con HA,
  ma non viene pubblicato su un topic di comando.

## Allineamento verificato sulla `10` live (11/11, sola lettura)

- Avvio accumulo diurno: consenso stabile di carica disponibile **oppure** batteria
  piena, con consenso stabile di prelievo rete spento. Mantenimento: SOC >15%, rete
  ≤300 W, scarica ≤250 W, prelievo stabile spento e FV maggiore del consumo base casa.
- Non esiste un margine sotto il massimo per avviare l'accumulo: può partire finché
  entrambe le zone sono sotto il massimo; una sola zona al massimo arresta subito.
- Notte: la `10` assume Toshiba acceso per il 100% del tempo residuo fino a
  `nilan_mattina`. Il SOC previsto sottrae profilo base casa più W dello Split; con
  copertura profilo inferiore al 100% usa il consumo base corrente costante. Richiede
  inoltre rete ≤300 W e consenso stabile di prelievo spento.
- W di ripiego: V1 1000 W, V2 1100 W, V3 1270 W. Il ranking segue la precedenza
  `migliore_caldo`/tabella descritta sopra.
- All'avvio la `10` imposta `input_number.toshiba_setpoint` a **29 °C**; non lascia
  invariato il setpoint. L'eventuale uso futuro di un setpoint dinamico resta una
  proposta aperta e non fa parte dell'ombra.

Differenze intenzionali: la `10` misura i 15 minuti da
`input_datetime.ecm_inverno_ultima_scelta`, cioè dalla scelta comandata; l'ombra li
misura dal cambio di stato reale Toshiba, come deciso per l'architettura futura. Inoltre
l'ombra applica il limite notturno V2 come vincolo rigido e valuta la sostenibilità
energetica di ogni candidato; la `10` può mantenere brevemente V3 nel passaggio alla
notte se la sua permanenza comandata non è conclusa e valuta l'energia sulla sola
velocità target. Questi scostamenti devono essere riconoscibili nelle divergenze, non
corretti automaticamente.

## Sicurezza

Il decisore non ha accesso a `call_service`. Un errore nel decisore o nell'ombra è
catturato e non interrompe campionamento, apprendimento o prove.

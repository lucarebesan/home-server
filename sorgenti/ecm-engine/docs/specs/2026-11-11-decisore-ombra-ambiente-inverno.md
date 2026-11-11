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
| `ombra.py` | adattatore dal campione HA al `Contesto`, medie 10 min e trend, confronto con lo stato reale, persistenza, metriche |

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
   E70/E80/E90 nella tabella appresa (costo noto), altrimenti V3 di giorno e V2 di notte.
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

Se gli helper HA dei latch (`ecm_inverno_recupero_*`, `ecm_inverno_accumulo_attivo`)
sono leggibili, lo stato precedente del decisore li usa (`fonte_stato = "ha"`);
altrimenti usa i propri latch persistiti (`fonte_stato = "proprio"`). Le temperature di
zona sono medie a 10 minuti calcolate dai campioni del motore, come nella `10`.

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

## Da verificare sul server prima del deploy

Entity id degli helper `ecm_inverno_recupero_*`, `ecm_inverno_accumulo_attivo`,
consensi FV/batteria diurni; soglie di importazione e scarica usate dalla `10` durante
l'accumulo; formula esatta del SOC notturno (in particolare quanta parte della notte si
assume con Toshiba acceso); gestione del setpoint Toshiba (se la `10` lo imposta o
lascia modulare l'inverter). Sono parametri in `decisore/parametri.py`, marcati
`DA VERIFICARE`. Il confronto in ombra serve anche a trovare dove la ricostruzione
differisce dalla `10`.

## Sicurezza

Il decisore non ha accesso a `call_service`. Un errore nel decisore o nell'ombra è
catturato e non interrompe campionamento, apprendimento o prove.

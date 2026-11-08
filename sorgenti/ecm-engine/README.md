# ECM Engine

Servizio che gira in un container sul server di casa (192.168.1.100). Ogni minuto legge da Home Assistant lo stato di Nilan Compact P, Toshiba, zone, batteria e fotovoltaico e salva un campione. Ogni 15 minuti ricostruisce i periodi a combinazione costante e calcola, per fascia di temperatura esterna, quanto consuma e quanto scalda o raffresca ogni combinazione. Pubblica i risultati su MQTT (discovery automatica in HA) e può avviare prove brevi tramite l'automazione 09 (`input_select.ecm_manuale`).

## Deploy

```bash
./deploy.sh
```

Esegue i test, copia il progetto in `~/ecm-engine` sul server con rsync e ricostruisce il container `ecm-engine`.

Il token HA si trova sul server in `~/.config/ecm/ha_token` ed è montato in sola lettura. Mosquitto accetta connessioni anonime: se un giorno servissero credenziali, vanno messe in `~/ecm-engine/.env` sul server (`MQTT_USER`, `MQTT_PASS`) e richiamate con `env_file` nel compose. `.env` non va mai committato.

## Dati

Il database SQLite si trova sul server in `~/ecm-engine/data/engine.db` (`/data/engine.db` dentro il container). I campioni restano per 400 giorni.

## Fermare il servizio

```bash
ssh home@192.168.1.100 'cd ~/ecm-engine && docker compose down'
```

## Entità pubblicate

- `sensor.ecm_engine_stato`: online, prova in corso, errore HA
- `sensor.ecm_engine_in_breve`: frase riassuntiva (attributo `righe`)
- `sensor.ecm_engine_migliore_caldo`, `sensor.ecm_engine_migliore_freddo`
- `sensor.ecm_engine_apprendimento_caldo`, `sensor.ecm_engine_apprendimento_freddo` (%)
- `sensor.ecm_engine_prova_proposta`: attributi `codice`, `durata`, `motivo`, `avviabile`, `motivo_blocco`
- `sensor.ecm_engine_prova_in_corso`
- `sensor.ecm_engine_dettaglio`: attributo `tabella` con una riga per combinazione (fascia esterna attuale)
- `sensor.ecm_engine_da_misurare`: tutte le combinazioni della stagione, attributo `righe` con `sezione` (provabili adesso, non provabili adesso con `motivo`, già misurate)
- `sensor.ecm_engine_ultime_prove`, `binary_sensor.ecm_engine_prova_avviabile`
- `sensor.ecm_engine_avvisi`: attributo `elenco`
- `button.ecm_engine_avvia_prova`: avvia la prova proposta
- `switch.ecm_engine_prove_automatiche`: prove automatiche (10-17, massimo 3 al giorno)

## Correzioni sui dati

Applicate dal segmenter a ogni ricalcolo, quindi anche allo storico:

- **Resistenza ACS** (`correct_acs`): il minuto resta valido con la combinazione dell'aria e la resistenza (circa 1,3 kW) viene tolta dal contatore Nilan.
- **Temperatura esterna** (`fix_text`): la sonda nel condotto della Compact vale solo dopo 10 minuti di ventilazione; negli altri minuti si interpola tra le letture buone vicine.
- **Stati illeggibili per poco** (`hold_states` nel campionamento live): ultimo valore valido per al più 3 minuti.

Per riparare lo storico dal datalogger del gateway (stati mancanti, consumo Compact dai kWh): `python -m ecm_engine.gw_repair --help`. Procedura completa in `memoria/procedure/ecm-engine.md` del repository home-server.

## Specifica

[docs/specs/2026-11-07-ecm-engine-fase1-design.md](docs/specs/2026-11-07-ecm-engine-fase1-design.md)

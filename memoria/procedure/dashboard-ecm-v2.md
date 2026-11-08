# Dashboard ECM v2

Ultima verifica: 2026-11-08.

## Scopo

Dashboard storage separata dalla Overview, `url_path` `ecm-v2`. Tab: Stato, Impostazioni, Diagnostica, Apprendimento. La vista ECM della Overview (`lovelace.lovelace`) resta intatta.

## Sorgente

`Misc/ha-ecm-v2/ecm_v2.yaml` sul PC di Mattia. `build.py` lo converte in JSON e controlla i template JavaScript; i template Jinja vanno provati a parte con `POST /api/template`.

## Deploy senza riavvio

`Misc/ha-ecm-v2/deploy_ws.py` gira dentro il container `homeassistant` (che ha aiohttp) e ha tre modi: `list`, `backup`, `save <file>`. Usa il token in `~/.config/ecm/ha_token`, letto sul server. Prima di ogni salvataggio fa un backup in `~/backup-ecm-v2-<data>.json` sul server.

Le istruzioni d'uso sono nell'intestazione dello script. In sintesi: copiare JSON e script sul server, poi `docker exec -i -e TOKEN="$(cat ~/.config/ecm/ha_token)" homeassistant python3 - ... < deploy_ws.py`.

## Verifica

Aprire `/ecm-v2/apprendimento` e controllare che le altre tab mostrino ancora le loro card. Il risultato del salvataggio deve essere `"success": true`.

## Ripristino

Salvare via WebSocket il JSON di backup più recente.

## Note

- Nei blocchi markdown con tabelle usare `|-` in YAML: con `>-` le righe si uniscono e la tabella si rompe.
- In HA una card si può nascondere solo in base allo stato di un'entità, non a un attributo: per questo il motore pubblica `binary_sensor.ecm_engine_prova_avviabile`.

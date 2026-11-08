# DuckDNS e certificato HTTPS

Ultima verifica: 2026-11-08.

## Come funziona

- `lrhub.duckdns.org` punta all'IP pubblico di casa, aggiornato dal container `duckdns`
  (stack Portainer "server", compose in
  `/var/lib/docker/volumes/opt_data/_data/compose/2/docker-compose.yml`, variabile
  `TOKEN`).
- `nginx` espone Home Assistant su `https://ha.lrhub.duckdns.org` con il certificato
  wildcard `*.lrhub.duckdns.org` (Let's Encrypt, cartella `/opt/certs`).
- Il certificato si ottiene con la challenge DNS su DuckDNS: anche il container
  `letsencrypt` usa il token DuckDNS (variabile `DUCKDNS_TOKEN`).

## Token DuckDNS

Il 2026-11-07 l'update rispondeva `KO`: il token era stato rigenerato sull'account
DuckDNS. Il token nuovo è stato messo nelle due variabili con un comando sudo (backup
del compose in `docker-compose.yml.bak-20261107`), poi duckdns e letsencrypt sono stati
ricreati. Il token non va scritto nei documenti.

Verifica: `docker logs --tail 5 duckdns` deve mostrare "successful", e
`dig +short lrhub.duckdns.org` deve restituire l'IP pubblico di casa.

## Rinnovo del certificato

Il loop interno del container `letsencrypt` (immagine `maksimstojkovic/letsencrypt`) non
rinnova più: certbot 5.x rifiuta l'opzione `--manual-public-ip-logging-ok`, che lo script
dell'immagine usa ancora. Il problema è comparso con l'aggiornamento delle immagini del
2026-11-03. Il rinnovo ora è nella **crontab dell'utente `home`**:

```
17 4 * * * docker exec letsencrypt certbot renew -q > $HOME/certbot-renew.log 2>&1; docker exec nginx nginx -s reload >> $HOME/certbot-renew.log 2>&1
```

- Prova: `docker exec letsencrypt certbot renew --dry-run` (riuscita il 2026-11-07).
- Il certificato in uso scadeva il 2027-01-03; certbot lo rinnova a 30 giorni dalla
  scadenza.
- Prima non esisteva nessun hook che ricaricasse nginx dopo il rinnovo: ora lo fa la
  crontab.
- Se il compose viene rifatto, la soluzione pulita è sostituire nginx e letsencrypt con
  SWAG (nginx e certbot nello stesso container, con supporto DuckDNS).

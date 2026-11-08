# Certificato HTTPS e DuckDNS

Ultima verifica: 2026-11-07.

## Stato

- Il dominio `*.lrhub.duckdns.org` è aggiornato dal container `duckdns`. Il token è nello stack Docker (compose di Portainer), non va riportato qui. Il 07/11 il token era stato rigenerato sull'account DuckDNS ed è stato aggiornato nello stack (backup del compose: `docker-compose.yml.bak-20261107`).
- Il certificato è emesso dal container `letsencrypt` con challenge DNS DuckDNS. Scadenza osservata il 07/11: 2027-01-03.
- Il rinnovo interno al container non funziona più: certbot 5.x rifiuta l'opzione `--manual-public-ip-logging-ok`. Il rinnovo è affidato alla **crontab dell'utente `home`**:
  ```
  17 4 * * * docker exec letsencrypt certbot renew -q > $HOME/certbot-renew.log 2>&1; docker exec nginx nginx -s reload >> $HOME/certbot-renew.log 2>&1
  ```

## Verifica

```sh
ssh hp 'crontab -l; cat ~/certbot-renew.log; docker exec letsencrypt certbot renew --dry-run'
ssh hp 'docker logs --tail 5 duckdns'   # deve rispondere OK, non KO
```

## Da fare

Con un server nuovo o con il compose rifatto, sostituire il container `letsencrypt` (per esempio con SWAG) invece di ricopiare la crontab.

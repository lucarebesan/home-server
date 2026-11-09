---
name: certificato-duckdns
description: Accesso esterno a Home Assistant (ha.lrhub.duckdns.org) - DuckDNS che risponde KO, DNS non aggiornato, certificato HTTPS in scadenza o non rinnovato, nginx. Usala quando HA non è raggiungibile da fuori casa.
---

# DuckDNS e certificato

Riferimento: `memoria/procedure/duckdns-certificato.md`.

## Verifiche (sola lettura)

```sh
ssh home@192.168.1.100 'docker logs --tail 5 duckdns'                 # "successful", non "KO"
dig +short lrhub.duckdns.org                           # = IP pubblico di casa
ssh home@192.168.1.100 'curl -s -4 https://api.ipify.org'              # IP pubblico visto dal server
ssh home@192.168.1.100 'echo | openssl s_client -connect 127.0.0.1:443 -servername ha.lrhub.duckdns.org 2>/dev/null | openssl x509 -noout -enddate'
ssh home@192.168.1.100 'crontab -l; cat ~/certbot-renew.log'
```

## Casi noti

- **DuckDNS risponde `KO`:** quasi sempre il token è stato rigenerato sull'account
  DuckDNS. Il token nuovo va chiesto all'utente e messo nelle variabili `TOKEN` (duckdns)
  e `DUCKDNS_TOKEN` (letsencrypt) del compose dello stack "server". Il compose richiede
  sudo: consegna all'utente un one-liner `ssh -t` che fa prima il backup del file e poi
  `docker compose -p server -f <file> up -d duckdns letsencrypt`. Non scrivere mai il
  token nei documenti o nei commit.
- **Certificato non rinnovato:** il loop interno del container `letsencrypt` è rotto
  (certbot 5 rifiuta un'opzione dello script). Il rinnovo lo fa la crontab di `home`.
  Prova con `docker exec letsencrypt certbot renew --dry-run`; il rinnovo DNS dipende da
  un token DuckDNS valido. Dopo un rinnovo serve `docker exec nginx nginx -s reload`.
- **Rifacimento del compose:** sostituire nginx e letsencrypt con SWAG, invece di
  ricopiare la crontab.

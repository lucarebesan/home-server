# Box, MEGA e Nextcloud sul mini PC

Ultima verifica: 2026-11-25.

## Scopo e stato

Nextcloud è disponibile su `https://cloud.lrhub.duckdns.org`, con l'account
amministratore interno `luca`. L'indirizzo email è associato all'account e può
essere usato per l'accesso. La password si cambia in Impostazioni personali →
Sicurezza; il valore non è nel repository. La copia di Box e MEGA è separata,
e la disponibilità dei file in Nextcloud va verificata dopo ciascuna importazione.

Box **non** va disdetto prima della verifica completa e di una copia di sicurezza
indipendente dal solo SSD del mini PC. Nessuna cancellazione viene eseguita su
Box o MEGA durante la migrazione.

## Configurazione corrente

- Mini PC Ubuntu, accesso operativo `ssh home@192.168.1.100`.
- Stack Docker in `/home/home/nextcloud/compose.yaml`, con PostgreSQL, Redis,
  applicazione e cron. I dati Nextcloud e il database sono in volumi Docker
  `nextcloud_html` e `nextcloud_db`.
- File `.env` con segreti iniziali in `/home/home/nextcloud/.env`, permessi 600.
  La password amministratore è stata cambiata dall'utente dopo l'installazione;
  non assumere che il valore iniziale nel file sia ancora valido.
- Proxy nginx nel container `nginx`, configurazione host `/opt/nginx/nginx.conf`.
  Il blocco `cloud.lrhub.duckdns.org` inoltra verso `nextcloud-app:80` nella rete
  Docker `server_default`, usa il certificato wildcard in `/opt/certs` e forza
  HTTPS. Backup della configurazione precedente:
  `/opt/nginx/nginx.conf.before-nextcloud-20261125`.
- Il DNS pubblico di `cloud.lrhub.duckdns.org` punta all'IP di casa; certificato
  Let's Encrypt valido per `*.lrhub.duckdns.org` alla verifica. La configurazione
  del rinnovo è in `duckdns-certificato.md`.
- Archivi grezzi, privati e separati:
  `/home/home/box-import` e `/home/home/mega-import`. Recuperi di versioni
  storiche Box: `/home/home/box-recovered`.
- Rclone in `/home/home/.local/bin/rclone`, remoti `box:` e `mega:` configurati
  in `/home/home/.config/rclone/rclone.conf` (segreto, permessi 600).
- Log e report tecnici privati in `/home/home/.local/state/`. I nomi dei file
  possono contenere dati personali: non pubblicare i log.
- Sorgenti degli script di migrazione in `sorgenti/nextcloud/migrazione/` nel
  repository; copie eseguibili sul mini PC in `/home/home/.local/state/`.

## Verifiche rapide

```sh
ssh home@192.168.1.100 'docker ps --filter name=nextcloud'
ssh home@192.168.1.100 'docker exec -u www-data nextcloud-app php occ status'
ssh home@192.168.1.100 'docker exec -u www-data nextcloud-app php occ setupchecks'
ssh home@192.168.1.100 'cat ~/.local/state/box-verified.status ~/.local/state/mega-verified.status'
```

La pagina di accesso risponde su `https://cloud.lrhub.duckdns.org`. In caso di
avviso certificato, controllare **prima** l'URL digitato: `duckdns`, non `dockdns`.
Il 25/11 l'iPhone mostrava un certificato scaduto di un altro sito per un
indirizzo digitato erroneamente; con l'indirizzo corretto l'accesso è riuscito.

## Copia e verifica dei cloud

Le copie sono da cloud a mini PC, senza passare per il PC di lavoro. La copia
Box è monitorata da `/home/home/.local/state/supervise_cloud_copy.py`: dopo la
fine, `rclone check` confronta il remoto con l'archivio. Se trova differenze
ripete la copia e il controllo (fino a tre controlli).

MEGA gratuito ha risposto `509 Bandwidth Limit Exceeded` dopo circa 5,3 GiB il
25/11 alle 17:15. Il download è stato sospeso senza perdere i file locali.
`/home/home/.local/state/resume_mega_quota.py` attende sei ore fra i tentativi,
poi riprende con `rclone copy --size-only` e verifica quando la copia termina.
Il primo tentativo alle 23:22 ha ancora incontrato la quota; quello delle 07:14
del 26/11 è terminato e il controllo alle 07:25 ha trovato 51.795 file
corrispondenti. Il supervisore MEGA precedente è stato fermato per evitare
tentativi ripetuti durante il blocco. L'archivio attivo MEGA è stato importato
in Nextcloud nella cartella `MEGA`, indicizzato con 51.795 file e zero errori.
L'audit dei percorsi non ha trovato duplicati, mancanze o differenze di
dimensione. `rclone size mega:` indica 14.409.517.883 byte di file attivi;
`rclone about mega:` indica 17,439 GiB occupati nell'account. La differenza
potrebbe appartenere al cestino o alle versioni storiche: non è inclusa nella
copia del cloud drive attivo e resta da classificare.

Se una verifica resta fallita, il mini PC invia un avviso tramite Home Assistant
a `notify.mobile_app_iphone_luca`. I file `box-verified.status` e
`mega-verified.status` contengono `verified` oppure `failed`; non basta il
contatore di avanzamento di rclone, perché il totale viene scoperto durante la
scansione. I processi `postprocess_cloud_import.py` attendono questi esiti e
avviano le importazioni separate in Nextcloud.

Box fornisce hash SHA-1; la copia e il controllo usano `--checksum` e
`--create-empty-src-dirs`. MEGA non fornisce hash/modtime a rclone: si usa
`--size-only`, più il controllo degli errori e di eventuali nomi duplicati nei
log. I file con lo stesso nome e percorso possono esistere su MEGA: prima di
dichiarare completa la migrazione cercare tali avvisi e risolverli senza
cancellare oggetti nel cloud.

## File cifrati dal ransomware

Su Box è stato osservato `README-RECOVER-uD1zw1ZbZm.txt` e file con suffisso
`.uD1zw1ZbZm`. La nota è una richiesta di riscatto, non una procedura da
eseguire. L'archivio grezzo mantiene note e file cifrati; Nextcloud riceve
soltanto file non marcati e versioni precedenti verificate. Non cancellare gli
originali su Box: alcune versioni precedenti possono ancora essere recuperate.

La scansione è in `~/.local/state/analyze_box_import.py` (`box` o `mega` come
argomento). Per i file Box cifrati, `audit_box_versions.py` legge in sola
lettura la cronologia Box; `recover_box_versions.py` scarica versioni precedenti
in `box-recovered`, confronta dimensione e SHA-1 forniti da Box e controlla il
formato dei documenti riconoscibili. I report JSON sono nella stessa cartella
di stato, con permessi 600. I file non recuperabili o dal formato incerto
restano nell'archivio separato e vanno segnalati all'utente.

## Importazione in Nextcloud

Solo dopo un file `.status` con `verified` e il report finale di analisi si
esegue `import_box_to_nextcloud.py` in un container temporaneo Python senza
rete, montando l'archivio originale in sola lettura, il report e il volume
`nextcloud_html`. Per Box si monta anche `box-recovered` in sola lettura.
L'importazione crea `Box.com` e `MEGA` come cartelle distinte nell'account
`luca`, esclude note e file cifrati e incorpora soltanto versioni Box con hash
e formato verificati. Lo script è ripetibile: salta file già identici e ferma
le collisioni. Dopo la copia, eseguire come `www-data`:

```sh
docker exec -u www-data nextcloud-app php occ files:scan --path='luca/files/Box.com'
docker exec -u www-data nextcloud-app php occ files:scan --path='luca/files/MEGA'
```

Confrontare il report `nextcloud-box-import-report.json` o
`nextcloud-mega-import-report.json` con il totale del rispettivo archivio.
Controllare inoltre l'apertura di campioni dal browser e dal telefono.
Il container temporaneo esegue come root per impostare la proprietà dei file
Nextcloud: dopo aver scritto il report privato (modo 600), ne assegna la
proprietà all'utente che possiede l'archivio sorgente. Il processo di controllo
esterno può così leggere il report. La versione precedente del 25/11 lasciava
il report `root:root`, causando un errore di permessi dopo una copia e scansione
già riuscite; correggere solo il proprietario del report e ripetere il controllo.

## Ripristino e limiti

Per un errore di proxy, ripristinare il backup di nginx con un operatore
autorizzato, validare con `nginx -t`, poi ricaricare nginx. Non eliminare i
volumi Nextcloud senza una copia verificata di file e database. Nessun backup
automatico indipendente dal mini PC è stato ancora configurato. Le email di
recupero password non funzionano finché non viene configurato un server SMTP.

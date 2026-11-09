# Migrazione dall'HP al mini PC

Ultima verifica: 2026-11-09 16:09 (cutover completato e verificato, vedi "Esito").

Scopo: spostare tutti i servizi dall'HP (`hp-homeassistant`) al mini PC (`minipc`) con
downtime breve e l'HP intatto come ripristino. Script in `sorgenti/migrazione/`.

## Macchine

| | HP (vecchio) | Mini PC (nuovo) |
|---|---|---|
| Hostname | `hp-homeassistant` | `minipc` |
| Hardware | i3-7100U, 3,2 GiB RAM, HDD | Ryzen 7 5825U, 14 GiB RAM, SSD 477 GB |
| OS | Ubuntu 26.04.1, NetworkManager | Ubuntu Server 26.04.1, netplan/networkd |
| Rete | WiFi, `.100` (prenotazione DHCP sul box) | ethernet `enp2s0` `68:1d:ef:66:29:75` (oggi `.76`), WiFi `wlp1s0` `44:90:ba:32:32:bd` (oggi `.25`) |
| Utenti | `home` (uid 1000) | `minipc` (uid 1000, admin con sudo), `home` (uid 1001, gruppo docker, solo chiave SSH, niente sudo) |

Rete del mini PC: ethernet preferita (metrica 100), WiFi di riserva (metrica 600), file
`/etc/netplan/60-ethernet.yaml`. Il file WiFi dell'installer non è stato toccato.

## Scelte

- Immagini Docker **copiate dall'HP** (`docker save | docker load`), non scaricate:
  HA resta 2026.9.3 anche se il compose dice `:latest`; le immagini locali
  (`ecm-engine`, `dtbridge`, `dtdiag`, `crosschex-webapi`) sono identiche. Gli ID
  differiscono perché il mini PC usa lo store containerd; verificati identici layer e
  data di build (11/11).
- Utente `home` e percorsi `/home/home`, `/opt` identici all'HP: compose, crontab,
  script e procedure restano validi.
- Niente sudo per copiare: `home` è nel gruppo docker su entrambe le macchine; i file
  root si leggono/scrivono tramite un container `alpine`.
- Copia diretta HP → mini PC con la chiave temporanea `~/.ssh/id_migrazione` dell'HP
  (commento `migrazione-hp-temporanea` in `authorized_keys` di `home@minipc`).
  Misurati: 39 MB/s diretto, ~3 MB/s passando dal Mac (entrambi in WiFi).
- Ogni cartella viene specchiata (svuotata e ricopiata), così i `-wal` SQLite di una
  copia precedente non si mescolano al DB finale.
- Stack Portainer creati con gli stessi nomi di progetto (`server`, `homeassistant`,
  `anviz-local-api`, `opt`) e la stessa `working_dir`, così Portainer li riconosce.
- Non creati: `grott`, `matter-hub`, `adguard`, `reolink-tv` (fermi anche sull'HP; i
  dati in `/opt` sono copiati). `dtdiag` sì.

## Passi già fatti (09/11)

1. `01-setup-minipc.sh` (sudo): fuso Europe/Rome, Docker CE, rsync, bluez, Bluetooth,
   netplan ethernet.
2. `02-utente-home.sh` (sudo): utente `home` con le stesse chiavi di `minipc`.
3. Immagini copiate (14,7 min via Mac).
4. `03-copia-dati.sh prova`: 5 min 54 s diretto dall'HP (prima 16,5 min via Mac).
   HA occupa 1,9 GB, di cui DB 1,2 GB, ~8.900 file. Limite: disco dell'HP.
5. `04-crea-container.sh`: 11 container in stato `Created`, nessuno avviato.
6. Riavvio del mini PC con cavo: nessun container partito da solo, ethernet preferita.

## Esito del cutover (09/11)

- Servizi fermi dalle 15:51:02 (HP) a 16:04:20 (mini PC): **~13 min**. Copia finale
  4 min 44 s; checksum dei DB HA ed ECM identici tra HP e mini PC; nella config HA
  mancano solo le `__pycache__` (escluse apposta).
- Prenotazione `.100` sul box spostata da Claude via interfaccia web (sessione già
  autenticata dall'utente). Durante l'operazione è stata aperta per errore la voce del
  relè Giorno1: chiusa con Annulla, verificata invariata.
- HA risponde in ~5 s dall'avvio (prima minuti); esterno 200 con certificato valido;
  71 switch relè/luci disponibili; `nilan_batch` 39/39; ECM campiona ogni 60 s; MQTT con
  `ecm_engine`, `dtbridge`, `dtdiag`; Portainer e Configurator 200.
- Confronto con l'ultimo stato sull'HP: delle 369 entità `unavailable` solo 10 erano
  valide prima, tutte Bluetooth. Causa: l'integrazione Bluetooth di HA conosceva solo
  l'adattatore dell'HP. Aggiunto `hci0` `44:90:BA:32:32:BE` (flusso di configurazione) e
  rimossa la voce vecchia `C8:21:58:3F:2C:BB`: ATC C1A9 tornato. Le altre `unavailable`
  (anche `nilan_*` e `toshiba_*` vecchie) lo erano già sull'HP.
- Chiave temporanea rimossa da `authorized_keys` del mini PC; restano sull'HP spento i
  file `~/.ssh/id_migrazione*` (innocui senza la riga autorizzata).

## Cutover (fatto il 09/11; passi per ripeterlo)

Prerequisito: ok esplicito dell'utente e accesso all'interfaccia del box Iliad.

1. Sull'HP fermare i servizi. Qui fermare i singoli container **è voluto**: al boot non
   ripartono e l'HP resta inerte come riserva.
   `docker stop homeassistant ecm-engine dtbridge dtdiag crosschex-webapi hassconfigurator nginx letsencrypt duckdns mosquitto opt-portainer-1`
2. Copia finale (lo script rifiuta di partire se un servizio è ancora attivo):
   `ssh home@192.168.1.100 'NEW=home@192.168.1.76 bash ~/03-copia-dati.sh finale </dev/null'`
3. Host key SSH dell'HP sul mini PC, così chi usa `.100` non vede l'avviso di chiave
   cambiata. Le chiavi private passano in pipe, mai su disco intermedio:
   ```
   ssh home@192.168.1.100 "docker run --rm -v /etc/ssh:/s:ro alpine sh -c 'cd /s && tar -cf - ssh_host_*'" \
     | ssh home@192.168.1.76 "docker run --rm -i -v /etc/ssh:/s alpine tar -C /s -xpf -"
   ```
4. Crontab di `home` sul mini PC uguale a quella dell'HP:
   `ssh home@192.168.1.100 'crontab -l' | ssh home@192.168.1.76 'crontab -'`
5. Spegnere l'HP: `ssh -t home@192.168.1.100 'sudo poweroff'`.
6. Box Iliad: spostare la prenotazione `.100` sul MAC ethernet del mini PC
   `68:1d:ef:66:29:75`. Il port forward 443 → `.100` resta valido.
7. Riavviare il mini PC (`ssh -t minipc@192.168.1.76 'sudo reboot'`): prende `.100` su
   ethernet e carica le host key dell'HP.
8. Avviare i container:
   `ssh home@192.168.1.100 'bash -s -- avvia' < sorgenti/migrazione/04-crea-container.sh`

## Verifica dopo il cutover

- `docker ps`: 11 container `Up`; log di `homeassistant`, `ecm-engine`, `dtbridge` senza errori.
- HA da fuori: `https://ha.lrhub.duckdns.org`; certificato valido.
- Relè: stato coerente in HA (solo lettura; niente comandi senza ok).
- ECM: campioni ogni 60 s, MQTT connesso.
- Bluetooth HA: compare l'adattatore nuovo `44:90:BA:32:32:BE`; rimuovere quello vecchio
  dopo aver verificato che i sensori BLE (bthome, ble_monitor) arrivano.
- `ssh home@192.168.1.100` senza avviso di host key.
- Pulizia: rimuovere la riga `migrazione-hp-temporanea` da `~home/.ssh/authorized_keys`
  del mini PC e `~/.ssh/id_migrazione*` sull'HP; poi aggiornare `inventario.md`.

## Ripristino

Mini PC: `docker stop` di tutti i container e spegnimento. Box: prenotazione `.100` di
nuovo sul MAC WiFi dell'HP. HP: accendere e avviare i container fermati al passo 1
(`docker start …`), poi verificare.

## Questioni aperte

- `ble_monitor` ha ancora nelle opzioni il MAC dell'adattatore HP: a ogni avvio scrive
  un errore e passa da solo all'adattatore di default (funziona). Da aggiornare dalle
  opzioni dell'integrazione.
- iBeacon `74278bda…` non ricevuto dal mini PC (sull'HP −88 dBm, al limite): probabile
  portata, dipende da dove sta il mini PC.
- Quando non serve più come riserva: cancellare `~/.ssh/id_migrazione*` sull'HP e
  decidere cosa fare dell'HP.
- I 4 "Created" mai esistiti sul mini PC (`grott`, `matter-hub`, `adguard`,
  `reolink-tv`) andranno ricreati dai loro stack solo se servono.
- `ha_backup_daily.sh` non compare nella crontab di `home`: non è chiaro se e come è
  pianificato.
- Alias `hp` non configurato su tutti i PC (mancava sul Mac di Mattia il 09/11).

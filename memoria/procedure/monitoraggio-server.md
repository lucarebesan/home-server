# Stato e monitoraggio del server

Ultima verifica: 2026-11-08, tramite `ssh hp` come `home`. I comandi seguenti si eseguono sul server; i risultati cambiano nel tempo. Le verifiche sono in sola lettura, salvo diversa indicazione. Non incollare nei documenti log contenenti segreti o dati personali.

## Controllo rapido

```sh
hostname; date; uptime
free -h
df -hT / /boot/efi
systemctl --failed --no-pager
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

- `uptime`: durata dall'avvio e carico medio a 1, 5 e 15 minuti. Confrontare il carico sostenuto con le 4 CPU logiche, non con una percentuale.
- `free -h`: osservare soprattutto la memoria disponibile e l'andamento dello swap; swap usato da solo non dimostra un problema.
- `df`: controllare spazio e tendenza nel tempo. L'8 novembre `/` era all'8%, circa 403 GiB disponibili. `df -i /` controlla invece gli inode.
- `systemctl --failed`: elenca unità fallite; un servizio statico può risultare fallito anche se attivato da un timer.
- `docker ps -a`: mostra anche container arrestati; verificare se l'arresto è intenzionale. `Up` non prova che l'applicazione sia sana. Se presente, lo stato `healthy`/`unhealthy` compare nella colonna Status.

## Diagnosi per risorsa

```sh
top -o %CPU                 # q per uscire
ps aux --sort=-%mem | head -15
vmstat 1 5                 # campioni successivi, osservare memoria, swap e attesa I/O
iostat -xz 1 3             # se disponibile: tendenze e latenza dei dischi
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL
journalctl --disk-usage
```

Per una temperatura leggibile in millesimi di grado: `cat /sys/class/thermal/thermal_zone7/temp` e `cat /sys/class/thermal/thermal_zone7/type`. Verificare prima che il tipo sia ancora `x86_pkg_temp`: la numerazione può cambiare. Al controllo era 44 °C; alcune zone non erano leggibili. `sensors` e `smartctl` non erano installati, quindi non è stata verificata la salute SMART del disco. Non confondere spazio libero e salute fisica del disco.

In caso di pressione su RAM, CPU o disco, identificare prima processo, durata e causa; controllare i log e lo stato del servizio interessato. Evitare pulizie, terminazioni o riavvii alla cieca. Per SMART valutare l'installazione di `smartmontools` e la verifica con privilegi adeguati; non è stata installata durante questo controllo.

## Servizi, container e log

```sh
systemctl status docker ssh --no-pager -l
systemctl status logrotate.service --no-pager -l
systemctl list-timers --all --no-pager
journalctl -p warning -b --no-pager -n 100
docker stats --no-stream
docker logs --tail 100 homeassistant
```

Sostituire `homeassistant` con il nome del container interessato. `docker logs` può contenere informazioni sensibili. L'utente `home` riusciva a elencare i container; `sudo -n -v` non riusciva, quindi gli interventi privilegiati possono richiedere autenticazione.

Prima di riavviare un servizio o container, verificare che sia effettivamente necessario, capire le dipendenze e concordare un'eventuale interruzione. Dopo un'azione, verificare stato, log e funzionamento dell'applicazione. Evitare `docker system prune`, cancellazioni di volumi e riavvii globali senza averne verificato conseguenze e backup.

## Anomalia osservata: logrotate

L'8 novembre `logrotate.service` era fallito: `/etc/logrotate.d/cloud-init` e `/etc/logrotate.d/cloud-init-base` contenevano entrambi una regola per `/var/log/cloud-init*.log`. Il timer risultava attivo e aveva una prossima esecuzione prevista. Questo può impedire la corretta rotazione di alcuni log; non si è stabilito che tutti i log siano privi di rotazione.

Per rivalutare:

```sh
systemctl status logrotate.service --no-pager -l
journalctl -u logrotate.service -b --no-pager -n 100
systemctl list-timers logrotate.timer --no-pager
grep -Hn cloud-init /etc/logrotate.d/*cloud*
```

Prima di correggere, verificare proprietà dei file e configurazione dei pacchetti, valutare quale regola mantenere e conservarne una copia. Testare la configurazione con `logrotate -d /etc/logrotate.conf` (modalità diagnostica, non esegue la rotazione), usando privilegi appropriati se necessari. Una correzione e il successivo avvio del servizio modificano il sistema e vanno valutati separatamente. Non è stata effettuata alcuna correzione.

## Backup e limiti del controllo

Esistono `/home/home/ha_backup_daily.sh` e la directory privata `/home/home/ha-backups`. La sola presenza di script e directory non prova che il backup sia pianificato, recente, completo o ripristinabile. La verifica del crontab dell'utente non ha mostrato righe contenenti `backup` o `ha_backup`; potrebbero esistere altre pianificazioni o destinazioni. Esaminare configurazione, esiti e destinazioni senza esporre segreti, poi verificare il ripristino con una procedura dedicata. Non sono stati effettuati test di ripristino.

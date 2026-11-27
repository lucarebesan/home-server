# Rinnovo password gateway Higeco

Installato sul mini PC il 27/11/2026 in `/home/home/higeco-password/renew.py`.
La prova reale ha rinnovato `user` e `admin`, ripristinato le regole e lasciato
`sensor.nilan_batch` a 40 valori aggiornati. `renew.py` usa la stessa API HTTP
della pagina Utenti del gateway `192.168.1.171`, senza librerie Python esterne.

## Sequenza

1. Login admin, lettura degli ID `user`/`admin` e di tutte le regole password.
2. Salvataggio persistente delle regole originali sul mini PC.
3. Disattivazione temporanea dei cinque requisiti opzionali e verifica della lettura.
4. Rinnovo della password attuale di `user`, poi di `admin`, nella stessa sessione.
5. Ripristino e rilettura delle regole originali; verifica dei login di entrambi.

Dal 27/11 i login di verifica e la sessione usata dall'esecuzione terminano
con `logoutUser`. La correzione è stata provata con sei test offline; non è
stato fatto un altro login reale dopo il blocco delle nuove sessioni admin.

Se un passaggio fallisce, il programma tenta il ripristino immediato. Il file
`~/.local/state/higeco-password/restore-rules.json` consente di riprovarlo al
successivo avvio dopo un'interruzione. Un errore del rinnovo invia una notifica
all'iPhone tramite Home Assistant, se il token HA locale è disponibile. Dopo
un rinnovo riuscito invia una notifica di successo; se HA non la accetta, la
ritenta al successivo controllo giornaliero. La notifica del rinnovo di prova
del 27/11 è stata ricevuta sull'iPhone di Luca.

Le password sono inserite dall'utente in un prompt nascosto e conservate solo in
`~/.config/higeco-password/credentials.json` sul mini PC, con permessi `600`.
Non inserirle in chat, nella riga di comando o nel repository. Il gateway usa
HTTP sulla LAN, come già fa la sua pagina web.

## Verifica e ripetizione della prova

1. Se le password cambiano, aggiornare il file locale delle credenziali in
   modo interattivo; `--setup` crea il file solo se è assente e non lo sovrascrive.
2. Eseguire `python3 /home/home/higeco-password/renew.py --check`: accede a entrambi
   gli account e legge utenti/regole, senza scrivere sul gateway.
3. Con l'utente presente e l'accesso admin funzionante, eseguire
   `python3 /home/home/higeco-password/renew.py --renew`. Controllare l'esito,
   le regole nel pannello, entrambi i login e `sensor.nilan_batch` in HA.

Il programma può essere eseguito una volta al giorno con `--scheduled`. Rinnova
solo se manca un successo dal **1° gennaio, marzo, maggio, luglio, settembre o
novembre** più recente, a partire dal 2027. Una giornata saltata viene recuperata
alla prima esecuzione successiva. Un controllo al boot serve anche a ripristinare
regole rimaste temporaneamente disattivate. Le esecuzioni concorrenti sono bloccate.

Pianificazione attiva nel crontab di `home` dal 27/11/2026:

```cron
15 3 * * * /usr/bin/python3 /home/home/higeco-password/renew.py --scheduled >>/home/home/.local/state/higeco-password/renew.log 2>&1 # HIGECO_PASSWORD
@reboot /bin/sleep 120 && /usr/bin/python3 /home/home/higeco-password/renew.py --scheduled >>/home/home/.local/state/higeco-password/renew.log 2>&1 # HIGECO_PASSWORD_BOOT
```

Per fermare il rinnovo, togliere solo le due righe marcate `HIGECO_PASSWORD` dal
crontab. Se `restore-rules.json` è presente, prima del fermo verificare nel
pannello che le regole siano state ripristinate. Non cancellare il file di
recupero prima della verifica.

## Recupero VPN dopo la prova del 27/11

La prova temporanea senza VPN ha mostrato che l'app Exrg su rete cellulare
apre l'impianto ma lascia dati e comandi fermi. Nuovi login admin sono stati
poi rifiutati. Dopo circa 30 minuti senza altri accessi Luca ha segnalato il
ritorno della possibilità di login. `recover_vpn.py now` ha fatto un singolo
accesso admin alle 13:03 del 27/11, ripristinato VPN e collegamento
gateway-server, chiuso la sessione e inviato un avviso iPhone ricevuto da
Luca. **L'app Exrg restava però senza dati e comandi**: lo stato del server
letto dal gateway non prova l'esito dell'app. Su richiesta di Luca non fare
altri accessi admin per ora.

Il backup privato della configurazione iniziale è
`~/.local/state/higeco-password/vpn-test-before.json`. La riga cron
temporanea `HIGECO_VPN_RECOVERY` è stata rimossa dopo il successo; il suo
stato rimane `complete=True`, `attempts=1`, notifica non pendente. Le
richieste HA sono state riprese su richiesta di Luca e ora hanno un'attesa
condivisa per i guasti (procedura Higeco).

Alle 13:31 del 27/11 un audit di sola lettura, autorizzato per una sessione
admin unica, ha trovato l'intera configurazione server identica al backup e
`abilVpn=1`, ma `getServerStatus.successo=0`. Quindi l'opzione VPN è attiva,
mentre il collegamento al server Exrg non risultava operativo. La notifica
del recupero precedente era troppo ottimista: il valore `successo=1` letto
subito dopo il salvataggio non ha garantito continuità. `audit_vpn.py` legge
e confronta i campi senza stamparne i valori, chiude la sessione e non
scrive sul gateway. **Non ripeterlo senza una nuova decisione di Luca:**
troppi login admin possono essere rifiutati dal gateway.

Stato senza contattare il gateway:
`python3 /home/home/higeco-password/recover_vpn.py status`. Dettagli,
backup, limiti e ripristino in `memoria/procedure/gateway-higeco.md`.

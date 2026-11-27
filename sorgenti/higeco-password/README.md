# Rinnovo password gateway Higeco

Bozza pronta per la prova reale, **non ancora installata**. `renew.py` usa la stessa API
HTTP della pagina Utenti del gateway `192.168.1.171`, senza librerie Python esterne.

## Sequenza

1. Login admin, lettura degli ID `user`/`admin` e di tutte le regole password.
2. Salvataggio persistente delle regole originali sul mini PC.
3. Disattivazione temporanea dei cinque requisiti opzionali e verifica della lettura.
4. Rinnovo della password attuale di `user`, poi di `admin`, nella stessa sessione.
5. Ripristino e rilettura delle regole originali; verifica dei login di entrambi.

Se un passaggio fallisce, il programma tenta il ripristino immediato. Il file
`~/.local/state/higeco-password/restore-rules.json` consente di riprovarlo al
successivo avvio dopo un'interruzione. Un errore del rinnovo invia una notifica
all'iPhone tramite Home Assistant, se il token HA locale è disponibile.

Le password sono inserite dall'utente in un prompt nascosto e conservate solo in
`~/.config/higeco-password/credentials.json` sul mini PC, con permessi `600`.
Non inserirle in chat, nella riga di comando o nel repository. Il gateway usa
HTTP sulla LAN, come già fa la sua pagina web.

## Prova controllata

1. Installare una copia del file in `/home/home/higeco-password/renew.py`.
2. Da una shell interattiva, eseguire `python3 /home/home/higeco-password/renew.py --setup`.
3. Eseguire `python3 /home/home/higeco-password/renew.py --check`: accede a entrambi
   gli account e legge utenti/regole, senza scrivere sul gateway.
4. Con l'utente presente e l'accesso admin funzionante, eseguire
   `python3 /home/home/higeco-password/renew.py --renew`. Controllare l'esito,
   le regole nel pannello, entrambi i login e `sensor.nilan_batch` in HA.
5. Installare la pianificazione solo dopo il successo della prova reale.

Il programma può essere eseguito una volta al giorno con `--scheduled`. Rinnova
solo se manca un successo dal **1° gennaio, marzo, maggio, luglio, settembre o
novembre** più recente, a partire dal 2027. Una giornata saltata viene recuperata
alla prima esecuzione successiva. Un controllo al boot serve anche a ripristinare
regole rimaste temporaneamente disattivate. Le esecuzioni concorrenti sono bloccate.

Pianificazione prevista nel crontab di `home`, **da non aggiungere prima del test**:

```cron
15 3 * * * /usr/bin/python3 /home/home/higeco-password/renew.py --scheduled >>/home/home/.local/state/higeco-password/renew.log 2>&1 # HIGECO_PASSWORD
@reboot /bin/sh -c 'sleep 120; /usr/bin/python3 /home/home/higeco-password/renew.py --scheduled >>/home/home/.local/state/higeco-password/renew.log 2>&1' # HIGECO_PASSWORD_BOOT
```

Per fermare il rinnovo, togliere solo le due righe marcate `HIGECO_PASSWORD` dal
crontab. Se `restore-rules.json` è presente, prima del fermo verificare nel
pannello che le regole siano state ripristinate. Non cancellare il file di
recupero prima della verifica.

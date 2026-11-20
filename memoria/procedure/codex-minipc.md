# Codex sul mini PC

Ultima verifica: 2026-11-20 (login, controllo remoto, telefono, crontab e Hand off).

## Stato e prerequisiti

- Server: `home@192.168.1.100`, Codex CLI in `/home/home/.local/bin/codex`.
- L'utente deve abilitare nelle impostazioni di sicurezza di ChatGPT l'accesso
  tramite codice dispositivo per Codex e gli altri prodotti indicati.
- Non incollare password, token, file `auth.json` o codici di abbinamento nel
  repository. I codici temporanei vanno inseriti solo nelle pagine/app ufficiali.

## Accesso ChatGPT sul server

1. Dal PC di casa, con SSH funzionante, avviare
   `ssh -tt home@192.168.1.100 'codex login --device-auth'`.
2. Sul browser dell'utente aprire l'URL mostrato dal comando e inserire il
   codice temporaneo. Usare lo stesso account ChatGPT dell'app Codex.
3. In una nuova sessione SSH verificare
   `ssh home@192.168.1.100 'codex login status'`:
   deve indicare `Logged in using ChatGPT`.

## Controllo remoto

1. Avviare `ssh home@192.168.1.100 'codex remote-control start --json'`.
   La risposta deve indicare `status: connected` e
   `remoteControlEnabled: true`.
2. Generare il codice di abbinamento con
   `ssh home@192.168.1.100 'codex remote-control pair'`. Inserirlo
   nell'app Codex del dispositivo che deve controllare il mini PC. Sul telefono
   usare "Inserisci codice manualmente" nella schermata del QR.
3. Verificare nell'app che `minipc` compaia come `Connesso` e aprire una chat
   di prova eseguita sul mini PC. Il 20/11 la connessione dal PC di lavoro è
   stata verificata; il 20/11 `minipc` era visibile anche nell'app del telefono,
   senza ancora una chat di prova.
4. Per interrompere il controllo remoto usare
   `ssh home@192.168.1.100 'codex remote-control stop'`.

La funzione `remote-control` della CLI è sperimentale. Il daemon usa il backend
PID e può aggiornarsi automaticamente: il 20/11 è passato da `0.170.0` a
`0.171.0` restando attivo. Nel crontab di `home` la riga marcata
`CODEX_REMOTE_CONTROL` avvia il comando dopo 30 secondi dal boot e ritenta
fino a cinque volte. `cron` era attivo e abilitato; l'esecuzione dopo un
riavvio non è stata ancora verificata. Per disattivare l'avvio al boot,
rimuovere solo quella riga dal crontab, lasciando intatte le altre.
Non esporre il socket o una porta app-server su Internet.

## Progetto Git e chat esistenti

Il repository è in `/home/home/home-server`, clonato dal remoto GitHub. La
cartella è salvata nell'app del PC di lavoro come progetto remoto `HOME-SERVER`
su `minipc`. La funzione Hand off richiede un progetto Git corrispondente su
entrambi gli host.

Il 20/11 Hand off delle chat `Gestisci mail via SSH` ed `ECM` da
`ZENBOOK-LUCA` a `minipc` ha restituito «Le chat paginate non possono ancora
essere continuate su un altro host». I passaggi si sono fermati durante la
preparazione, prima di copiare cronologia e stato Git: gli originali sono
rimasti sul ponte e non sono state create copie.
Non usare spostamenti manuali dei file interni di Codex come se fossero un
trasferimento supportato. Il limite è segnalato in
[openai/codex#40879](https://github.com/openai/codex/issues/40879).
Collegare direttamente l'app Codex del ponte al mini PC non supera questo
blocco sul formato della cronologia. Le altre chat non sono state provate e
potrebbero avere esiti diversi.

Per continuare il lavoro della posta sul mini PC serve una nuova chat nel
progetto remoto che legga `AGENTS.md`, `memoria/inventario.md` e
`memoria/procedure/mail-svuota.md`. La vecchia chat e la sua automazione di
pulizia ogni due ore restano sul PC ponte: prima di spegnerlo occorre decidere
come sostituire quella pianificazione, evitando due controlli paralleli.

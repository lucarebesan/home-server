# Gestione posta Gmail sul mini PC

Ultima verifica: 2026-11-17 (installazione del programma e timer in simulazione;
autenticazione Gmail ancora da configurare).

## Scopo e limiti

- Account unico: `ing.rebesan@gmail.com`, sola Posta in arrivo.
- La destinazione per eventuali spostamenti è l'etichetta `SVUOTA`.
  `ENEA` e `legale` sono protette. Non usare Cestino né eliminazione.
- `sorgenti/mail-svuota/` è la fonte del codice. Sul server è copiato in
  `/home/home/mail-svuota/`. Stato e log restano sotto
  `/home/home/.local/share/mail-svuota/`, fuori dal repository.
- Il timer ogni 30 minuti esegue **solo simulazione**. Senza credenziale
  esce senza connettersi. Nessun passaggio automatico a `--apply`.
- Le regole iniziali usano intestazioni, oggetto e indicatori di invio massivo.
  Sono un primo filtro, non riproducono il giudizio semantico delle vecchie
  automazioni. I messaggi incerti restano `review`.

## Credenziale

Google non accetta la normale password dell'account in questo client IMAP.
Per la via scelta serve la verifica in due passaggi e una password per le app,
generata dall'utente su
`https://myaccount.google.com/apppasswords`. Non inviare la password in chat,
non salvarla nel repository e non inserirla nella riga di comando.

L'utente la può inserire direttamente dal proprio terminale con:

```bash
ssh -t home@192.168.1.100 'install -d -m 700 ~/.config/mail-svuota; umask 077; read -rsp "Password per le app Gmail: " p; printf "\n"; printf "%s" "$p" > ~/.config/mail-svuota/app-password; unset p; chmod 600 ~/.config/mail-svuota/app-password'
```

Il programma verifica proprietario e permessi `600` prima di usarla. Una
password per le app può non essere disponibile con alcune impostazioni di
sicurezza dell'account; in quel caso progettare OAuth prima di proseguire.

## Verifica in simulazione

1. Test del codice: `cd ~/mail-svuota && python3 -m unittest -v test_mail_svuota`.
2. Dopo aver inserito la credenziale: `python3 ~/mail-svuota/mail_svuota.py`.
   Il comando stampa solo i conteggi. Le decisioni, con motivazione e
   mittente/oggetto, sono nel database locale protetto.
3. Estrarre un campione di `candidate`, `review` e `keep`; controllare
   esplicitamente PEC, sicurezza, ordini/ricevute, banca, fiscalità,
   assicurazioni, contratti, messaggi personali e operativi, corsi futuri,
   RENOLIT e la distinzione Pinterest automatico/personale.
4. Confrontare il numero dei messaggi in Posta in arrivo e le flag non lette
   prima/dopo la simulazione. La simulazione usa `BODY.PEEK` e selezione
   read-only; non deve cambiare nessuna etichetta o flag.
5. Prima di uno spostamento reale, verificare nell'account che `SVUOTA` sia
   visibile in IMAP e testare **un solo candidato approvato** con
   `--apply-uid UID`. Il programma richiede che lo stesso UID sia già stato
   classificato `candidate` nella simulazione e ricontrolla identità,
   etichette e flag.

## Attivazione e ripristino

Non attivare spostamenti automatici finché la simulazione non è stata
revisionata e l'automazione Codex precedente non è stata coordinata o spenta.
La pianificazione corrente usa solo `run-dry.sh`.

Per fermare la simulazione, rimuovere dalla crontab di `home` solo la riga
con `# MAIL_SVUOTA_DRY`; lasciare intatte le altre righe. Per revocare
l'accesso, rimuovere il file `~/.config/mail-svuota/app-password` sul server
e revocare la relativa password per le app dall'account Google. Lo stato
SQLite può essere conservato per audit; non contiene la credenziale.

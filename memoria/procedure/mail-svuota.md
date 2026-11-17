# Gestione posta Gmail sul mini PC

Ultima verifica: 2026-11-17 (accesso Gmail, scansione completa, timer in
simulazione, singolo spostamento con `UID MOVE` e modello locale verificati).

## Scopo e limiti

- Account unico: `ing.rebesan@gmail.com`, sola Posta in arrivo.
- La destinazione per eventuali spostamenti è l'etichetta `SVUOTA`.
  `ENEA` e `legale` sono protette. Non usare Cestino né eliminazione.
- `sorgenti/mail-svuota/` è la fonte del codice. Sul server è copiato in
  `/home/home/mail-svuota/`. Stato e log restano sotto
  `/home/home/.local/share/mail-svuota/`, fuori dal repository.
- Il timer ogni 30 minuti esegue **solo simulazione**. Senza credenziale
  esce senza connettersi. Nessun passaggio automatico a `--apply-uid`.
- Le regole iniziali usano intestazioni, oggetto e indicatori di invio massivo.
  Sono un primo filtro, non riproducono il giudizio semantico delle vecchie
  automazioni. I messaggi incerti restano `review`.
- `semantic_shadow.py` è una prova separata e manuale: invia al solo modello
  locale mittente, oggetto e fino a 1800 caratteri del corpo per UID scelti.
  Usa `BODY.PEEK` in modalità IMAP read-only, non passa gli allegati al modello, non sposta
  messaggi e conserva nel database locale solo esito e motivo, non il corpo.

## Credenziale

Google non accetta la normale password dell'account in questo client IMAP.
Per la via scelta serve la verifica in due passaggi e una password per le app,
generata dall'utente su
`https://myaccount.google.com/apppasswords`. Non inviare la password in chat,
non salvarla nel repository e non inserirla nella riga di comando.

L'utente la può inserire direttamente dal proprio terminale con:

```bash
ssh -t home@192.168.1.100 'bash ~/mail-svuota/set-password.sh'
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
   read-only; non deve cambiare nessuna etichetta o flag. Il collaudo iniziale
   è registrato nel diario di novembre.
5. Prima di uno spostamento reale, verificare nell'account che `SVUOTA` sia
   visibile in IMAP e testare **un solo candidato approvato** con
   `--apply-uid UID`. Il programma richiede che lo stesso UID sia già stato
   classificato `candidate` nella simulazione e ricontrolla identità,
   etichette e flag. Lo spostamento usa `UID MOVE`, supportato dal server
   Gmail: verificare con una nuova connessione che l'ID Gmail non sia più
   in `INBOX`, sia presente una sola volta in `SVUOTA` e conservi le flag.
   Ottenere l'ok esplicito dell'utente sul messaggio preciso prima di ogni
   prova reale.

## Attivazione e ripristino

Non attivare spostamenti automatici finché la simulazione non è stata
revisionata e l'automazione Codex precedente non è stata coordinata o spenta.
La pianificazione corrente usa solo `run-dry.sh`.

Per fermare la simulazione, rimuovere dalla crontab di `home` solo la riga
con `# MAIL_SVUOTA_DRY`; lasciare intatte le altre righe. Per revocare
l'accesso, rimuovere il file `~/.config/mail-svuota/app-password` sul server
e revocare la relativa password per le app dall'account Google. Lo stato
SQLite può essere conservato per audit; non contiene la credenziale.

## Modello locale (prova, non automazione)

Il 17/11 è stato avviato `mail-ollama` con
`sorgenti/mail-svuota/compose.ollama.yml` e scaricato `qwen3:4b-instruct`.
La porta 11434 è legata solo al loopback del mini PC; il container ha limiti
di 4 CPU e 5 GiB, un modello caricato e una richiesta alla volta. Non è
configurata una API OpenAI. Comandi di verifica:

```bash
ssh home@192.168.1.100 'docker ps --filter name=mail-ollama'
ssh home@192.168.1.100 'docker exec mail-ollama ollama list'
ssh home@192.168.1.100 'cd ~/mail-svuota && python3 semantic_shadow.py --uid UID'
```

Usare solo UID ancora in INBOX e già censiti dalla simulazione corrente.
L'ultimo comando legge il messaggio e stampa regola, risposta grezza del
modello e decisione effettiva: `keep` delle regole prevale sempre; se il
corpo non è disponibile, la decisione effettiva è `uncertain`. Il file
SQLite `~/.local/share/mail-svuota/state.sqlite3` contiene la tabella
`semantic_shadow` con esiti, senza testo delle email. Il modello non è nel
cron; soltanto `run-dry.sh` è pianificato.

Nel campione del 17/11 il modello ha riconosciuto offerte Beta Formazione,
Copernico, ECLISSE, Blumatica e Temu, consegna Amazon, avviso GitHub e una
conversazione tecnica. Ha però proposto erroneamente `SVUOTA` per due
notifiche Pinterest personali, con confidenza alta; con la prima versione
del prompt aveva sbagliato anche una consegna Amazon. Le regole ora
proteggono esplicitamente i due casi Pinterest, gli avvisi PEC e gli
aggiornamenti degli ordini Amazon osservati. **Non usare la confidenza del
modello per attivare spostamenti autonomi**. Prima servono un campione più
ampio revisionato, criteri conservativi, verifica delle flag e coordinamento
con l'automazione Codex precedente.

Per fermare solo il modello, senza toccare gli altri container:

```bash
ssh home@192.168.1.100 'cd ~/mail-svuota && docker compose -f compose.ollama.yml stop mail-ollama'
```

Questo arresto esplicito impedisce il riavvio automatico al boot finché non
si usa `docker compose -f compose.ollama.yml start mail-ollama`. Eseguirlo
solo con l'autorizzazione dell'utente richiesta dalle regole del server.

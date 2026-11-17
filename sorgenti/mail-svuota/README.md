# Mail SVUOTA

Programma Python standard library per valutare la sola Posta in arrivo di
`ing.rebesan@gmail.com` via IMAP TLS. Le regole sono in `rules.json`. Il
comando ordinario è una simulazione: registra le decisioni in
`~/.local/share/mail-svuota/state.sqlite3` e non modifica la casella.

`--apply-uid UID` è un'operazione separata che può spostare un solo messaggio
già classificato come `candidate`; prima di usarla servono prova reale,
revisione delle decisioni e coordinamento con l'automazione Codex
preesistente. Non usa Cestino, `\\Deleted` o `EXPUNGE`.

La credenziale non appartiene al repository. Procedura di installazione,
verifica e ripristino: `memoria/procedure/mail-svuota.md`.

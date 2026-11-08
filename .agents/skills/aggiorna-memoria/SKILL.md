---
name: aggiorna-memoria
description: Registra nel repository home-server cosa si è scoperto o fatto sul server (inventario, procedure, diario) con commit e push, senza segreti e senza doppioni. Usala alla fine di ogni intervento o scoperta utile.
---

# Aggiornare la memoria del server

## Dove va cosa

| Tipo di informazione | File |
|---|---|
| Stato e configurazione attuali (IP, container, servizi, dispositivi) | `memoria/inventario.md` |
| Come fare qualcosa in modo ripetibile (scopo, prerequisiti, passi, verifica, ripristino) | `memoria/procedure/<argomento>.md` |
| Cosa è successo e cosa si è deciso, con data | `memoria/diario/<anno-mese>.md` |
| Flussi di lavoro per gli agenti (quando e come intervenire) | `.agents/skills/<nome>/SKILL.md` |

Ogni fatto va scritto **in un solo posto**. Le skill rimandano alle procedure, non le
copiano. Prima di creare un file nuovo cerca se l'argomento esiste già
(`grep -ril <parola> memoria .agents`): aggiorna quello invece di aprirne un secondo.

## Regole

- Niente password, token o chiavi: al massimo indica dove si trovano.
- Tieni distinti fatti verificati (con data), ipotesi e questioni aperte.
- Aggiorna la riga "Ultima verifica" del file che modifichi.
- Il repository lo usano più sessioni in parallelo (anche dalla stessa cartella): prima
  di scrivere lancia `git fetch` e `git status`; nel commit includi solo i file che hai
  modificato tu (`git add <percorsi>`, non `git add -A`); poi `git pull --rebase` se serve
  e `git push`.
- Messaggio di commit in italiano: cosa e perché.

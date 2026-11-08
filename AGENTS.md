# Home server

Questo repository contiene la memoria operativa dell'home server. Prima di intervenire, consulta `memoria/inventario.md` e le eventuali procedure pertinenti in `memoria/procedure/`. Verifica sempre lo stato attuale del server e l'autorizzazione per l'operazione richiesta: la documentazione può essere superata.

Dopo un intervento riuscito, aggiorna le informazioni e le procedure utili a ripeterlo, distinguendo fatti verificati, ipotesi e questioni aperte. Non inserire password, token, chiavi private o altri segreti nel repository. Evita dati personali non necessari.

Quando modifichi questo repository, crea un commit delle modifiche relative al lavoro svolto e invialo al remoto con un push. Rispetta eventuali modifiche preesistenti dell'utente e segnala eventuali problemi di sincronizzazione o accesso.

## Come è organizzato

- `memoria/inventario.md`: com'è fatto il server oggi (rete, container, dispositivi, posizione dei segreti).
- `memoria/procedure/`: come fare le cose, passo per passo, con verifica e ripristino. È la fonte dei dettagli.
- `memoria/diario/`: cosa è successo e cosa si è deciso, per data, con le questioni aperte.
- `.agents/skills/`: flussi di lavoro per gli agenti. Dicono quando e come intervenire e rimandano alle procedure, senza copiarle.
- `sorgenti/`: codice di `ecm-engine` e della dashboard ECM v2. È la fonte di verità: si modifica e si fa il deploy da qui.

Ogni fatto sta in un solo posto: aggiorna quel file invece di crearne uno nuovo (vedi la skill `aggiorna-memoria`).

## Skill disponibili

| Skill | Quando |
|---|---|
| `check-server` | controllo generale in sola lettura, "è ripartito tutto?" |
| `luci-dingtian` | luci o relè Dingtian, ponte `dtbridge` |
| `rete-wifi` | crolli di rete, box Iliad, router EOLO, WiFi del server |
| `certificato-duckdns` | HA non raggiungibile da fuori, DuckDNS, certificato |
| `config-home-assistant` | modificare automazioni e configurazione di HA |
| `clima-ecm` | Nilan, Toshiba, ACS, ECM Engine, gateway Higeco |
| `aggiorna-memoria` | registrare un intervento o una scoperta |

## Regole sempre valide

- Accesso: `ssh hp` (utente `home`, IP `192.168.1.100`). `home` non ha sudo senza password: un comando privilegiato va consegnato all'utente come one-liner `ssh -t hp '…'`.
- Prima si osserva, poi si propone, e si agisce solo con l'ok dell'utente. Senza un ok esplicito niente riavvii di container o del server, niente modifiche a box, router o relè, niente luci accese o spente.
- Per spegnere il server non fermare i singoli container (`restart: unless-stopped` non li riavvierebbe al boot).
- Le automazioni spente a mano in HA (deploy GitHub, `00-NILAN WRITE`, `luci_*`) restano spente finché Luca non decide diversamente.
- Il disco è meccanico e lento: evita query pesanti sul database di HA e polling aggressivi.
- Più sessioni o agenti possono lavorare su questo repository: `git fetch` e `git status` prima di scrivere, `git add` dei soli file toccati.

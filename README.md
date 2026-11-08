# Home server: memoria operativa

Note, procedure e storico del server di casa (`hp-homeassistant`, Home Assistant e
servizi in Docker), pensati per essere usati da Codex o da un altro agente.

## Come usarlo con Codex

1. Apri Codex nella cartella del repository: legge da solo `AGENTS.md` (regole e mappa)
   e le skill in `.agents/skills/`.
2. Chiedi in linguaggio normale, per esempio "fai un check del server", "perché si sono
   spente le luci in sottotetto?", "è crollata la rete stanotte". Codex sceglie la skill
   adatta dalla descrizione.
3. Per richiamare una skill in modo esplicito: digita `$` e scegli dall'elenco (oppure
   `/skills`), per esempio `$check-server`.

Codex deve poter entrare nel server con `ssh hp` (alias in `~/.ssh/config` verso
`home@192.168.1.100`, con la tua chiave autorizzata sul server).

## Cosa c'è

- `memoria/inventario.md`: com'è fatto il server oggi.
- `memoria/procedure/`: procedure passo per passo (rete, relè Dingtian, DuckDNS e
  certificato, configurazione HA, ECM, gateway Higeco, dashboard, monitoraggio).
- `memoria/diario/`: cronologia degli interventi e questioni aperte.
- `.agents/skills/`: flussi di lavoro per l'agente (vedi la tabella in `AGENTS.md`).
- `sorgenti/`: codice dei servizi ECM, fonte di verità: `ecm-engine/` (motore di
  apprendimento, con la sua storia git) e `ha-ecm-v2/` (dashboard ECM v2).

## Regole principali

- Niente segreti nel repository: solo dove si trovano.
- L'agente osserva e propone, e interviene solo dopo il tuo ok.
- Dopo ogni intervento l'agente aggiorna la memoria, poi fa commit e push.

I sorgenti ECM si modificano solo in `sorgenti/`. Sul PC di Mattia `Misc/ecm-engine` e
`Misc/ha-ecm-v2` sono symlink a queste cartelle. Il ponte dei relè (`Misc/dtbridge/`) sta
ancora sul PC di Mattia, con una copia sul server in `~/dingtian/`.

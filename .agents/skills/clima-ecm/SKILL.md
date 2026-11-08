---
name: clima-ecm
description: Clima e logica ECM - Nilan CompactP, Toshiba, ACS, gateway Higeco 192.168.1.171, container ecm-engine (apprendimento e prove), dashboard ECM v2. Usala per domande o problemi su riscaldamento, raffrescamento, ricambio aria, acqua calda, stagione estate/inverno.
---

# Clima ed ECM

Riferimenti in `memoria/procedure/`:
- `ecm-engine.md`: motore di apprendimento, prove, entità `ecm_engine_*`;
- `gateway-higeco.md`: gateway Nilan/Toshiba/contatori, lettura a blocchi da HA, storico;
- `dashboard-ecm-v2.md`: dashboard `ecm-v2` e deploy via WebSocket;
- `config-home-assistant.md`: come modificare automazioni e package ECM.

Contesto recente in `memoria/diario/2026-11-03_08-interventi.md`, sezione clima.

## Regole

- **`00-NILAN WRITE` è spenta da un utente** (dal 7/11): senza WRITE nessun comando
  arriva alle macchine. Non riaccenderla senza l'ok esplicito di Luca.
- Il gateway Higeco si usa in sola lettura con l'utente predefinito. Le credenziali admin
  le inserisce a mano l'utente nella pagina: mai in chat, nei file o negli script.
- Le prove di `ecm-engine` cambiano davvero il clima: "Prove automatiche" è spento di
  default. Non accenderlo e non avviare prove senza ok.
- Per la numerazione delle combinazioni fa fede HA, non il sito ECM.
- I sorgenti di `ecm-engine` e della dashboard stanno in questo repository
  (`sorgenti/ecm-engine/`, `sorgenti/ha-ecm-v2/`) e sono la fonte di verità. Ogni
  modifica va committata qui; il deploy parte da queste cartelle (vedi le procedure).
  Sul server `~/ecm-engine` è solo la copia distribuita da `deploy.sh`.

## Diagnosi tipica

1. Stagione attuale e motivo: automazione `00-NILAN Cambio Stagione Automatico T10`
   (soglia `commutazione_estate_inverno`).
2. Stato delle automazioni ECM (on/off, ultimo trigger) ed errori nel log di HA.
3. Valori letti dal gateway (sensori Nilan/Toshiba in HA; se sono `unavailable`,
   controlla il gateway con `ping 192.168.1.171`).
4. Proposte e misure del motore nella tab "Apprendimento".

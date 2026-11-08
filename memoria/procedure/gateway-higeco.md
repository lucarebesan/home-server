# Gateway Higeco (Nilan, Toshiba, contatori)

Ultima verifica: 2026-11-08. Documentazione completa del protocollo, catalogo delle 228 grandezze e mappature: `Misc/ecm-engine/docs/gateway/` sul PC di Mattia (`acts.md`, `catalogo_grandezze.csv`, `import_mapping.md`).

## Cos'è

- Higeco GWCV4-M1-2ETH, `http://192.168.1.171`, firmware core 25.12.1, impianto "Rebesan-Foletto", collegato al cloud `exrg-data.it`.
- Dispositivi Modbus: Compact P (driver Nilan CTS602, 89 grandezze), Split Toshiba (IntesisBox, 21), modulo I/O iSMA (temperatura EGWK, 21), contatori di energia SDM120 di Compact e Split (9 ciascuno), sanificatore Jonix (20), ingressi della scheda (3).
- HA legge e scrive attraverso `/config/scripts/nilan_sensor.sh` e `nilan_write.sh`, con l'utente di sola lettura predefinito.

## Utenti

- Pannello di controllo → Utenti (cliccare l'icona, non l'etichetta). Gli utenti esistenti sono `admin` (Amministratore) e `user` (Ruolo 15). Ci sono 15 ruoli con permessi a matrice (sistema, interfaccia, periferiche, plugin). Nessun utente è stato aggiunto.
- Le credenziali admin le conosce Mattia: si inseriscono a mano nella pagina, mai in chat, script o repository.
- Con `user` si leggono circa 49 grandezze tramite i plugin proxy (`pluginManager.cgi` `sendCmd`/`sendCommand`, `getShm`). Storico (`dataLogCgi getDataLog`) e lettura diretta (`acqModCgi getShmData`) richiedono admin.

## Lettura

- Login: `GET /cgi-bin/userCgi?p=user&u=<utente>&query=[{"act":"getStatus"}]` → cookie `gwc=<k>`. Le risposte sono compresse: usare `curl --compressed`.
- Più letture in una richiesta: più oggetti `sendCommand` nello stesso array `query`. Il gateway le esegue comunque una alla volta (0,2–0,5 s ciascuna; tutte le 60 di HA in 14–29 s).
- `getShm {"idPlugin":1999690}` restituisce in 0,4 s i valori del modulo APP, compresa l'**umidità vera** (il sensore HA su 1999108 Id15 legge un registro non mappato).
- **Solo comandi di lettura**: mai comandi `W*`, né set/save/reset/reboot.

## Storico (datalogger)

- Inizia il 2026-07-04 06:03. Compact P, Split e modulo I/O ogni 60 s; contatori ogni 600 s.
- Richiesta: `POST /cgi-bin/dataLogCgi` con `query=[{"act":"getDataLog","sn":"UG7G8G3CUG7G","DATI":{"idLog":<id dispositivo>,"start":s,"stop":s,"maxNumRecord":100000,"period":60,"zeroTimeOffset":0,"items":[<id grandezze>]}}]`.
- Una settimana di Compact P (28 colonne registrate) richiede circa 17 s e pesa 2,2 MB. Fare una richiesta alla volta, con pause di qualche secondo: HA usa lo stesso gateway.
- **Il campo `utc` non è UTC**: è l'ora locale scritta come epoch (+2 h in estate, +1 h in inverno). Il 25/10 il gateway ha cambiato ora alle 07:52, non alle 03:00.
- Export eseguito l'8/11 dalla sessione admin nel browser; file in `Misc/ecm-engine/data_gw/` (circa 92 MB, fuori da git).

## Osservazioni

- Allarme Nilan attivo il 15–17/07 e dal 15/10 al 27/10 (dal datalogger); lo stato di controllo non è mai passato ad ALLARME.
- Buco di 1,6 h il 18/08 su tutti i dispositivi; circa il 3% di letture mancanti sui contatori.

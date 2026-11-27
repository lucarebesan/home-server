# Dashboard Chiusure e Chiusure2

Ultima verifica: 2026-11-27 13:59–14:00 (Chiusure2 salvata e riletta identica).

## Viste e sorgenti

La Overview storage predefinita (`lovelace`) contiene la vista originale
`/lovelace/chiusure` e, subito dopo, `/lovelace/chiusure2`, aggiunta su richiesta
di Luca per confrontare una nuova grafica mantenendo dati e comandi.

Il sorgente della nuova vista è `/config/dashboards/chiusure2.json`, versionato
nel repository HA nel commit `ed193c9`. È una copia per manutenzione: il file
non viene caricato automaticamente dalla Overview, che resta in modalità
storage. Le modifiche vanno salvate via WebSocket e allineate a quel file.

`sorgenti/ha-chiusure/build.js` in questo repository costruisce Chiusure2 da
un export aggiornato della sola vista originale. Usa solamente componenti già
presenti: card native e `custom:button-card`. `deploy.py` aggiunge la vista con
backup e confronto di tutte le viste preesistenti; rifiuta una Chiusure2 già
presente e un originale cambiato nel frattempo. Non usarlo per sovrascrivere
una versione successivamente modificata dall'utente.

## Contenuti e verifiche

- Comandi generali in alto: meteo, stato e toggle automazioni, Giardino,
  Sezionale, Primo risveglio, Tutti svegli e comandi dei due gruppi.
- Quattro schede frangisole e sei avvolgibili, con la stessa riga cover nativa
  per posizione/controlli e gli stessi servizi per inclinazioni e preset.
  I doppi impulsi sono indicati come Su ×2 e Giù ×2.
- Esposizione al sole in ciascuna scheda secondo gli stessi intervalli azimut
  dell'originale. Riepiloghi Piano terra/Sottotetto e azimut conservati.
- Tabella orari con gli stessi calcoli, fase, data/ora, alba, apertura,
  fine giornaliero, inizio serale, crepuscolo, fine serale e chiusura ordinaria.

La build verifica la conservazione delle **51 azioni esplicite** originali,
delle dieci righe cover con posizione e la sintassi dei 13 template JavaScript.
Il deploy ha renderizzato tramite HA tutti e tre i template markdown, ricevuto
successo da `lovelace/config/save` e riletto una configurazione identica.
La vista originale e tutte le altre sono risultate integralmente invariate.
Nessun reload, riavvio o comando alle chiusure/automazioni durante il collaudo;
nessun nuovo errore pertinente nei log controllati. La verifica visiva da
telefono/PC e dei tocchi reali resta all'utente; i comandi della nuova vista
sono operativi e agiscono sulle stesse entità dell'originale.

## Ricostruzione e salvataggio

1. Leggere la configurazione corrente con WebSocket `lovelace/config`
   senza `url_path` e ricavare la sola vista `path=chiusure`. Il token si legge
   solo sul server da `~/.config/ecm/ha_token`, senza stamparlo o copiarlo.
2. Eseguire `node sorgenti/ha-chiusure/build.js originale.json chiusure2.json`.
   Se il layout originale è cambiato, adattare prima il builder: gli assert
   e il confronto azioni servono a prevenire perdite silenziose.
3. Per la prima installazione eseguire `deploy.py` dentro il container HA,
   passando i due JSON come argomenti e il token via stdin JSON. Per aggiornare
   una vista già presente partire dal live e sostituire soltanto Chiusure2,
   preservando le modifiche dell'utente e tutte le altre viste.
4. Rileggere la configurazione, confrontare integralmente le viste, committare
   e inviare soltanto `dashboards/chiusure2.json` dal repository HA.

## Ripristino

Backup completo immediatamente precedente:
`/config/tmp/backup_lovelace_chiusure2_20261127-135921.json`.
Per rimuovere la prova leggere il live, eliminare soltanto la vista
`path=chiusure2`, salvarlo via WebSocket e verificare le altre viste. Non
ripristinare indiscriminatamente il backup completo se nel frattempo altre
viste sono cambiate. La copia JSON nel repository HA va mantenuta coerente
con la decisione finale di conservare o rimuovere la vista.

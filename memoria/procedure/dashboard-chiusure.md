# Dashboard Chiusure e Chiusure2

Ultima verifica: 2026-11-27 15:30 (Chiusure2 compatta, due colonne, riletta identica).

## Viste e sorgenti

La Overview storage predefinita (`lovelace`) contiene la vista originale
`/lovelace/chiusure` e, subito dopo, `/lovelace/chiusure2`, aggiunta su richiesta
di Luca per confrontare una nuova grafica mantenendo dati e comandi.

Il sorgente della nuova vista è `/config/dashboards/chiusure2.json`, versionato
nel repository HA, versione compatta nel commit `d233b52`. È una copia per manutenzione: il file
non viene caricato automaticamente dalla Overview, che resta in modalità
storage. Le modifiche vanno salvate via WebSocket e allineate a quel file.

`sorgenti/ha-chiusure/build.js` in questo repository costruisce Chiusure2 da
un export aggiornato della sola vista originale. Usa solamente componenti già
presenti: card native, `custom:button-card` e card-mod (risorsa verificata).
`deploy.py` aggiunge la vista con backup e confronto di tutte le viste
preesistenti. Per aggiornare accetta `--replace precedente-chiusure2.json`:
verifica che il live coincida con quel precedente e che l'originale non sia
cambiato. Non sovrascrivere modifiche dell'utente senza prima riconciliarle.

## Preferenza grafica di Luca

La prima proposta a tre colonne e con schede grandi è stata rifiutata.
Luca richiede **massima compattezza e rapidità**, due colonne come la vista
originale, pulsanti piccoli subito accessibili e nessun banner o titolo grande.
Non aumentare colonne o ingombri per un restyling. La versione corrente ha
esattamente due sezioni da una colonna, pulsanti alti 34–42 px e nessuna grande
card per gli orari; testi e righe native hanno padding ridotto.

## Contenuti e verifiche

- A sinistra: meteo/toggle automazioni, Giardino, Sezionale, Risveglio,
  Tutti svegli, gruppo frangisole, quattro chiusure e orari compatti.
  A destra: gruppo avvolgibili, sei chiusure e riepiloghi sole/posizioni.
- Quattro righe frangisole e sei avvolgibili, con la stessa riga cover nativa
  per posizione/controlli e gli stessi servizi per inclinazioni e preset.
  I doppi impulsi sono indicati come Su ×2 e Giù ×2.
- Esposizione al sole nei riepiloghi Piano terra/Sottotetto secondo gli stessi
  intervalli azimut dell'originale. Posizioni e azimut conservati.
- Orari in poche righe, senza tabella: stessi calcoli, fase, data/ora, alba, apertura,
  fine giornaliero, inizio serale, crepuscolo, fine serale e chiusura ordinaria.

La build verifica la conservazione delle **51 azioni esplicite** originali,
delle dieci righe cover con posizione e la sintassi dei due template JavaScript.
Il deploy compatto ha renderizzato tramite HA tutti e cinque i template markdown, ricevuto
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
3. Eseguire `deploy.py` dentro il container HA, passando i due JSON come
   argomenti e il token via stdin JSON. Per aggiornare aggiungere
   `--replace precedente-chiusure2.json`, esportato dal live appena letto.
4. Rileggere la configurazione, confrontare integralmente le viste, committare
   e inviare soltanto `dashboards/chiusure2.json` dal repository HA.

## Ripristino

Backup completo immediatamente precedente:
`/config/tmp/backup_lovelace_chiusure2_20261127-153021.json` (prima del compattamento).
Il backup della prima installazione è
`/config/tmp/backup_lovelace_chiusure2_20261127-135921.json`.
Per rimuovere la prova leggere il live, eliminare soltanto la vista
`path=chiusure2`, salvarlo via WebSocket e verificare le altre viste. Non
ripristinare indiscriminatamente il backup completo se nel frattempo altre
viste sono cambiate. La copia JSON nel repository HA va mantenuta coerente
con la decisione finale di conservare o rimuovere la vista.

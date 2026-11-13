# Costi e consumi elettrici

Ultima verifica: 2026-11-13 (cinque fatture e comunicazione di rinnovo esaminate; sorgenti locali, nessun deploy).

## Fonti e dati

- `sorgenti/ecm-engine/billing_invoices.json` contiene solo periodi, kWh F1/F23 e voci economiche aggregate delle cinque bollette dicembre 2025–settembre 2026. Niente PDF, POD, nome, indirizzo o estremi di pagamento nel repository.
- `sorgenti/ecm-engine/ecm_engine/billing.py` riconcilia i cinque totali con imponibile, IVA e canone; stima una finestra tariffaria da **kWh prelevati dalla rete** distinti per fascia. Non usare `sensor.consumo_casa_mese`, che include consumi coperti da FV e batteria, né `sensor.costo_energia_mese` (moltiplicatore indicativo 0,35 €/kWh).
- Il prezzo bloccato attuale vale fino al 30/11/2026. La comunicazione del fornitore indica dal 01/12/2026 al 30/11/2027 una proposta di rinnovo con F1 0,1333 €/kWh e F23 0,1281 €/kWh **al netto delle perdite** (0,14663 e 0,14091 con perdite 10%); quota commerciale invariata a 144 €/anno. Sconto domiciliazione del 5% sul corrispettivo energia. Se il cliente non cambia offerta, la comunicazione indica applicazione automatica dal 01/12. Verificare sulla prima bolletta successiva quale offerta sia stata effettivamente applicata.
- Dispacciamento, rete/oneri, potenza e accise nel modello sono i valori **osservati ad agosto–settembre 2026**, non prezzi fissi garantiti dal contratto. Canone TV e sconti straordinari si inseriscono separatamente. Un cambio di fornitore rende non applicabile lo scenario di rinnovo.

## Aggiornamento a ogni bolletta

1. Estrarre periodo di competenza, kWh fatturati F1 e F23, letture effettive o stimate, quote consumi/fissa/potenza, accise, IVA, canone e conguagli/sconti. Aggiornare una riga o aggiungerla a `billing_invoices.json` senza identificativi. Verificare con `reconcile_invoice` che il totale coincida al centesimo.
2. Confrontare i kWh prelevati dell'inverter/HA con quelli del distributore sulla fattura; ricostruire eventuali giorni mancanti. Solo dopo collegare il conteggio live alla dashboard e distinguere importo maturato alla data e previsione di fine periodo. Per la fascia F1/F23 servono contatori distinti o una ricostruzione oraria verificata. In assenza di copertura sufficiente mostrare “stima non disponibile”.
3. Ricalibrare le voci regolate e misurare l'errore previsione/fattura. Se cambia contratto, aggiungere una tariffa con date di validità; non applicare vecchi prezzi a una finestra che attraversa la scadenza.

## Stato

La vista `Costi e consumi` è **solo nel sorgente locale** della dashboard. Mostra bollette verificate e condizioni/scenario; la previsione resta esplicitamente non disponibile finché il prelievo di rete non è riconciliato. Il server non era raggiungibile dalla postazione durante il lavoro del 13/11: stato live, sensore e deploy non verificati. Nessuna automazione o container è stato modificato.

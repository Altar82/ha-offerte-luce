# Offerte Luce

[![Download](https://img.shields.io/github/downloads/Altar82/ha-offerte-luce/total?label=download)](https://github.com/Altar82/ha-offerte-luce/releases) [![Installazioni attive](https://img.shields.io/badge/dynamic/json?label=installazioni%20attive&query=%24.offerte_luce.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&color=41BDF5)](https://analytics.home-assistant.io/custom_integrations)

Integrazione per Home Assistant che confronta **tutte le offerte luce e gas del mercato libero** pubblicate ogni giorno sul [Portale Offerte di ARERA](https://www.ilportaleofferte.it) con **i tuoi consumi reali**, presi dalle statistiche della dashboard Energia o dalla bolletta.

Ti dice qual è l'offerta più conveniente per te, quanto spenderesti in un anno e quanto risparmieresti rispetto a quella che hai adesso. Quando il risparmio supera una soglia scelta da te, ti avvisa con una notifica in Home Assistant.

Luce e gas si aggiungono separatamente: **Aggiungi integrazione → Offerte Luce** e scegli *Offerte luce* o *Offerte gas*.

## Cosa fa

- Scarica ogni giorno l'elenco ufficiale delle offerte (Open Data ARERA, circa 3.500 offerte luce).
- Ricava dai dati orari dell'ultimo anno quanto consumi in **F1, F2 e F3**, tenendo conto di sabati, domeniche e festività.
- Scarta le offerte che non puoi sottoscrivere: tipo di cliente, residenza, zona, limiti di consumo e potenza, offerte scadute o solo luce+gas.
- Per ogni offerta calcola la spesa annua: quota fissa, prezzo dell'energia per fascia, dispacciamento del venditore e sconti. Per le offerte variabili usa il PUN che indichi tu.
- Mette in classifica le 10 offerte migliori.
- **Gas**: stesso confronto sulle offerte gas (circa 2.000), con prezzo in €/Smc, offerte variabili legate al PSV e scaglioni di consumo.

## Entità

| Entità | Descrizione |
|---|---|
| `sensor.offerte_luce_migliore_offerta` | Nome dell'offerta più conveniente. Negli attributi trovi venditore, link, dettaglio dei costi, sconti e la classifica delle prime 10 |
| `sensor.offerte_luce_costo_migliore_offerta` | Spesa annua stimata con l'offerta migliore (€/anno) |
| `sensor.offerte_luce_costo_offerta_attuale` | Spesa annua stimata con la tua offerta attuale |
| `sensor.offerte_luce_risparmio_annuo` | Differenza tra le due |
| `sensor.offerte_luce_consumo_annuo` | Consumo annuo, con F1/F2/F3 negli attributi |
| `binary_sensor.offerte_luce_conviene_cambiare` | Acceso se il risparmio supera la soglia |
| `sensor.offerte_luce_offerte_confrontate` | Diagnostica: offerte confrontate e motivi di esclusione |

Per il gas le entità hanno lo stesso nome con il prefisso `offerte_gas_` (es. `sensor.offerte_gas_migliore_offerta`) e il consumo è in Smc.

Quando compare una nuova offerta migliore oltre la soglia:
- arriva una **notifica in Home Assistant** con offerta, risparmio e link (si può disattivare da *Configura*);
- viene generato l'evento `offerte_luce_conviene_cambiare` (con `fornitura`: `luce` o `gas`), utile per mandarla anche sul telefono.

### Esempio di notifica

```yaml
automation:
  - alias: Avviso offerta più conveniente
    triggers:
      - trigger: event
        event_type: offerte_luce_conviene_cambiare
    actions:
      - action: notify.notify
        data:
          title: "Offerta {{ trigger.event.data.fornitura }} più conveniente"
          message: >
            {{ trigger.event.data.offerta }} ({{ trigger.event.data.venditore }}):
            risparmieresti circa {{ trigger.event.data.risparmio_annuo | round(0) }} € all'anno (IVA esclusa).
            {{ trigger.event.data.url }}
```

## Installazione

### Dal Marketplace (consigliata)

1. In Home Assistant apri **Marketplace** e cerca **Offerte Luce**.
2. Installala e riavvia Home Assistant.
3. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Offerte Luce**.

### Come repository personalizzato

Se non la trovi nella ricerca, nel Marketplace apri il menu ⋮ → **Repository personalizzati**, aggiungi `https://github.com/Altar82/ha-offerte-luce` come **Integrazione** e poi segui i passi qui sopra.

Per la luce serve un sensore di energia prelevata dalla rete (kWh, `total_increasing`) con almeno 2 settimane di statistiche, oppure il consumo annuo della bolletta. Per il gas basta il consumo annuo della bolletta (il sensore è facoltativo). Se la dashboard Energia è configurata, il sensore viene proposto in automatico.

## Configurazione

**Fornitura**: sensore dei consumi, tipo di fornitura (residente, non residente, altri usi), potenza impegnata, regione ed eventualmente codice ISTAT del comune.

**Offerta attuale**: prezzo fisso, oppure spread se hai un'offerta variabile, e quota fissa annua. Prendi i valori dalla voce *spesa per la materia energia* della bolletta, IVA esclusa. In alternativa puoi indicare il codice offerta del Portale Offerte.

**PUN, sconti e avvisi** (da *Configura*):
- PUN previsto per fascia, oppure un sensore che lo fornisce in €/kWh o €/MWh;
- se accetti bolletta online e domiciliazione, per contare i relativi sconti;
- soglia di risparmio, notifica in Home Assistant e frequenza di aggiornamento.

### Gas

**Fornitura**: il **consumo annuo in Smc** che trovi in bolletta (consigliato) oppure il sensore del gas della dashboard Energia, tipo di fornitura e zona. Il gas si consuma soprattutto d'inverno: con meno di un anno di dati del sensore la stima annua è poco affidabile, per questo il consumo della bolletta ha la precedenza.

**Offerta attuale**: prezzo in €/Smc (o spread sul PSV) e quota fissa dalla voce *spesa per la materia gas naturale*, oppure il codice offerta.

**PSV, sconti e avvisi**: il PSV previsto in €/Smc (o un sensore in €/Smc o €/MWh) per stimare le offerte variabili, più le stesse opzioni della luce.

## Cosa include la stima (e cosa no)

La stima comprende **solo le voci che cambiano da un venditore all'altro**: prezzo dell'energia, quota fissa, corrispettivi del venditore, una tantum e sconti. Il risultato è **IVA esclusa**, mentre negli attributi trovi anche il valore con IVA.

Trasporto, oneri di sistema e accise (e per il gas le componenti regolate come QVD) sono uguali per tutti i venditori e non sono inclusi. Per questo la cifra è più bassa della bolletta, ma il **confronto** tra offerte resta corretto.

Limiti da conoscere:
- per le offerte variabili il risultato dipende dal PUN (o PSV) che imposti;
- per il gas l'IVA indicata negli attributi è al 10% fino a 480 Smc l'anno e al 22% oltre (usi domestici);
- gli sconti limitati nel tempo vengono contati solo per i mesi in cui valgono;
- gli sconti con condizioni particolari (es. "porta un amico") non vengono contati, ma sono elencati negli attributi;
- alcune offerte hanno dati incoerenti nell'elenco ufficiale: quelle palesemente sbagliate vengono scartate, quelle corrette con un'ipotesi sono segnate come `stima_approssimata`.

Prima di cambiare fornitore **verifica sempre le condizioni sul sito del venditore** o sul Portale Offerte.

## Fonte dei dati

Dati: *Portale Offerte, ARERA / Acquirente Unico*, Open Data con licenza [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.it).

Questa integrazione non è affiliata ad ARERA, ad Acquirente Unico né ad alcun venditore.

## Licenza

MIT

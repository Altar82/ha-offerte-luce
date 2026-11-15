# Offerte Luce

Integrazione per Home Assistant che confronta **tutte le offerte luce del mercato libero** pubblicate ogni giorno sul [Portale Offerte di ARERA](https://www.ilportaleofferte.it) con **i tuoi consumi reali**, presi dalle statistiche della dashboard Energia.

Ti dice qual è l'offerta più conveniente per te, quanto spenderesti in un anno e quanto risparmieresti rispetto a quella che hai adesso. Quando il risparmio supera una soglia scelta da te, può avvisarti.

## Cosa fa

- Scarica ogni giorno l'elenco ufficiale delle offerte (Open Data ARERA, circa 3.500 offerte luce).
- Ricava dai dati orari dell'ultimo anno quanto consumi in **F1, F2 e F3**, tenendo conto di sabati, domeniche e festività.
- Scarta le offerte che non puoi sottoscrivere: tipo di cliente, residenza, zona, limiti di consumo e potenza, offerte scadute o solo luce+gas.
- Per ogni offerta calcola la spesa annua: quota fissa, prezzo dell'energia per fascia, dispacciamento del venditore e sconti. Per le offerte variabili usa il PUN che indichi tu.
- Mette in classifica le 10 offerte migliori.

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

Quando compare una nuova offerta migliore oltre la soglia, viene generato l'evento `offerte_luce_conviene_cambiare`.

### Esempio di notifica

```yaml
automation:
  - alias: Avviso offerta luce più conveniente
    triggers:
      - trigger: event
        event_type: offerte_luce_conviene_cambiare
    actions:
      - action: notify.notify
        data:
          title: "Offerta luce più conveniente"
          message: >
            {{ trigger.event.data.offerta }} ({{ trigger.event.data.venditore }}):
            risparmieresti circa {{ trigger.event.data.risparmio_annuo | round(0) }} € all'anno (IVA esclusa).
            {{ trigger.event.data.url }}
```

## Installazione

1. Nel Marketplace (HACS) apri il menu ⋮ → **Repository personalizzati** e aggiungi `https://github.com/Altar82/ha-offerte-luce` come **Integrazione**.
2. Installa **Offerte Luce** e riavvia Home Assistant.
3. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Offerte Luce**.

Serve un sensore di energia prelevata dalla rete (kWh, `total_increasing`) con almeno 2 settimane di statistiche. Se la dashboard Energia è configurata, viene proposto in automatico.

## Configurazione

**Fornitura**: sensore dei consumi, tipo di fornitura (residente, non residente, altri usi), potenza impegnata, regione ed eventualmente codice ISTAT del comune.

**Offerta attuale**: prezzo fisso, oppure spread se hai un'offerta variabile, e quota fissa annua. Prendi i valori dalla voce *spesa per la materia energia* della bolletta, IVA esclusa. In alternativa puoi indicare il codice offerta del Portale Offerte.

**PUN, sconti e avvisi** (da *Configura*):
- PUN previsto per fascia, oppure un sensore che lo fornisce in €/kWh o €/MWh;
- se accetti bolletta online e domiciliazione, per contare i relativi sconti;
- soglia di risparmio per l'avviso e frequenza di aggiornamento.

## Cosa include la stima (e cosa no)

La stima comprende **solo le voci che cambiano da un venditore all'altro**: prezzo dell'energia, quota fissa, corrispettivi del venditore, una tantum e sconti. Il risultato è **IVA esclusa**, mentre negli attributi trovi anche il valore con IVA.

Trasporto, oneri di sistema e accise sono uguali per tutti i venditori e non sono inclusi. Per questo la cifra è più bassa della bolletta, ma il **confronto** tra offerte resta corretto.

Limiti da conoscere:
- per le offerte variabili il risultato dipende dal PUN che imposti;
- gli sconti limitati nel tempo vengono contati solo per i mesi in cui valgono;
- gli sconti con condizioni particolari (es. "porta un amico") non vengono contati, ma sono elencati negli attributi;
- alcune offerte hanno dati incoerenti nell'elenco ufficiale: quelle palesemente sbagliate vengono scartate, quelle corrette con un'ipotesi sono segnate come `stima_approssimata`.

Prima di cambiare fornitore **verifica sempre le condizioni sul sito del venditore** o sul Portale Offerte.

## Fonte dei dati

Dati: *Portale Offerte, ARERA / Acquirente Unico*, Open Data con licenza [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.it).

Questa integrazione non è affiliata ad ARERA, ad Acquirente Unico né ad alcun venditore.

## Licenza

MIT

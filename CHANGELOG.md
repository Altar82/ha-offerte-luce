# Changelog

## 0.2.0

### Novità
- **Offerte gas**: oltre alla luce si possono confrontare le offerte gas del mercato libero. Si aggiungono come
  seconda voce (*Aggiungi integrazione → Offerte Luce → Offerte gas*) e hanno sensori propri: migliore offerta,
  costi, risparmio, consumo annuo in Smc e *Conviene cambiare*. Gestisce prezzo fisso, offerte variabili legate
  al PSV e scaglioni di consumo.
- **Consumo annuo dalla bolletta**: per il gas è il modo consigliato; per la luce è un'alternativa al sensore
  (se ci sono entrambi, dal sensore si prende solo la ripartizione F1/F2/F3).
- **Notifica quando conviene cambiare**: oltre all'evento, compare una notifica in Home Assistant con offerta,
  risparmio annuo e link. Si disattiva da *Configura → PUN, sconti e avvisi*.
- L'evento `offerte_luce_conviene_cambiare` indica anche la `fornitura` (`luce` o `gas`).

### Correzioni
- Svuotando un campo facoltativo nelle opzioni (es. il codice ISTAT) il valore iniziale non torna più fuori.

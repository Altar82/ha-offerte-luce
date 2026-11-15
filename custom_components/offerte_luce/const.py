"""Costanti di Offerte Luce."""

DOMAIN = "offerte_luce"

CONF_STAT = "statistica_energia"
CONF_TIPO_CLIENTE = "tipo_cliente"
CONF_POTENZA = "potenza_kw"
CONF_REGIONE = "regione"
CONF_COMUNE = "comune_istat"

CONF_ATTUALE = "offerta_attuale"
CONF_CODICE = "codice_offerta"
CONF_PREZZO = "prezzo_kwh"
CONF_QUOTA = "quota_fissa_anno"

CONF_PUN_ENTITA = "pun_entita"
CONF_PUN_F1 = "pun_f1"
CONF_PUN_F2 = "pun_f2"
CONF_PUN_F3 = "pun_f3"
CONF_ONLINE = "bolletta_online"
CONF_SDD = "domiciliazione"
CONF_DUAL = "includi_dual"
CONF_SOGLIA = "soglia_risparmio"
CONF_ORE = "aggiornamento_ore"

CLIENTE_RESIDENTE = "domestico_residente"
CLIENTE_NON_RESIDENTE = "domestico_non_residente"
CLIENTE_ALTRI_USI = "altri_usi"

ATTUALE_CODICE = "codice"
ATTUALE_FISSO = "fisso"
ATTUALE_VARIABILE = "variabile"
ATTUALE_NESSUNA = "nessuna"

DEFAULT_PUN = 0.22  # €/kWh, autunno 2026: va aggiornato o collegato a un sensore
DEFAULT_SOGLIA = 50.0
DEFAULT_ORE = 12
IVA_DOMESTICO = 0.10
IVA_ALTRI_USI = 0.22
TOP = 10

EVENTO = f"{DOMAIN}_conviene_cambiare"

# codici ISTAT delle regioni
REGIONI = {
    "01": "Piemonte",
    "02": "Valle d'Aosta",
    "03": "Lombardia",
    "04": "Trentino-Alto Adige",
    "05": "Veneto",
    "06": "Friuli-Venezia Giulia",
    "07": "Liguria",
    "08": "Emilia-Romagna",
    "09": "Toscana",
    "10": "Umbria",
    "11": "Marche",
    "12": "Lazio",
    "13": "Abruzzo",
    "14": "Molise",
    "15": "Campania",
    "16": "Puglia",
    "17": "Basilicata",
    "18": "Calabria",
    "19": "Sicilia",
    "20": "Sardegna",
}

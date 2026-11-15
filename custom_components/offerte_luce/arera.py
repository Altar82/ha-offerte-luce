"""Lettura degli Open Data del Portale Offerte ARERA (luce, mercato libero) e calcolo della spesa.

Modulo puro (solo libreria standard): niente Home Assistant, testabile da riga di comando.

Fonte: file XML giornaliero pubblicato da Acquirente Unico per conto di ARERA,
licenza CC-BY 4.0. I codici dei campi sono stati ricavati dai dati reali:
dove il significato non è certo, il calcolo resta prudente e l'offerta viene segnalata.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

NS = "{http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01}"
URL_TEMPLATE = (
    "https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv/offerteML/"
    "{y:04d}_{m:02d}/PO_Offerte_E_MLIBERO_{y:04d}{m:02d}{d:02d}.xml"
)
FONTE = "Portale Offerte ARERA / Acquirente Unico - Open Data CC-BY 4.0"

# --- codici (dedotti dai dati) -------------------------------------------------
CLIENTE_DOMESTICO = "01"
CLIENTE_ALTRI_USI = "02"
OFFERTA_FISSA = "01"
OFFERTA_VARIABILE = "02"
FASCE_MONO = "01"
FASCE_F123 = "03"
FASCE_BIORARIA = "07"
FASCE_PERSONALIZZATE = "91"
UNITA_EURO_ANNO = "01"
UNITA_EURO_KW = "02"
UNITA_EURO_KWH = "03"
UNITA_EURO_UNA_TANTUM = "05"
UNITA_PERCENTUALE = "06"
# indici di prezzo trattati come PUN (gli altri non sono stimabili)
IDX_PUN = {"01", "08", "12"}
# condizioni di applicazione degli sconti
SCONTO_SEMPRE = "00"
SCONTO_BOLLETTA_ONLINE = "01"
SCONTO_DOMICILIAZIONE = "03"

FASCE = ("F1", "F2", "F3")
MAX_EURO_KWH = 1.5  # oltre si assume un errore di unità (€/MWh)


def url_for(day: date) -> str:
    return URL_TEMPLATE.format(y=day.year, m=day.month, d=day.day)


def _t(el: ET.Element, path: str) -> str | None:
    x = el.find("/".join(NS + p for p in path.split("/")))
    if x is None or x.text is None:
        return None
    v = x.text.strip()
    return v or None


def _all(el: ET.Element, path: str) -> list[str]:
    return [x.text.strip() for x in el.findall("/".join(NS + p for p in path.split("/"))) if x.text and x.text.strip()]


def _f(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _durata(v: str | None) -> int | None:
    n = _f(v)
    return int(n) if n and n > 0 else None


_PAROLE_ONLINE = ("bolletta", "web", "mail", "digital", "elettronic", "online", "on line", "app")
_PAROLE_SDD = ("domicilia", "sdd", "rid", "addebito", "sepa", "carta di credito")


def _condizione(codice: str | None, testo: str) -> str | None:
    """Riconduce le condizioni 'altro' (99) a bolletta online / domiciliazione quando il testo lo dice."""
    if codice != "99":
        return codice
    t = testo.lower()
    if any(w in t for w in _PAROLE_SDD):
        return SCONTO_DOMICILIAZIONE
    if any(w in t for w in _PAROLE_ONLINE) and "amic" not in t:
        return SCONTO_BOLLETTA_ONLINE
    return codice


def _mesi_sconto(s: ET.Element, oggi: datetime) -> float:
    """Quanti dei prossimi 12 mesi copre lo sconto (PeriodoValidita)."""
    pv = s.find(NS + "PeriodoValidita")
    if pv is None:
        return 12.0
    durata = _f(_t(pv, "DURATA"))
    if durata and durata > 0:
        return min(durata, 12.0)
    if _t(pv, "MESE_VALIDITA"):
        return 1.0
    da, fino = _d(_t(pv, "VALIDO_DA")), _d(_t(pv, "VALIDO_FINO"))
    if da or fino:
        inizio = max(da or oggi, oggi)
        fine = min(fino or datetime.max, oggi + timedelta(days=365))
        giorni = (fine - inizio).days
        return max(0.0, min(12.0, giorni / 30.44))
    return 12.0


def _d(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d/%m/%Y_%H:%M:%S")
    except ValueError:
        return None


# --- modello ------------------------------------------------------------------
@dataclass
class Intervallo:
    fascia: str | None
    prezzo: float
    unita: str | None
    consumo_da: float | None = None
    consumo_a: float | None = None


@dataclass
class Componente:
    nome: str
    macroarea: str | None
    tipologia: str | None
    intervalli: list[Intervallo]


@dataclass
class Sconto:
    nome: str
    descrizione: str
    condizione: str | None
    tipologia: str | None
    prezzo: float
    unita: str | None
    fascia: str | None = None  # 11/12/13 = solo F1/F2/F3
    mesi: float = 12.0  # mesi del primo anno in cui lo sconto vale


@dataclass
class Offerta:
    codice: str
    piva: str | None
    nome: str
    descrizione: str
    tipo_cliente: str | None
    residente: str | None
    tipo_offerta: str | None
    fasce: str | None
    indice: str | None
    coefficiente: float
    durata_mesi: int | None
    singola: bool
    inizio: datetime | None
    fine: datetime | None
    url_offerta: str | None
    sito: str | None
    telefono: str | None
    consumo_min: float | None
    consumo_max: float | None
    potenza_min: float | None
    potenza_max: float | None
    regioni: set[str] = field(default_factory=set)
    province: set[str] = field(default_factory=set)
    comuni: set[str] = field(default_factory=set)
    componenti: list[Componente] = field(default_factory=list)
    dispacciamento_kwh: float = 0.0
    sconti: list[Sconto] = field(default_factory=list)
    condizioni_limitanti: list[str] = field(default_factory=list)

    @property
    def venditore(self) -> str:
        s = (self.sito or self.url_offerta or self.piva or "").lower()
        for pre in ("https://", "http://", "www."):
            s = s.removeprefix(pre)
        return s.split("/")[0] or (self.piva or "?")

    @property
    def variabile(self) -> bool:
        return self.tipo_offerta == OFFERTA_VARIABILE


def parse_offerta(el: ET.Element, oggi: datetime | None = None) -> Offerta:
    oggi = oggi or datetime.now()
    o = Offerta(
        codice=_t(el, "IdentificativiOfferta/COD_OFFERTA") or "",
        piva=_t(el, "IdentificativiOfferta/PIVA_UTENTE"),
        nome=_t(el, "DettaglioOfferta/NOME_OFFERTA") or "?",
        descrizione=_t(el, "DettaglioOfferta/DESCRIZIONE") or "",
        tipo_cliente=_t(el, "DettaglioOfferta/TIPO_CLIENTE"),
        residente=_t(el, "DettaglioOfferta/DOMESTICO_RESIDENTE"),
        tipo_offerta=_t(el, "DettaglioOfferta/TIPO_OFFERTA"),
        fasce=_t(el, "TipoPrezzo/TIPOLOGIA_FASCE"),
        indice=_t(el, "RiferimentiPrezzoEnergia/IDX_PREZZO_ENERGIA"),
        coefficiente=_f(_t(el, "RiferimentiPrezzoEnergia/COEFFICIENTE")) or 1.0,
        durata_mesi=_durata(_t(el, "DettaglioOfferta/DURATA")),
        singola=(_t(el, "DettaglioOfferta/OFFERTA_SINGOLA") or "SI").upper() == "SI",
        inizio=_d(_t(el, "ValiditaOfferta/DATA_INIZIO")),
        fine=_d(_t(el, "ValiditaOfferta/DATA_FINE")),
        url_offerta=_t(el, "DettaglioOfferta/Contatti/URL_OFFERTA"),
        sito=_t(el, "DettaglioOfferta/Contatti/URL_SITO_VENDITORE"),
        telefono=_t(el, "DettaglioOfferta/Contatti/TELEFONO"),
        consumo_min=_f(_t(el, "CaratteristicheOfferta/CONSUMO_MIN")),
        consumo_max=_f(_t(el, "CaratteristicheOfferta/CONSUMO_MAX")),
        potenza_min=_f(_t(el, "CaratteristicheOfferta/POTENZA_MIN")),
        potenza_max=_f(_t(el, "CaratteristicheOfferta/POTENZA_MAX")),
    )
    for z in el.findall(NS + "ZoneOfferta"):
        o.regioni.update(_all(z, "REGIONE"))
        o.province.update(_all(z, "PROVINCIA"))
        o.comuni.update(_all(z, "COMUNE"))
    for ci in el.findall(NS + "ComponenteImpresa"):
        ivs = []
        for iv in ci.findall(NS + "IntervalloPrezzi"):
            p = _f(_t(iv, "PREZZO"))
            if p is None:
                continue
            ivs.append(
                Intervallo(
                    fascia=_t(iv, "FASCIA_COMPONENTE"),
                    prezzo=p,
                    unita=_t(iv, "UNITA_MISURA"),
                    consumo_da=_f(_t(iv, "CONSUMO_DA")),
                    consumo_a=_f(_t(iv, "CONSUMO_A")),
                )
            )
        o.componenti.append(Componente(_t(ci, "NOME") or "", _t(ci, "MACROAREA"), _t(ci, "TIPOLOGIA"), ivs))
    for d in el.findall(NS + "Dispacciamento"):
        # i corrispettivi regolati sono uguali per tutti: contano solo quelli del venditore (con valore)
        if _t(d, "TIPO_DISPACCIAMENTO") == "99":
            o.dispacciamento_kwh += _f(_t(d, "VALORE_DISP")) or 0.0
    for s in el.findall(NS + "Sconto"):
        mesi = _mesi_sconto(s, oggi)
        testo = " ".join(filter(None, (_t(s, "Condizione/DESCRIZIONE_CONDIZIONE"), _t(s, "DESCRIZIONE"), _t(s, "NOME"))))
        fascia = _t(s, "CODICE_COMPONENTE_FASCIA")
        for ps in s.findall(NS + "PrezziSconto"):
            p = _f(_t(ps, "PREZZO"))
            if p is None:
                continue
            o.sconti.append(
                Sconto(
                    nome=_t(s, "NOME") or "Sconto",
                    descrizione=_t(s, "DESCRIZIONE") or "",
                    condizione=_condizione(_t(s, "Condizione/CONDIZIONE_APPLICAZIONE"), testo),
                    tipologia=_t(ps, "TIPOLOGIA"),
                    prezzo=p,
                    unita=_t(ps, "UNITA_MISURA"),
                    fascia=fascia,
                    mesi=mesi,
                )
            )
    for c in el.findall(NS + "CondizioniContrattuali"):
        if _t(c, "LIMITANTE") == "01":
            o.condizioni_limitanti.append((_t(c, "DESCRIZIONE") or _t(c, "ALTRO") or "")[:300])
    return o


def iter_offerte(path: str, oggi: datetime | None = None) -> Iterable[Offerta]:
    """Legge il file in streaming (20 MB, ~3.500 offerte) senza caricarlo tutto in memoria."""
    for _, el in ET.iterparse(path):
        if el.tag == NS + "offerta":
            yield parse_offerta(el, oggi)
            el.clear()


# --- profilo cliente ------------------------------------------------------------
@dataclass
class Profilo:
    domestico: bool = True
    residente: bool = True
    potenza_kw: float = 3.0
    regione: str | None = None  # codice ISTAT a 2 cifre
    comune: str | None = None  # codice ISTAT a 6 cifre
    kwh: dict[str, float] = field(default_factory=lambda: {"F1": 0.0, "F2": 0.0, "F3": 0.0})
    pun: dict[str, float] = field(default_factory=lambda: {"F1": 0.12, "F2": 0.12, "F3": 0.12})
    bolletta_online: bool = True
    domiciliazione: bool = True
    includi_dual: bool = False

    @property
    def totale(self) -> float:
        return sum(self.kwh.values())


def compatibile(o: Offerta, p: Profilo, oggi: datetime) -> str | None:
    """None se l'offerta è sottoscrivibile dal profilo, altrimenti il motivo dell'esclusione."""
    if o.tipo_cliente != (CLIENTE_DOMESTICO if p.domestico else CLIENTE_ALTRI_USI):
        return "tipo cliente"
    if p.domestico and o.residente in ("01", "02"):
        if (o.residente == "01") != p.residente:
            return "residenza"
    if p.domestico and p.residente and any(w in o.nome.lower() for w in ("seconda casa", "non resid")):
        return "residenza"
    if not o.singola and not p.includi_dual:
        return "solo luce+gas"
    if o.inizio and o.inizio > oggi or o.fine and o.fine < oggi:
        return "fuori validità"
    if o.tipo_offerta not in (OFFERTA_FISSA, OFFERTA_VARIABILE):
        return "tipo prezzo non stimabile"
    if o.variabile and o.indice not in IDX_PUN:
        return "indice non stimabile"
    if o.fasce not in (FASCE_MONO, FASCE_F123, FASCE_BIORARIA, FASCE_PERSONALIZZATE):
        return "fasce non gestite"
    c = p.totale
    if o.consumo_min and c < o.consumo_min or o.consumo_max and c > o.consumo_max:
        return "consumo fuori limiti"
    if o.potenza_min and p.potenza_kw < o.potenza_min or o.potenza_max and p.potenza_kw > o.potenza_max:
        return "potenza fuori limiti"
    if o.regioni or o.province or o.comuni:
        provincia = p.comune[:3] if p.comune else None
        if not (
            (p.regione and p.regione in o.regioni)
            or (provincia and provincia in o.province)
            or (p.comune and p.comune in o.comuni)
        ):
            return "zona"
    return None


# --- calcolo ------------------------------------------------------------------
def _kwh_price(v: float) -> float:
    return v / 1000 if v > MAX_EURO_KWH else v


def _prezzo_fascia(ivs: list[Intervallo], fasce: str | None, banda: str, consumo: float) -> float | None:
    """Prezzo €/kWh di una componente per la banda F1/F2/F3."""
    ivs = [i for i in ivs if i.unita == UNITA_EURO_KWH]
    if not ivs:
        return None
    # scaglioni di consumo annuo
    scaglione = [i for i in ivs if i.consumo_da is not None or i.consumo_a is not None]
    if scaglione:
        ok = [
            i for i in ivs
            if (i.consumo_da or 0) <= consumo and (i.consumo_a is None or i.consumo_a == 0 or consumo <= i.consumo_a)
        ]
        ivs = ok or ivs
    by = {i.fascia: i.prezzo for i in ivs}
    if fasce == FASCE_F123:
        key = {"F1": "01", "F2": "02", "F3": "03"}[banda]
        if key in by:
            return _kwh_price(by[key])
    elif fasce == FASCE_BIORARIA:
        key = "07" if banda == "F1" else "08"
        if key in by:
            return _kwh_price(by[key])
    # monoraria, fasce personalizzate o prezzo unico: un solo valore per tutte le ore
    if len(set(by.values())) == 1 or fasce in (FASCE_MONO, FASCE_PERSONALIZZATE):
        for k in ("01", "91", None):
            if k in by:
                return _kwh_price(by[k])
        return _kwh_price(next(iter(by.values())))
    return None


@dataclass
class Stima:
    offerta: Offerta
    totale: float  # € / anno, solo voci del venditore (+ PUN per le variabili), IVA esclusa
    quota_fissa: float
    energia: float
    una_tantum: float
    sconti: float
    sconti_esclusi: list[str]
    approssimata: bool

    @property
    def prezzo_medio(self) -> float:
        kwh = sum(self._kwh.values()) if hasattr(self, "_kwh") else 0
        return self.energia / kwh if kwh else 0.0

    def as_dict(self) -> dict[str, Any]:
        o = self.offerta
        return {
            "nome": o.nome,
            "venditore": o.venditore,
            "codice_offerta": o.codice,
            "tipo": "variabile (PUN + spread)" if o.variabile else "prezzo fisso",
            "costo_annuo": round(self.totale, 2),
            "quota_fissa_anno": round(self.quota_fissa, 2),
            "costo_energia_anno": round(self.energia, 2),
            "prezzo_medio_kwh": round(self.prezzo_medio, 4),
            "sconti_applicati": round(self.sconti, 2),
            "sconti_non_applicati": self.sconti_esclusi,
            "una_tantum": round(self.una_tantum, 2),
            "durata_mesi": o.durata_mesi,
            "valida_fino": o.fine.strftime("%d/%m/%Y") if o.fine else None,
            "condizioni_limitanti": o.condizioni_limitanti,
            "stima_approssimata": self.approssimata,
            "url": o.url_offerta or (f"https://{o.venditore}" if o.venditore else None),
            "telefono": o.telefono,
        }


def stima(o: Offerta, p: Profilo) -> Stima | None:
    """Spesa annua per le sole voci che cambiano tra venditori (oneri, rete e imposte sono uguali per tutti)."""
    consumo = p.totale
    fissa = energia = una_tantum = 0.0
    approssimata = o.fasce in (FASCE_BIORARIA, FASCE_PERSONALIZZATE)
    for c in o.componenti:
        for i in c.intervalli:
            if i.unita == UNITA_EURO_ANNO:
                fissa += i.prezzo
            elif i.unita == UNITA_EURO_KW:
                fissa += i.prezzo * p.potenza_kw
            elif i.unita == UNITA_EURO_UNA_TANTUM:
                una_tantum += i.prezzo
        if any(i.unita == UNITA_EURO_KWH for i in c.intervalli):
            for banda in FASCE:
                prezzo = _prezzo_fascia(c.intervalli, o.fasce, banda, consumo)
                if prezzo is None:
                    return None  # struttura non interpretabile: meglio escludere che sbagliare
                if any(i.prezzo > MAX_EURO_KWH for i in c.intervalli if i.unita == UNITA_EURO_KWH):
                    approssimata = True
                energia += prezzo * p.kwh[banda]
    energia += o.dispacciamento_kwh * consumo
    if o.variabile:
        energia += sum(p.pun[b] * o.coefficiente * p.kwh[b] for b in FASCE)
    if energia <= 0:
        return None  # offerta senza prezzo dell'energia utilizzabile

    sconti = 0.0
    esclusi: list[str] = []
    kwh_fascia = {"11": p.kwh["F1"], "12": p.kwh["F2"], "13": p.kwh["F3"]}
    for s in o.sconti:
        applicabile = s.condizione in (None, SCONTO_SEMPRE) or (
            s.condizione == SCONTO_BOLLETTA_ONLINE and p.bolletta_online
        ) or (s.condizione == SCONTO_DOMICILIAZIONE and p.domiciliazione)
        if not applicabile:
            esclusi.append(f"{s.nome}: {s.descrizione[:120]}")
            continue
        quota = s.mesi / 12
        if s.unita == UNITA_EURO_UNA_TANTUM:
            sconti += s.prezzo
        elif s.unita == UNITA_EURO_ANNO:
            sconti += s.prezzo * quota
        elif s.unita == UNITA_EURO_KWH:
            sconti += _kwh_price(s.prezzo) * kwh_fascia.get(s.fascia or "", consumo) * quota
        elif s.unita == UNITA_PERCENTUALE and 0 < s.prezzo < 100:
            sconti += energia * s.prezzo / 100 * quota
        else:
            esclusi.append(f"{s.nome}: unità non gestita")
    if sconti > 0.6 * (fissa + energia):
        # sconti che azzerano la bolletta: dati quasi certamente incoerenti
        return None
    totale = fissa + energia + una_tantum - sconti
    st = Stima(o, totale, fissa, energia, una_tantum, sconti, esclusi, approssimata)
    st._kwh = dict(p.kwh)  # type: ignore[attr-defined]
    return st


@dataclass
class Confronto:
    stime: list[Stima]
    esclusi: dict[str, int]
    attuale: Stima | None = None
    attuale_trovata: bool = False


def confronta(path: str, p: Profilo, oggi: datetime | None = None, codice_attuale: str | None = None) -> Confronto:
    """Stime ordinate per costo, offerte escluse per motivo e, se richiesta, la stima dell'offerta attuale."""
    oggi = oggi or datetime.now()
    risultati: list[Stima] = []
    esclusi: dict[str, int] = {}
    cod = (codice_attuale or "").strip().upper()
    attuale: Stima | None = None
    trovata = False
    for o in iter_offerte(path, oggi):
        if cod and o.codice.upper() == cod:
            trovata = True
            attuale = stima(o, p)
        motivo = compatibile(o, p, oggi)
        if motivo is None:
            s = stima(o, p)
            if s is None:
                motivo = "prezzi non interpretabili"
            else:
                risultati.append(s)
                continue
        esclusi[motivo] = esclusi.get(motivo, 0) + 1
    risultati.sort(key=lambda s: s.totale)
    return Confronto(risultati, esclusi, attuale, trovata)


def trova(path: str, codice: str) -> Offerta | None:
    codice = codice.strip().upper()
    for o in iter_offerte(path):
        if o.codice.upper() == codice:
            return o
    return None

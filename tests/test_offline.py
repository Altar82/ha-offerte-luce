"""Test senza Home Assistant: parser ARERA, calcolo spesa e fasce orarie."""

import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

BASE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "offerte_luce"


def _carica(nome):
    spec = importlib.util.spec_from_file_location(nome, BASE / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


arera = _carica("arera")
consumi = _carica("consumi")
ROMA = consumi.ROMA
NSU = "http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01"


def offerta(codice, *, tipo="02", fasce="03", cliente="01", prezzi=("0.02", "0.02", "0.02"), quota="120",
            extra="", zone="", residente="", singola="SI"):
    ivs = "".join(
        f"<IntervalloPrezzi><FASCIA_COMPONENTE>0{i + 1}</FASCIA_COMPONENTE><PREZZO>{p}</PREZZO>"
        f"<UNITA_MISURA>03</UNITA_MISURA></IntervalloPrezzi>"
        for i, p in enumerate(prezzi)
    )
    res = f"<DOMESTICO_RESIDENTE>{residente}</DOMESTICO_RESIDENTE>" if residente else ""
    return f"""<offerta>
<IdentificativiOfferta><PIVA_UTENTE>1</PIVA_UTENTE><COD_OFFERTA>{codice}</COD_OFFERTA></IdentificativiOfferta>
<DettaglioOfferta><OFFERTA_SINGOLA>{singola}</OFFERTA_SINGOLA><TIPO_CLIENTE>{cliente}</TIPO_CLIENTE>{res}
<TIPO_OFFERTA>{tipo}</TIPO_OFFERTA><NOME_OFFERTA>Offerta {codice}</NOME_OFFERTA><DURATA>-1</DURATA>
<Contatti><URL_SITO_VENDITORE>www.{codice.lower()}.it</URL_SITO_VENDITORE></Contatti></DettaglioOfferta>
<RiferimentiPrezzoEnergia><IDX_PREZZO_ENERGIA>12</IDX_PREZZO_ENERGIA></RiferimentiPrezzoEnergia>
<ValiditaOfferta><DATA_INIZIO>01/01/2026_00:00:00</DATA_INIZIO><DATA_FINE>31/12/2026_23:59:59</DATA_FINE></ValiditaOfferta>
<TipoPrezzo><TIPOLOGIA_FASCE>{fasce}</TIPOLOGIA_FASCE></TipoPrezzo>
<ComponenteImpresa><NOME>Energia</NOME><MACROAREA>04</MACROAREA>{ivs}</ComponenteImpresa>
<ComponenteImpresa><NOME>Quota</NOME><MACROAREA>01</MACROAREA><IntervalloPrezzi><PREZZO>{quota}</PREZZO>
<UNITA_MISURA>01</UNITA_MISURA></IntervalloPrezzi></ComponenteImpresa>{extra}{zone}
</offerta>"""


def scrivi(tmp_path, *offerte):
    p = tmp_path / "o.xml"
    p.write_text(f'<ListaOfferteMercatoLibero xmlns="{NSU}">{"".join(offerte)}</ListaOfferteMercatoLibero>')
    return str(p)


PROFILO = dict(kwh={"F1": 1000.0, "F2": 1000.0, "F3": 1000.0}, pun={"F1": 0.2, "F2": 0.1, "F3": 0.1})
OGGI = datetime(2026, 6, 1)


def test_variabile_con_dispacciamento_e_sconti(tmp_path):
    extra = """<Dispacciamento><TIPO_DISPACCIAMENTO>99</TIPO_DISPACCIAMENTO><VALORE_DISP>0.01</VALORE_DISP></Dispacciamento>
<Dispacciamento><TIPO_DISPACCIAMENTO>14</TIPO_DISPACCIAMENTO></Dispacciamento>
<Sconto><NOME>Tre mesi</NOME><DESCRIZIONE>x</DESCRIZIONE><PeriodoValidita><DURATA>3</DURATA></PeriodoValidita>
<Condizione><CONDIZIONE_APPLICAZIONE>00</CONDIZIONE_APPLICAZIONE></Condizione>
<PrezziSconto><TIPOLOGIA>03</TIPOLOGIA><UNITA_MISURA>01</UNITA_MISURA><PREZZO>40</PREZZO></PrezziSconto></Sconto>
<Sconto><NOME>Web</NOME><DESCRIZIONE>y</DESCRIZIONE><Condizione><CONDIZIONE_APPLICAZIONE>99</CONDIZIONE_APPLICAZIONE>
<DESCRIZIONE_CONDIZIONE>Invio bolletta via e-mail</DESCRIZIONE_CONDIZIONE></Condizione>
<PrezziSconto><TIPOLOGIA>01</TIPOLOGIA><UNITA_MISURA>01</UNITA_MISURA><PREZZO>12</PREZZO></PrezziSconto></Sconto>
<Sconto><NOME>Amico</NOME><DESCRIZIONE>porta un amico</DESCRIZIONE><Condizione><CONDIZIONE_APPLICAZIONE>99</CONDIZIONE_APPLICAZIONE>
<DESCRIZIONE_CONDIZIONE>Porta un amico</DESCRIZIONE_CONDIZIONE></Condizione>
<PrezziSconto><TIPOLOGIA>01</TIPOLOGIA><UNITA_MISURA>05</UNITA_MISURA><PREZZO>50</PREZZO></PrezziSconto></Sconto>"""
    path = scrivi(tmp_path, offerta("A", extra=extra))
    c = arera.confronta(path, arera.Profilo(**PROFILO), OGGI)
    s = c.stime[0]
    # 120 + (0.02 + 0.01) * 3000 + PUN (200 + 100 + 100) - (40 * 3/12 + 12)
    assert round(s.totale, 2) == 120 + 90 + 400 - 22
    assert len(s.sconti_esclusi) == 1 and "Amico" in s.sconti_esclusi[0]
    senza_online = arera.confronta(path, arera.Profilo(**PROFILO, bolletta_online=False), OGGI).stime[0]
    assert round(senza_online.totale, 2) == round(s.totale + 12, 2)


def test_fisso_unita_sbagliata_e_ordine(tmp_path):
    path = scrivi(
        tmp_path,
        offerta("CARA", tipo="01", fasce="01", prezzi=("0.30",)),
        offerta("MWH", tipo="01", fasce="01", prezzi=("150",)),  # €/MWh scritto come €/kWh
    )
    c = arera.confronta(path, arera.Profilo(**PROFILO), OGGI)
    assert [s.offerta.codice for s in c.stime] == ["MWH", "CARA"]
    assert round(c.stime[0].totale, 2) == 120 + 0.15 * 3000
    assert c.stime[0].approssimata


def test_filtri(tmp_path):
    zona = "<ZoneOfferta><REGIONE>12</REGIONE></ZoneOfferta>"
    path = scrivi(
        tmp_path,
        offerta("BUSINESS", cliente="02"),
        offerta("LAZIO", zone=zona),
        offerta("NONRES", residente="02"),
        offerta("DUAL", singola="NO"),
        offerta("OK"),
    )
    c = arera.confronta(path, arera.Profilo(**PROFILO, regione="03"), OGGI)
    assert [s.offerta.codice for s in c.stime] == ["OK"]
    assert c.esclusi == {"tipo cliente": 1, "zona": 1, "residenza": 1, "solo luce+gas": 1}
    c = arera.confronta(path, arera.Profilo(**PROFILO, regione="12"), OGGI)
    assert {s.offerta.codice for s in c.stime} == {"OK", "LAZIO"}
    scad = arera.confronta(path, arera.Profilo(**PROFILO), datetime(2027, 2, 1))
    assert scad.stime == [] and scad.esclusi["fuori validità"] == 2


def test_offerta_attuale_per_codice(tmp_path):
    path = scrivi(tmp_path, offerta("BUSINESS", cliente="02"), offerta("OK"))
    c = arera.confronta(path, arera.Profilo(**PROFILO), OGGI, codice_attuale="business")
    assert c.attuale_trovata and c.attuale is not None


def test_sconti_eccessivi_scartati(tmp_path):
    extra = """<Sconto><NOME>Enorme</NOME><DESCRIZIONE>x</DESCRIZIONE><Condizione><CONDIZIONE_APPLICAZIONE>00</CONDIZIONE_APPLICAZIONE></Condizione>
<PrezziSconto><TIPOLOGIA>03</TIPOLOGIA><UNITA_MISURA>03</UNITA_MISURA><PREZZO>0.5</PREZZO></PrezziSconto></Sconto>"""
    c = arera.confronta(scrivi(tmp_path, offerta("X", extra=extra)), arera.Profilo(**PROFILO), OGGI)
    assert c.stime == [] and c.esclusi == {"prezzi non interpretabili": 1}


def test_fasce():
    f = lambda *a: consumi.fascia(datetime(*a, tzinfo=ROMA))
    assert f(2026, 11, 16, 10) == "F1"  # lunedì
    assert f(2026, 11, 16, 7) == "F2"
    assert f(2026, 11, 16, 19) == "F2"
    assert f(2026, 11, 16, 23) == "F3"
    assert f(2026, 11, 14, 10) == "F2"  # sabato
    assert f(2026, 11, 14, 6) == "F3"
    assert f(2026, 11, 15, 12) == "F3"  # domenica
    assert f(2026, 12, 8, 10) == "F3"  # Immacolata, martedì
    assert consumi.pasqua(2026).isoformat() == "2026-04-05"
    assert f(2026, 4, 6, 10) == "F3"  # Pasquetta
    # UTC: 9:00 UTC di un lunedì d'inverno = 10:00 a Roma
    assert consumi.fascia(datetime(2026, 11, 16, 9, tzinfo=timezone.utc)) == "F1"


def test_per_fascia_annualizza():
    inizio = datetime(2026, 1, 12, 0, tzinfo=ROMA)  # lunedì, nessun festivo
    righe = [(inizio + timedelta(hours=h), 1.0) for h in range(24 * 7 * 4)]  # 4 settimane, 1 kWh/h
    kwh, giorni = consumi.per_fascia(righe)
    assert round(giorni) == 28
    # in una settimana: F1 = 5*11 = 55 h, F2 = 5*5 + 16 = 41 h, F3 = 168 - 96 = 72 h
    k = 365 / 28
    assert round(kwh["F1"], 3) == round(55 * 4 * k, 3)
    assert round(kwh["F2"], 3) == round(41 * 4 * k, 3)
    assert round(kwh["F3"], 3) == round(72 * 4 * k, 3)
    assert consumi.per_fascia(righe[:24])[1] < consumi.GIORNI_MINIMI

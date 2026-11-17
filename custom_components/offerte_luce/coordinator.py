"""Scarica le offerte, legge i consumi e fa il confronto."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import arera
from .consumi import GIORNI_MINIMI, ROMA, per_fascia
from .const import (
    ATTUALE_CODICE,
    ATTUALE_FISSO,
    ATTUALE_VARIABILE,
    CLIENTE_ALTRI_USI,
    CLIENTE_NON_RESIDENTE,
    CONF_ATTUALE,
    CONF_CODICE,
    CONF_COMUNE,
    CONF_CONSUMO_ANNUO,
    CONF_FORNITURA,
    CONF_NOTIFICA,
    CONF_PSV,
    CONF_PSV_ENTITA,
    CONF_DUAL,
    CONF_ONLINE,
    CONF_ORE,
    CONF_POTENZA,
    CONF_PREZZO,
    CONF_PUN_ENTITA,
    CONF_PUN_F1,
    CONF_PUN_F2,
    CONF_PUN_F3,
    CONF_QUOTA,
    CONF_REGIONE,
    CONF_SDD,
    CONF_SOGLIA,
    CONF_STAT,
    CONF_TIPO_CLIENTE,
    DEFAULT_ORE,
    DEFAULT_PSV,
    DEFAULT_PUN,
    DEFAULT_SOGLIA,
    DOMAIN,
    EVENTO,
    FORNITURA_GAS,
    FORNITURA_LUCE,
    IVA_ALTRI_USI,
    IVA_DOMESTICO,
    KWH_PER_SMC,
    QUOTE_FASCE,
    SOGLIA_IVA_GAS,
    TOP,
)

_LOGGER = logging.getLogger(__name__)
GIORNI_INDIETRO = 7
TIMEOUT = aiohttp.ClientTimeout(total=180)


@dataclass
class Risultato:
    data_file: str
    kwh: dict[str, float]
    giorni_dati: float
    pun: dict[str, float]
    pun_fonte: str
    confrontate: int
    esclusi: dict[str, int]
    migliori: list[dict[str, Any]]
    attuale: dict[str, Any] | None
    costo_attuale: float | None
    risparmio: float | None
    conviene: bool
    soglia: float
    iva: float
    note: list[str] = field(default_factory=list)
    fornitura: str = FORNITURA_LUCE

    @property
    def gas(self) -> bool:
        return self.fornitura == FORNITURA_GAS

    @property
    def unita(self) -> str:
        return "Smc" if self.gas else "kWh"

    @property
    def migliore(self) -> dict[str, Any] | None:
        return self.migliori[0] if self.migliori else None


def opz(entry: ConfigEntry) -> dict[str, Any]:
    """Dati e opzioni uniti (le opzioni vincono)."""
    return {**entry.data, **entry.options}


class OfferteCoordinator(DataUpdateCoordinator[Risultato]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        ore = float(opz(entry).get(CONF_ORE, DEFAULT_ORE))
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=ore), config_entry=entry)
        self.cartella = hass.config.path(DOMAIN)
        self.fornitura = opz(entry).get(CONF_FORNITURA, FORNITURA_LUCE)
        self.gas = self.fornitura == FORNITURA_GAS
        self._prefisso = f"offerte_{self.fornitura}_"
        self._ultima_migliore: str | None = None
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")

    async def async_carica_stato(self) -> None:
        dati = await self._store.async_load() or {}
        self._ultima_migliore = dati.get("ultima_migliore")

    # --- file ARERA ------------------------------------------------------------
    def _percorso(self, giorno: datetime) -> str:
        return os.path.join(self.cartella, f"{self._prefisso}{giorno:%Y%m%d}.xml")

    def _file_in_cache(self) -> list[str]:
        if not os.path.isdir(self.cartella):
            return []
        return sorted(f for f in os.listdir(self.cartella) if f.startswith(self._prefisso) and f.endswith(".xml"))

    def _salva(self, percorso: str, contenuto: bytes) -> None:
        os.makedirs(self.cartella, exist_ok=True)
        tmp = percorso + ".tmp"
        with open(tmp, "wb") as f:
            f.write(contenuto)
        os.replace(tmp, percorso)
        for vecchio in self._file_in_cache():
            p = os.path.join(self.cartella, vecchio)
            if p != percorso:
                os.remove(p)

    async def _scarica(self) -> tuple[str, str]:
        """Ritorna (percorso, data) dell'elenco più recente disponibile."""
        oggi = dt_util.now(ROMA)
        sessione = async_get_clientsession(self.hass)
        for n in range(GIORNI_INDIETRO):
            giorno = oggi - timedelta(days=n)
            percorso = self._percorso(giorno)
            if await self.hass.async_add_executor_job(os.path.exists, percorso):
                return percorso, f"{giorno:%d/%m/%Y}"
            try:
                async with sessione.get(arera.url_for(giorno.date(), self.gas), timeout=TIMEOUT) as r:
                    if r.status == 404:
                        continue
                    r.raise_for_status()
                    contenuto = await r.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Download offerte del %s non riuscito: %s", giorno.date(), err)
                continue
            if b"<" not in contenuto[:200]:
                continue
            await self.hass.async_add_executor_job(self._salva, percorso, contenuto)
            return percorso, f"{giorno:%d/%m/%Y}"
        cache = await self.hass.async_add_executor_job(self._file_in_cache)
        if cache:
            nome = cache[-1]
            d = nome.removeprefix(self._prefisso).removesuffix(".xml")
            return os.path.join(self.cartella, nome), f"{d[6:8]}/{d[4:6]}/{d[0:4]}"
        raise UpdateFailed("Impossibile scaricare l'elenco delle offerte dal Portale Offerte ARERA")

    # --- consumi -----------------------------------------------------------------
    async def _consumi(self, stat: str) -> tuple[dict[str, float], float]:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        fine = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        inizio = fine - timedelta(days=365)
        dati = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, inizio, fine, {stat}, "hour", None, {"change"}
        )
        righe = []
        for r in dati.get(stat, []):
            t = r.get("start")
            if isinstance(t, (int, float)):
                t = datetime.fromtimestamp(t, tz=dt_util.UTC)
            if t is not None and r.get("change") is not None:
                righe.append((t, float(r["change"])))
        return per_fascia(righe)

    async def _consumo_annuo(self, o: dict[str, Any], note: list[str]) -> tuple[dict[str, float], float]:
        """Consumo annuo per fascia (luce, kWh) o totale in "F1" (gas, Smc) e giorni di dati usati."""
        manuale = float(o.get(CONF_CONSUMO_ANNUO) or 0)
        stat = o.get(CONF_STAT)
        per_f: dict[str, float] = {"F1": 0.0, "F2": 0.0, "F3": 0.0}
        giorni = 0.0
        if stat:
            try:
                per_f, giorni = await self._consumi(stat)
            except Exception as err:  # noqa: BLE001 - il recorder può non essere pronto
                if not manuale:
                    raise UpdateFailed(f"Lettura delle statistiche di {stat} non riuscita: {err}") from err
                _LOGGER.debug("Statistiche di %s non leggibili, uso il consumo indicato: %s", stat, err)
            if self.gas and (st := self.hass.states.get(stat)) is not None:
                unita = str(st.attributes.get("unit_of_measurement") or "")
                if unita in (UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.MEGA_WATT_HOUR):
                    k = KWH_PER_SMC * (1000 if unita == UnitOfEnergy.MEGA_WATT_HOUR else 1)
                    per_f = {f: v / k for f, v in per_f.items()}
        ok = giorni >= GIORNI_MINIMI and sum(per_f.values()) > 0
        if manuale:
            if self.gas:
                return {"F1": manuale, "F2": 0.0, "F3": 0.0}, giorni
            tot = sum(per_f.values()) if ok else 0
            quote = {f: v / tot for f, v in per_f.items()} if tot else QUOTE_FASCE
            if not tot:
                note.append("Ripartizione F1/F2/F3 tipica: per quella reale serve il sensore di energia")
            return {f: manuale * q for f, q in quote.items()}, giorni
        if not ok:
            raise UpdateFailed(
                f"Servono almeno {GIORNI_MINIMI} giorni di statistiche orarie di {stat} (ora: {giorni:.0f}) "
                "oppure il consumo annuo dalla bolletta"
                if stat
                else "Indica il consumo annuo dalla bolletta o un sensore con le statistiche"
            )
        if giorni < 360:
            note.append(f"Consumo annuo stimato da {giorni:.0f} giorni di dati")
            if self.gas:
                note.append(
                    "Il gas si consuma soprattutto d'inverno: con meno di un anno di dati la stima è poco "
                    "affidabile, meglio indicare il consumo annuo che trovi in bolletta"
                )
        if self.gas:
            return {"F1": sum(per_f.values()), "F2": 0.0, "F3": 0.0}, giorni
        return per_f, giorni

    def _psv(self, o: dict[str, Any]) -> tuple[float, str]:
        ent = o.get(CONF_PSV_ENTITA)
        if ent and (st := self.hass.states.get(ent)) is not None:
            try:
                v = float(st.state)
            except ValueError:
                pass
            else:
                unita = str(st.attributes.get("unit_of_measurement") or "").lower()
                if "mwh" in unita or v > 10:  # €/MWh
                    v = v * KWH_PER_SMC / 1000
                if 0 < v < 10:
                    return v, ent
        return float(o.get(CONF_PSV) or DEFAULT_PSV), "valore impostato"

    def _iva(self, domestico: bool, consumo: float) -> float:
        if not domestico:
            return IVA_ALTRI_USI
        if self.gas and consumo > SOGLIA_IVA_GAS:
            # 10% fino a 480 Smc l'anno, 22% oltre (media pesata sui consumi)
            return (SOGLIA_IVA_GAS * IVA_DOMESTICO + (consumo - SOGLIA_IVA_GAS) * IVA_ALTRI_USI) / consumo
        return IVA_DOMESTICO

    # --- PUN -----------------------------------------------------------------------
    def _pun(self, o: dict[str, Any]) -> tuple[dict[str, float], str]:
        ent = o.get(CONF_PUN_ENTITA)
        if ent and (st := self.hass.states.get(ent)) is not None:
            try:
                v = float(st.state)
            except ValueError:
                pass
            else:
                if v > 1.5:  # €/MWh
                    v /= 1000
                if 0 < v < 1.5:
                    return {"F1": v, "F2": v, "F3": v}, ent
        return (
            {
                "F1": float(o.get(CONF_PUN_F1) or DEFAULT_PUN),
                "F2": float(o.get(CONF_PUN_F2) or o.get(CONF_PUN_F1) or DEFAULT_PUN),
                "F3": float(o.get(CONF_PUN_F3) or o.get(CONF_PUN_F1) or DEFAULT_PUN),
            },
            "valori impostati",
        )

    # --- aggiornamento ---------------------------------------------------------------
    async def _async_update_data(self) -> Risultato:
        o = opz(self.config_entry)
        note: list[str] = []
        percorso, data_file = await self._scarica()

        kwh, giorni = await self._consumo_annuo(o, note)

        if self.gas:
            psv, pun_fonte = self._psv(o)
            pun = {"F1": psv, "F2": psv, "F3": psv}
        else:
            pun, pun_fonte = self._pun(o)
        tipo = o.get(CONF_TIPO_CLIENTE)
        comune = (o.get(CONF_COMUNE) or "").strip() or None
        profilo = arera.Profilo(
            domestico=tipo != CLIENTE_ALTRI_USI,
            residente=tipo != CLIENTE_NON_RESIDENTE,
            potenza_kw=float(o.get(CONF_POTENZA) or 3),
            regione=o.get(CONF_REGIONE),
            comune=comune,
            kwh=kwh,
            pun=pun,
            bolletta_online=bool(o.get(CONF_ONLINE, True)),
            domiciliazione=bool(o.get(CONF_SDD, True)),
            includi_dual=bool(o.get(CONF_DUAL, False)),
            gas=self.gas,
            psv=pun["F1"],
        )
        modo = o.get(CONF_ATTUALE)
        codice = o.get(CONF_CODICE) if modo == ATTUALE_CODICE else None
        conf: arera.Confronto = await self.hass.async_add_executor_job(
            arera.confronta, percorso, profilo, dt_util.now(ROMA).replace(tzinfo=None), codice
        )
        if not conf.stime:
            raise UpdateFailed("Nessuna offerta compatibile trovata nell'elenco ARERA")

        attuale: dict[str, Any] | None = None
        costo_attuale: float | None = None
        consumo = profilo.totale
        if modo == ATTUALE_CODICE and codice:
            if conf.attuale:
                attuale = conf.attuale.as_dict()
                costo_attuale = conf.attuale.totale
            elif conf.attuale_trovata:
                note.append("Offerta attuale trovata ma con prezzi non interpretabili")
            else:
                note.append("Codice offerta attuale non presente nell'elenco di oggi: usa il prezzo manuale")
        elif modo in (ATTUALE_FISSO, ATTUALE_VARIABILE) and o.get(CONF_PREZZO) is not None:
            prezzo = float(o[CONF_PREZZO])
            quota = float(o.get(CONF_QUOTA) or 0)
            energia = prezzo * consumo
            if modo == ATTUALE_VARIABILE:
                energia += sum(pun[f] * kwh[f] for f in kwh)
            costo_attuale = quota + energia
            indice = "PSV" if self.gas else "PUN"
            attuale = {
                "nome": "Offerta attuale (dati inseriti)",
                "tipo": f"variabile ({indice} + spread)" if modo == ATTUALE_VARIABILE else "prezzo fisso",
                "costo_annuo": round(costo_attuale, 2),
                "quota_fissa_anno": round(quota, 2),
                "costo_energia_anno": round(energia, 2),
                ("prezzo_medio_smc" if self.gas else "prezzo_medio_kwh"): round(energia / consumo, 4) if consumo else None,
            }

        migliori = [s.as_dict() for s in conf.stime[:TOP]]
        soglia = float(o.get(CONF_SOGLIA) or DEFAULT_SOGLIA)
        risparmio = round(costo_attuale - conf.stime[0].totale, 2) if costo_attuale is not None else None
        conviene = risparmio is not None and risparmio >= soglia
        iva = self._iva(tipo != CLIENTE_ALTRI_USI, consumo)

        ris = Risultato(
            data_file=data_file,
            kwh={f: round(v, 1) for f, v in kwh.items()},
            giorni_dati=round(giorni, 1),
            pun=pun,
            pun_fonte=pun_fonte,
            confrontate=len(conf.stime),
            esclusi=conf.esclusi,
            migliori=migliori,
            attuale=attuale,
            costo_attuale=round(costo_attuale, 2) if costo_attuale is not None else None,
            risparmio=risparmio,
            conviene=conviene,
            soglia=soglia,
            iva=iva,
            note=note,
            fornitura=self.fornitura,
        )
        codice_migliore = migliori[0]["codice_offerta"]
        if conviene and codice_migliore != self._ultima_migliore:
            self.hass.bus.async_fire(
                EVENTO,
                {
                    "offerta": migliori[0]["nome"],
                    "venditore": migliori[0]["venditore"],
                    "codice_offerta": codice_migliore,
                    "costo_annuo": migliori[0]["costo_annuo"],
                    "costo_attuale": ris.costo_attuale,
                    "risparmio_annuo": risparmio,
                    "url": migliori[0]["url"],
                    "fornitura": self.fornitura,
                },
            )
            if o.get(CONF_NOTIFICA, True):
                persistent_notification.async_create(
                    self.hass,
                    (
                        f"**{migliori[0]['nome']}** ({migliori[0]['venditore']}) costerebbe circa "
                        f"{migliori[0]['costo_annuo']:.0f} €/anno contro {ris.costo_attuale:.0f} € dell'offerta "
                        f"attuale: **{risparmio:.0f} € in meno all'anno** (IVA esclusa, solo le voci del venditore).\n\n"
                        + (f"[Vedi l'offerta]({migliori[0]['url']})" if migliori[0].get("url") else "")
                    ),
                    title=f"{self.config_entry.title}: c'è un'offerta più conveniente",
                    notification_id=f"{DOMAIN}_{self.config_entry.entry_id}",
                )
        nuovo = codice_migliore if conviene else None
        if nuovo != self._ultima_migliore:
            self._ultima_migliore = nuovo
            await self._store.async_save({"ultima_migliore": nuovo})
        return ris

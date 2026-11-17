"""Configurazione di Offerte Luce."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector as sel

from .const import (
    ATTUALE_CODICE,
    ATTUALE_FISSO,
    ATTUALE_NESSUNA,
    ATTUALE_VARIABILE,
    CLIENTE_ALTRI_USI,
    CLIENTE_NON_RESIDENTE,
    CLIENTE_RESIDENTE,
    CONF_ATTUALE,
    CONF_CODICE,
    CONF_COMUNE,
    CONF_CONSUMO_ANNUO,
    CONF_FORNITURA,
    CONF_NOTIFICA,
    CONF_PSV,
    CONF_PSV_BOLLETTA,
    CONF_PSV_ENTITA,
    CONF_DUAL,
    CONF_ONLINE,
    CONF_ORE,
    CONF_POTENZA,
    CONF_PREZZO,
    CONF_PUN_BOLLETTA,
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
    FORNITURA_GAS,
    FORNITURA_LUCE,
    KWH_PER_SMC,
    REGIONI,
)


async def _da_energia(hass: HomeAssistant, gas: bool = False) -> tuple[str | None, float | None]:
    """Sensore di prelievo dalla rete (o del gas) e prezzo fisso impostati nella dashboard Energia, se ci sono."""
    try:
        from homeassistant.components.energy.data import async_get_manager

        dati = (await async_get_manager(hass)).data or {}
    except Exception:  # noqa: BLE001 - la dashboard Energia può non essere configurata
        return None, None
    for src in dati.get("energy_sources", []):
        if gas:
            if src.get("type") == "gas" and src.get("stat_energy_from"):
                return src["stat_energy_from"], src.get("number_energy_price")
            continue
        if src.get("type") != "grid":
            continue
        flussi = src.get("flow_from") or [src]
        for f in flussi:
            if stat := f.get("stat_energy_from"):
                return stat, f.get("number_energy_price")
    return None, None


def _select(chiave: str, valori: list[str]) -> sel.SelectSelector:
    return sel.SelectSelector(
        sel.SelectSelectorConfig(options=valori, translation_key=chiave, mode=sel.SelectSelectorMode.DROPDOWN)
    )


def _num(minimo: float, massimo: float, passo: float | str, unita: str | None = None) -> sel.NumberSelector:
    return sel.NumberSelector(
        sel.NumberSelectorConfig(min=minimo, max=massimo, step=passo, unit_of_measurement=unita, mode=sel.NumberSelectorMode.BOX)
    )


def _gas(d: dict[str, Any]) -> bool:
    return d.get(CONF_FORNITURA) == FORNITURA_GAS


def _schema_fornitura(d: dict[str, Any]) -> vol.Schema:
    if _gas(d):
        return _schema_fornitura_gas(d)
    return vol.Schema(
        {
            vol.Optional(CONF_STAT, description={"suggested_value": d.get(CONF_STAT)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
            vol.Optional(CONF_CONSUMO_ANNUO, description={"suggested_value": d.get(CONF_CONSUMO_ANNUO)}): _num(
                0, 1000000, "any", "kWh"
            ),
            vol.Required(CONF_TIPO_CLIENTE, default=d.get(CONF_TIPO_CLIENTE, CLIENTE_RESIDENTE)): _select(
                CONF_TIPO_CLIENTE, [CLIENTE_RESIDENTE, CLIENTE_NON_RESIDENTE, CLIENTE_ALTRI_USI]
            ),
            vol.Required(CONF_POTENZA, default=d.get(CONF_POTENZA, 3.0)): _num(0.5, 100, 0.5, "kW"),
            vol.Required(CONF_REGIONE, default=d.get(CONF_REGIONE, vol.UNDEFINED)): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[sel.SelectOptionDict(value=k, label=v) for k, v in REGIONI.items()],
                    mode=sel.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_COMUNE, description={"suggested_value": d.get(CONF_COMUNE)}): sel.TextSelector(),
        }
    )


def _schema_fornitura_gas(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_STAT, description={"suggested_value": d.get(CONF_STAT)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class=["gas", "energy"])
            ),
            vol.Optional(CONF_CONSUMO_ANNUO, description={"suggested_value": d.get(CONF_CONSUMO_ANNUO)}): _num(
                0, 1000000, "any", "Smc"
            ),
            vol.Required(CONF_TIPO_CLIENTE, default=d.get(CONF_TIPO_CLIENTE, CLIENTE_RESIDENTE)): _select(
                CONF_TIPO_CLIENTE, [CLIENTE_RESIDENTE, CLIENTE_NON_RESIDENTE, CLIENTE_ALTRI_USI]
            ),
            vol.Required(CONF_REGIONE, default=d.get(CONF_REGIONE, vol.UNDEFINED)): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[sel.SelectOptionDict(value=k, label=v) for k, v in REGIONI.items()],
                    mode=sel.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_COMUNE, description={"suggested_value": d.get(CONF_COMUNE)}): sel.TextSelector(),
        }
    )


def _schema_attuale(d: dict[str, Any]) -> vol.Schema:
    if _gas(d):
        return vol.Schema(
            {
                vol.Required(CONF_ATTUALE, default=d.get(CONF_ATTUALE, ATTUALE_FISSO)): _select(
                    CONF_ATTUALE, [ATTUALE_FISSO, ATTUALE_VARIABILE, ATTUALE_CODICE, ATTUALE_NESSUNA]
                ),
                vol.Optional(CONF_PREZZO, description={"suggested_value": d.get(CONF_PREZZO)}): _num(0, 5, "any", "€/Smc"),
                vol.Optional(CONF_QUOTA, description={"suggested_value": d.get(CONF_QUOTA)}): _num(0, 2000, "any", "€/anno"),
                vol.Optional(CONF_PSV_BOLLETTA, description={"suggested_value": d.get(CONF_PSV)}): _num(0, 1000, "any", "€/Smc"),
                vol.Optional(CONF_CODICE, description={"suggested_value": d.get(CONF_CODICE)}): sel.TextSelector(),
            }
        )
    return vol.Schema(
        {
            vol.Required(CONF_ATTUALE, default=d.get(CONF_ATTUALE, ATTUALE_FISSO)): _select(
                CONF_ATTUALE, [ATTUALE_FISSO, ATTUALE_VARIABILE, ATTUALE_CODICE, ATTUALE_NESSUNA]
            ),
            vol.Optional(CONF_PREZZO, description={"suggested_value": d.get(CONF_PREZZO)}): _num(0, 2, "any", "€/kWh"),
            vol.Optional(CONF_QUOTA, description={"suggested_value": d.get(CONF_QUOTA)}): _num(0, 2000, "any", "€/anno"),
            vol.Optional(CONF_PUN_BOLLETTA, description={"suggested_value": _pun_unico(d)}): _num(0, 1000, "any", "€/kWh"),
            vol.Optional(CONF_CODICE, description={"suggested_value": d.get(CONF_CODICE)}): sel.TextSelector(),
        }
    )


def _pun_unico(d: dict[str, Any]) -> float | None:
    """Il PUN già impostato, se è uguale per tutte le fasce."""
    valori = {d.get(CONF_PUN_F1), d.get(CONF_PUN_F2), d.get(CONF_PUN_F3)}
    return valori.pop() if len(valori) == 1 else None


def applica_pun(d: dict[str, Any]) -> dict[str, Any]:
    """Il PUN letto in bolletta diventa il PUN previsto per tutte le fasce (accetta anche €/MWh)."""
    d = dict(d)
    v = d.pop(CONF_PUN_BOLLETTA, None)
    if v:
        v = float(v)
        if v > 1.5:
            v /= 1000
        d[CONF_PUN_F1] = d[CONF_PUN_F2] = d[CONF_PUN_F3] = round(v, 5)
    return d


def applica_psv(d: dict[str, Any]) -> dict[str, Any]:
    """Il PSV letto in bolletta diventa il PSV previsto (accetta anche €/MWh)."""
    d = dict(d)
    v = d.pop(CONF_PSV_BOLLETTA, None)
    if v:
        v = float(v)
        if v > 10:
            v = v * KWH_PER_SMC / 1000
        d[CONF_PSV] = round(v, 5)
    return d


def _schema_opzioni(d: dict[str, Any]) -> vol.Schema:
    comuni = {
        vol.Required(CONF_ONLINE, default=d.get(CONF_ONLINE, True)): sel.BooleanSelector(),
        vol.Required(CONF_SDD, default=d.get(CONF_SDD, True)): sel.BooleanSelector(),
        vol.Required(CONF_DUAL, default=d.get(CONF_DUAL, False)): sel.BooleanSelector(),
        vol.Required(CONF_SOGLIA, default=d.get(CONF_SOGLIA, DEFAULT_SOGLIA)): _num(0, 2000, 1, "€/anno"),
        vol.Required(CONF_NOTIFICA, default=d.get(CONF_NOTIFICA, True)): sel.BooleanSelector(),
        vol.Required(CONF_ORE, default=d.get(CONF_ORE, DEFAULT_ORE)): _num(6, 48, 1, "h"),
    }
    if _gas(d):
        return vol.Schema(
            {
                vol.Optional(CONF_PSV_ENTITA, description={"suggested_value": d.get(CONF_PSV_ENTITA)}): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PSV, default=d.get(CONF_PSV, DEFAULT_PSV)): _num(0, 5, "any", "€/Smc"),
                **comuni,
            }
        )
    return vol.Schema(
        {
            vol.Optional(CONF_PUN_ENTITA, description={"suggested_value": d.get(CONF_PUN_ENTITA)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_PUN_F1, default=d.get(CONF_PUN_F1, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            vol.Required(CONF_PUN_F2, default=d.get(CONF_PUN_F2, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            vol.Required(CONF_PUN_F3, default=d.get(CONF_PUN_F3, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            **comuni,
        }
    )


def _errori_attuale(d: dict[str, Any]) -> dict[str, str]:
    modo = d.get(CONF_ATTUALE)
    if modo in (ATTUALE_FISSO, ATTUALE_VARIABILE) and d.get(CONF_PREZZO) is None:
        return {CONF_PREZZO: "prezzo_mancante"}
    if modo == ATTUALE_CODICE and not (d.get(CONF_CODICE) or "").strip():
        return {CONF_CODICE: "codice_mancante"}
    return {}


def _errori_comune(d: dict[str, Any]) -> dict[str, str]:
    c = (d.get(CONF_COMUNE) or "").strip()
    if c and not (c.isdigit() and len(c) == 6):
        return {CONF_COMUNE: "comune_non_valido"}
    if not d.get(CONF_STAT) and not d.get(CONF_CONSUMO_ANNUO):
        return {"base": "consumo_mancante"}
    return {}


def _applica_indice(d: dict[str, Any]) -> dict[str, Any]:
    return applica_psv(d) if CONF_PSV_BOLLETTA in d else applica_pun(d)


class OfferteLuceConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._dati: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=[FORNITURA_LUCE, FORNITURA_GAS])

    async def async_step_luce(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._fornitura(FORNITURA_LUCE, user_input)

    async def async_step_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._fornitura(FORNITURA_GAS, user_input)

    async def _fornitura(self, tipo: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        self._dati[CONF_FORNITURA] = tipo
        if user_input is not None:
            errori = _errori_comune(user_input)
            if not errori:
                chiave = user_input.get(CONF_STAT) or "manuale"
                await self.async_set_unique_id(chiave if tipo == FORNITURA_LUCE else f"gas_{chiave}")
                self._abort_if_unique_id_configured()
                self._dati.update(user_input)
                return await self.async_step_attuale()
            dati = {**user_input, CONF_FORNITURA: tipo}
        else:
            stat, prezzo = await _da_energia(self.hass, tipo == FORNITURA_GAS)
            dati = {CONF_FORNITURA: tipo, **({CONF_STAT: stat} if stat else {})}
            if prezzo:
                self._dati[CONF_PREZZO] = prezzo
        return self.async_show_form(step_id=tipo, data_schema=_schema_fornitura(dati), errors=errori)

    async def async_step_attuale(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        gas = _gas(self._dati)
        if user_input is not None:
            errori = _errori_attuale(user_input)
            if not errori:
                self._dati.pop(CONF_PREZZO, None)
                self._dati.update(_applica_indice(user_input))
                return self.async_create_entry(title="Offerte Gas" if gas else "Offerte Luce", data=self._dati)
        return self.async_show_form(
            step_id="attuale_gas" if gas else "attuale",
            data_schema=_schema_attuale({**self._dati, **(user_input or {})}),
            errors=errori,
        )

    async def async_step_attuale_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_attuale(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return OfferteLuceOptionsFlow()


class OfferteLuceOptionsFlow(OptionsFlow):
    def __init__(self) -> None:
        self._nuove: dict[str, Any] = {}

    @property
    def _attuali(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def _gas(self) -> bool:
        return _gas(self._attuali)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._gas:
            return self.async_show_menu(step_id="init_gas", menu_options=["fornitura_gas", "attuale_gas", "calcolo_gas"])
        return self.async_show_menu(step_id="init", menu_options=["fornitura", "attuale", "calcolo"])

    async def async_step_fornitura_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_fornitura(user_input)

    async def async_step_attuale_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_attuale(user_input)

    async def async_step_calcolo_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_calcolo(user_input)

    def _passo(self, nome: str) -> str:
        return f"{nome}_gas" if self._gas else nome

    async def _salva(self, user_input: dict[str, Any], vuoti: tuple[str, ...]) -> ConfigFlowResult:
        nuove = {**self.config_entry.options, **user_input}
        for k in vuoti:  # i campi facoltativi svuotati non arrivano nel modulo
            if k not in user_input:
                # None e non pop: il valore iniziale sta nei dati dell'entry e tornerebbe fuori
                nuove[k] = None
        return self.async_create_entry(data=nuove)

    async def async_step_fornitura(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_comune(user_input)
            if not errori:
                return await self._salva(user_input, (CONF_COMUNE, CONF_STAT, CONF_CONSUMO_ANNUO))
        return self.async_show_form(
            step_id=self._passo("fornitura"),
            data_schema=_schema_fornitura({**self._attuali, **(user_input or {})}),
            errors=errori,
        )

    async def async_step_attuale(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_attuale(user_input)
            if not errori:
                return await self._salva(_applica_indice(user_input), (CONF_PREZZO, CONF_QUOTA, CONF_CODICE))
        return self.async_show_form(
            step_id=self._passo("attuale"),
            data_schema=_schema_attuale({**self._attuali, **(user_input or {})}),
            errors=errori,
        )

    async def async_step_calcolo(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._salva(user_input, (CONF_PSV_ENTITA,) if self._gas else (CONF_PUN_ENTITA,))
        return self.async_show_form(step_id=self._passo("calcolo"), data_schema=_schema_opzioni(self._attuali))

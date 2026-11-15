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
    DEFAULT_PUN,
    DEFAULT_SOGLIA,
    DOMAIN,
    REGIONI,
)


async def _da_energia(hass: HomeAssistant) -> tuple[str | None, float | None]:
    """Sensore di prelievo dalla rete e prezzo fisso impostati nella dashboard Energia, se ci sono."""
    try:
        from homeassistant.components.energy.data import async_get_manager

        dati = (await async_get_manager(hass)).data or {}
    except Exception:  # noqa: BLE001 - la dashboard Energia può non essere configurata
        return None, None
    for src in dati.get("energy_sources", []):
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


def _schema_fornitura(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_STAT, default=d.get(CONF_STAT, vol.UNDEFINED)): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class="energy")
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


def _schema_attuale(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ATTUALE, default=d.get(CONF_ATTUALE, ATTUALE_FISSO)): _select(
                CONF_ATTUALE, [ATTUALE_FISSO, ATTUALE_VARIABILE, ATTUALE_CODICE, ATTUALE_NESSUNA]
            ),
            vol.Optional(CONF_PREZZO, description={"suggested_value": d.get(CONF_PREZZO)}): _num(0, 2, "any", "€/kWh"),
            vol.Optional(CONF_QUOTA, description={"suggested_value": d.get(CONF_QUOTA)}): _num(0, 2000, "any", "€/anno"),
            vol.Optional(CONF_CODICE, description={"suggested_value": d.get(CONF_CODICE)}): sel.TextSelector(),
        }
    )


def _schema_opzioni(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_PUN_ENTITA, description={"suggested_value": d.get(CONF_PUN_ENTITA)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_PUN_F1, default=d.get(CONF_PUN_F1, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            vol.Required(CONF_PUN_F2, default=d.get(CONF_PUN_F2, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            vol.Required(CONF_PUN_F3, default=d.get(CONF_PUN_F3, DEFAULT_PUN)): _num(0, 2, "any", "€/kWh"),
            vol.Required(CONF_ONLINE, default=d.get(CONF_ONLINE, True)): sel.BooleanSelector(),
            vol.Required(CONF_SDD, default=d.get(CONF_SDD, True)): sel.BooleanSelector(),
            vol.Required(CONF_DUAL, default=d.get(CONF_DUAL, False)): sel.BooleanSelector(),
            vol.Required(CONF_SOGLIA, default=d.get(CONF_SOGLIA, DEFAULT_SOGLIA)): _num(0, 2000, 1, "€/anno"),
            vol.Required(CONF_ORE, default=d.get(CONF_ORE, DEFAULT_ORE)): _num(6, 48, 1, "h"),
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
    return {}


class OfferteLuceConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._dati: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_comune(user_input)
            if not errori:
                await self.async_set_unique_id(user_input[CONF_STAT])
                self._abort_if_unique_id_configured()
                self._dati.update(user_input)
                return await self.async_step_attuale()
            dati = user_input
        else:
            stat, prezzo = await _da_energia(self.hass)
            dati = {CONF_STAT: stat} if stat else {}
            if prezzo:
                self._dati[CONF_PREZZO] = prezzo
        return self.async_show_form(step_id="user", data_schema=_schema_fornitura(dati), errors=errori)

    async def async_step_attuale(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_attuale(user_input)
            if not errori:
                self._dati.pop(CONF_PREZZO, None)
                self._dati.update(user_input)
                return self.async_create_entry(title="Offerte Luce", data=self._dati)
        return self.async_show_form(
            step_id="attuale", data_schema=_schema_attuale(user_input or self._dati), errors=errori
        )

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

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["fornitura", "attuale", "calcolo"])

    async def _salva(self, user_input: dict[str, Any], vuoti: tuple[str, ...]) -> ConfigFlowResult:
        nuove = {**self.config_entry.options, **user_input}
        for k in vuoti:  # i campi facoltativi svuotati non arrivano nel modulo
            if k not in user_input:
                nuove.pop(k, None)
        return self.async_create_entry(data=nuove)

    async def async_step_fornitura(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_comune(user_input)
            if not errori:
                return await self._salva(user_input, (CONF_COMUNE,))
        return self.async_show_form(
            step_id="fornitura", data_schema=_schema_fornitura(user_input or self._attuali), errors=errori
        )

    async def async_step_attuale(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            errori = _errori_attuale(user_input)
            if not errori:
                return await self._salva(user_input, (CONF_PREZZO, CONF_QUOTA, CONF_CODICE))
        return self.async_show_form(
            step_id="attuale", data_schema=_schema_attuale(user_input or self._attuali), errors=errori
        )

    async def async_step_calcolo(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._salva(user_input, (CONF_PUN_ENTITA,))
        return self.async_show_form(step_id="calcolo", data_schema=_schema_opzioni(self._attuali))

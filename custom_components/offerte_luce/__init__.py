"""Offerte Luce: confronta le offerte del Portale Offerte ARERA con i tuoi consumi reali."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OfferteCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type OfferteConfigEntry = ConfigEntry[OfferteCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OfferteConfigEntry) -> bool:
    coordinator = OfferteCoordinator(hass, entry)
    await coordinator.async_carica_stato()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_ricarica))
    return True


async def _ricarica(hass: HomeAssistant, entry: OfferteConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OfferteConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

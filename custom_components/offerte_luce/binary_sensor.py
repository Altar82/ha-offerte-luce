"""Sensore 'conviene cambiare'."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OfferteConfigEntry
from .entity import OfferteEntity


async def async_setup_entry(hass: HomeAssistant, entry: OfferteConfigEntry, add: AddEntitiesCallback) -> None:
    add([ConvieneCambiare(entry.runtime_data, "conviene_cambiare")])


class ConvieneCambiare(OfferteEntity, BinarySensorEntity):
    _attr_icon = "mdi:swap-horizontal-circle-outline"

    @property
    def is_on(self) -> bool | None:
        r = self.coordinator.data
        return None if r.risparmio is None else r.conviene

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        r = self.coordinator.data
        m = r.migliore or {}
        return {
            "soglia": r.soglia,
            "risparmio_annuo": r.risparmio,
            "offerta": m.get("nome"),
            "venditore": m.get("venditore"),
            "url": m.get("url"),
        }

"""Entità base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .arera import FONTE
from .const import DOMAIN
from .coordinator import OfferteCoordinator


class OfferteEntity(CoordinatorEntity[OfferteCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = FONTE

    def __init__(self, coordinator: OfferteCoordinator, chiave: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{chiave}"
        self._attr_translation_key = chiave
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Portale Offerte ARERA",
            model="Confronto offerte gas" if coordinator.gas else "Confronto offerte luce",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.ilportaleofferte.it",
        )

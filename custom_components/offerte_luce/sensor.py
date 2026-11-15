"""Sensori di Offerte Luce."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OfferteConfigEntry
from .coordinator import Risultato
from .entity import OfferteEntity

EURO_ANNO = "€/anno"


def _migliore_attr(r: Risultato) -> dict[str, Any]:
    m = dict(r.migliore or {})
    m["costo_annuo_iva_inclusa"] = round(m.get("costo_annuo", 0) * (1 + r.iva), 2)
    m["classifica"] = [
        {k: x[k] for k in ("nome", "venditore", "tipo", "costo_annuo", "url")} for x in r.migliori
    ]
    m["data_elenco_offerte"] = r.data_file
    m["pun_usato"] = r.pun
    m["note"] = r.note
    return m


@dataclass(frozen=True, kw_only=True)
class Descrizione(SensorEntityDescription):
    valore: Callable[[Risultato], Any]
    attributi: Callable[[Risultato], dict[str, Any]] | None = None


SENSORI = (
    Descrizione(
        key="migliore_offerta",
        icon="mdi:trophy-outline",
        valore=lambda r: (r.migliore or {}).get("nome"),
        attributi=_migliore_attr,
    ),
    Descrizione(
        key="costo_migliore_offerta",
        icon="mdi:cash-check",
        native_unit_of_measurement=EURO_ANNO,
        suggested_display_precision=0,
        valore=lambda r: (r.migliore or {}).get("costo_annuo"),
    ),
    Descrizione(
        key="costo_offerta_attuale",
        icon="mdi:cash",
        native_unit_of_measurement=EURO_ANNO,
        suggested_display_precision=0,
        valore=lambda r: r.costo_attuale,
        attributi=lambda r: dict(r.attuale or {}),
    ),
    Descrizione(
        key="risparmio_annuo",
        icon="mdi:piggy-bank-outline",
        native_unit_of_measurement=EURO_ANNO,
        suggested_display_precision=0,
        valore=lambda r: r.risparmio,
        attributi=lambda r: {
            "risparmio_iva_inclusa": round(r.risparmio * (1 + r.iva), 2) if r.risparmio is not None else None
        },
    ),
    Descrizione(
        key="consumo_annuo",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        valore=lambda r: round(sum(r.kwh.values()), 1),
        attributi=lambda r: {
            "F1": r.kwh["F1"],
            "F2": r.kwh["F2"],
            "F3": r.kwh["F3"],
            "giorni_di_dati": r.giorni_dati,
        },
    ),
    Descrizione(
        key="offerte_confrontate",
        icon="mdi:format-list-numbered",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        valore=lambda r: r.confrontate,
        attributi=lambda r: {"escluse": r.esclusi, "data_elenco_offerte": r.data_file, "pun_fonte": r.pun_fonte},
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: OfferteConfigEntry, add: AddEntitiesCallback) -> None:
    add(OfferteSensor(entry.runtime_data, d) for d in SENSORI)


class OfferteSensor(OfferteEntity, SensorEntity):
    entity_description: Descrizione

    def __init__(self, coordinator, descrizione: Descrizione) -> None:
        super().__init__(coordinator, descrizione.key)
        self.entity_description = descrizione

    @property
    def native_value(self) -> Any:
        return self.entity_description.valore(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        f = self.entity_description.attributi
        return f(self.coordinator.data) if f else None

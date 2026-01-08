"""Shared entity base classes for Heat Pump Predictor."""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:  # pragma: no cover
    from .coordinator import HeatPumpCoordinator


class HeatPumpBaseEntity(CoordinatorEntity["HeatPumpCoordinator"]):
    """Common base for all entities in the integration."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: "HeatPumpCoordinator",
        unique_id: str,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the entity base."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id}"
        self._attr_device_info = coordinator.device_info
        if translation_key:
            self._attr_translation_key = translation_key
        if translation_placeholders:
            self._attr_translation_placeholders = dict(translation_placeholders)

    @property
    def available(self) -> bool:
        """Return entity availability based on coordinator state."""
        return bool(self.coordinator.last_update_success)

    @property
    def device_info(self) -> dict:
        """Return device info for registry grouping."""
        return self._attr_device_info or {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
        }
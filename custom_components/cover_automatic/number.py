"""Number platform for CoverAutomatic: global comfort settings of profiles A and B."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import i18n
from .const import DOMAIN
from .coordinator import CoverAutomaticCoordinator
from .storage import settings_cross_error

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import CoverAutomaticConfigEntry


@dataclass(frozen=True, slots=True)
class _ComfortNumber:
    """One comfort setting exposed as a number entity."""

    key: str  # storage setting
    translation_key: str
    minimum: float
    maximum: float
    temperature: bool  # absolute temperature (False: a temperature difference)


_NUMBERS = (
    _ComfortNumber("comfort_temp_min", "comfort_temp_min_a", -50, 60, True),
    _ComfortNumber("comfort_temp_max", "comfort_temp_max_a", -50, 60, True),
    _ComfortNumber("comfort_hysteresis", "comfort_hysteresis_a", 0.1, 5, False),
    _ComfortNumber("comfort_temp_min_b", "comfort_temp_min_b", -50, 60, True),
    _ComfortNumber("comfort_temp_max_b", "comfort_temp_max_b", -50, 60, True),
    _ComfortNumber("comfort_hysteresis_b", "comfort_hysteresis_b", 0.1, 5, False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoverAutomaticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the comfort number entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        CoverAutomaticComfortNumber(coordinator, entry.entry_id, description)
        for description in _NUMBERS
    )


class CoverAutomaticComfortNumber(CoordinatorEntity[CoverAutomaticCoordinator], NumberEntity):
    """Global comfort band or hysteresis of a comfort profile."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.1

    def __init__(
        self,
        coordinator: CoverAutomaticCoordinator,
        entry_id: str,
        description: _ComfortNumber,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._key = description.key
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{DOMAIN}_{description.translation_key}"
        self._attr_native_min_value = description.minimum
        self._attr_native_max_value = description.maximum
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        if description.temperature:
            # A hysteresis is a difference: no unit conversion for it
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "CoverAutomatic",
            "manufacturer": "CoverAutomatic",
            "model": i18n.text(coordinator.hass, "model_controller"),
        }

    @property
    def native_value(self) -> float:
        """Current value of the setting."""
        return float(getattr(self.coordinator.storage, self._key))

    async def async_set_native_value(self, value: float) -> None:
        """Store a new value; the cold setpoint must stay below the hot one."""
        storage = self.coordinator.storage
        value = round(float(value), 2)

        def _resulting(key: str) -> float:
            return value if key == self._key else getattr(storage, key)

        if settings_cross_error(_resulting, (self._key,)):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_comfort_range",
            )
        setattr(storage, self._key, value)
        # A slider or an automation can send many values in a row: one write
        storage.schedule_save()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

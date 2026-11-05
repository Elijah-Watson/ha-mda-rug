"""Speed of the current scene. Choosing a scene moves it to that scene's own speed."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MdaRugEffectSpeed(entry)])


class MdaRugEffectSpeed(RestoreNumber):
    _attr_has_entity_name = True
    _attr_translation_key = "effect_speed"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, entry):
        self._client = entry.runtime_data
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_effect_speed"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, address)})

    @property
    def native_value(self):
        return self._client.speed

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_number_data()
        if previous and previous.native_value is not None:
            if 1 <= previous.native_value <= 100:
                self._client.speed = int(previous.native_value)
        self._client.on_speed_stored = self.async_write_ha_state
        self.async_on_remove(self._clear_speed_listener)

    def _clear_speed_listener(self):
        self._client.on_speed_stored = None

    async def async_set_native_value(self, value):
        speed = int(value)
        # Keep the old value if the rug refuses, so the slider never claims a failed speed.
        if self._client.on_speed_change is not None:
            await self._client.on_speed_change(speed)
        self._client.speed = speed
        self.async_write_ha_state()

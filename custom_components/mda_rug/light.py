"""One HA light with power, HS color, brightness, and three scene palettes."""

from __future__ import annotations

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from . import protocol
from .client import RugError
from .const import CONF_SPEED, DEFAULT_SPEED, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MdaRugLight(entry)])


class MdaRugLight(LightEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True  # Color/brightness are last requested values.
    _attr_color_mode = ColorMode.HS
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, entry):
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_effect_list = ["Solid", *protocol.SCENES]
        self._entry = entry
        self._client = entry.runtime_data
        self._address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = self._address
        self._attr_is_on = self._client.state.on
        self._attr_available = True
        self._attr_hs_color = None
        self._attr_brightness = None
        self._attr_effect = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer="MDA Rugs",
            model="LED rug (0x00AD)",
            name=entry.title,
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous:
            # Restore requested values, never override the freshly queried power state.
            attrs = previous.attributes
            hs = attrs.get(ATTR_HS_COLOR)
            if isinstance(hs, (list, tuple)) and len(hs) == 2:
                try:
                    protocol.color(hs[0], hs[1], 100)
                    self._attr_hs_color = tuple(hs)
                except (TypeError, ValueError):
                    pass
            value = attrs.get(ATTR_BRIGHTNESS)
            if isinstance(value, int) and 1 <= value <= 255:
                self._attr_brightness = value
            effect = attrs.get(ATTR_EFFECT)
            if effect in self._attr_effect_list:
                expected = 110 if effect == "Solid" else protocol.SCENES[effect][0]
                current = self._client.state
                if current.mode == 0x25 and current.mode_id == expected:
                    self._attr_effect = effect
                else:
                    self._attr_hs_color = None
                    self._attr_brightness = None
        self.async_on_remove(
            bluetooth.async_register_callback(
                self.hass,
                self._advertisement,
                {"address": self._address, "connectable": True},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )
        self.async_on_remove(
            bluetooth.async_track_unavailable(
                self.hass,
                self._unavailable,
                self._address,
                connectable=True,
            )
        )

    @callback
    def _advertisement(self, info, change):
        if not protocol.matches(info.service_data, self._address):
            return
        self._attr_available = True
        data = info.manufacturer_data.get(0x5A00, b"")
        if len(data) == 27 and data[0] == 0x80 and data[1] in (0x23, 0x24):
            self._attr_is_on = data[1] == 0x23
            # If another controller selects a different mode, discard our stale label/color.
            effect = self._attr_effect
            expected = (
                110
                if effect == "Solid"
                else protocol.SCENES[effect][0]
                if effect in protocol.SCENES
                else None
            )
            if expected is not None and (data[2] != 0x25 or data[3] != expected):
                self._attr_effect = None
                self._attr_hs_color = None
                self._attr_brightness = None
        self.async_write_ha_state()

    @callback
    def _unavailable(self, info):
        self._attr_available = False
        self.async_write_ha_state()

    async def _execute(self, commands):
        try:
            state = await self._client.execute(commands)
        except (BleakError, RugError, TimeoutError, OSError) as exc:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"MDA rug: {exc}") from exc
        self._attr_available = True
        self._attr_is_on = state.on

    async def async_turn_on(self, **kwargs):
        value = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)
        if value == 0:
            await self.async_turn_off()
            return
        percent = max(1, round(protocol.bounded(value, 1, 255) * 100 / 255))
        effect = kwargs.get(ATTR_EFFECT)
        hs = kwargs.get(ATTR_HS_COLOR)
        if effect is not None and effect not in self._attr_effect_list:
            raise HomeAssistantError("Unknown MDA rug effect")
        if effect not in (None, "Solid") and hs is not None:
            raise HomeAssistantError("Choose either a scene or a solid color in one action")
        commands = [protocol.power(True)]
        requested_effect = self._attr_effect
        requested_hs = self._attr_hs_color
        if effect in protocol.SCENES:
            speed = self._entry.options.get(CONF_SPEED, DEFAULT_SPEED)
            commands += [protocol.scene(effect, speed), protocol.brightness(percent)]
            requested_effect, requested_hs = effect, None
        elif hs is not None or effect == "Solid":
            requested_hs = tuple(hs or self._attr_hs_color or (0, 0))
            commands.append(protocol.color(*requested_hs, percent))
            requested_effect = "Solid"
        elif ATTR_BRIGHTNESS in kwargs:
            commands.append(protocol.brightness(percent))
        await self._execute(commands)
        self._attr_effect = requested_effect
        self._attr_hs_color = requested_hs
        if len(commands) > 1:
            self._attr_brightness = value
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._execute([protocol.power(False)])
        self.async_write_ha_state()

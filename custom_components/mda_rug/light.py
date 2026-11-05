"""One HA light with power, HS color, brightness, and the captured scene palettes."""

from __future__ import annotations

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    EFFECT_OFF,
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
from .const import CONF_COLOR_ORDER, DEFAULT_COLOR_ORDER, DOMAIN

PARALLEL_UPDATES = 1
WHITE = (0, 0)


def _percent(value: int) -> int:
    return max(1, round(protocol.bounded(value, 1, 255) * 100 / 255))


def _mode_id(effect: str | None) -> int | None:
    """The status reply's mode ID for a selection, or None when nothing is selected."""
    if effect == EFFECT_OFF:
        return protocol.SOLID_MODE_ID
    if effect in protocol.SCENES:
        return protocol.SCENES[effect][0]
    return None


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MdaRugLight(entry)])


class MdaRugLight(LightEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "rug"
    _attr_should_poll = False
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, entry):
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_effect_list = [EFFECT_OFF, *protocol.SCENES]
        self._entry = entry
        self._client = entry.runtime_data
        self._address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = self._address
        self._attr_is_on = self._client.state.on
        self._attr_available = True
        self._attr_hs_color = None
        self._attr_brightness = None
        self._attr_effect = None
        self._attr_extra_state_attributes = {"color_correction": self._color_order}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer="MDA Rugs",
            model="LED rug (0x00AD)",
            name=entry.title,
        )

    @property
    def _color_order(self) -> str:
        return self._entry.options.get(CONF_COLOR_ORDER, DEFAULT_COLOR_ORDER)

    @property
    def color_mode(self) -> ColorMode:
        # A scene owns its colors, so only brightness can be adjusted while one runs.
        return ColorMode.BRIGHTNESS if self._attr_effect in protocol.SCENES else ColorMode.HS

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if (
            previous
            and previous.attributes.get("color_correction")
            == self._attr_extra_state_attributes["color_correction"]
        ):
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
            current = self._client.state
            if (
                effect in self._attr_effect_list
                and current.mode == 0x25
                and current.mode_id == _mode_id(effect)
            ):
                self._attr_effect = effect
            else:
                self._attr_hs_color = None
                self._attr_brightness = None
        self._client.on_speed_change = self.async_apply_speed
        self.async_on_remove(self._clear_speed_listener)
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
    def _clear_speed_listener(self):
        self._client.on_speed_change = None

    @callback
    def _advertisement(self, info, change):
        if not protocol.matches(info.service_data, self._address):
            return
        self._attr_available = True
        data = info.manufacturer_data.get(0x5A00, b"")
        if len(data) == 27 and data[0] == 0x80 and data[1] in (0x23, 0x24):
            self._attr_is_on = data[1] == 0x23
            # If another controller selects a different mode, discard our stale label/color.
            expected = _mode_id(self._attr_effect)
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
            # A failed command says nothing about reachability: advertisements decide that.
            raise HomeAssistantError(f"MDA rug: {exc}") from exc
        self._attr_available = True
        self._attr_is_on = state.on
        return state

    def _scene(self, effect: str, percent: int, speed: int | None = None) -> bytes:
        return protocol.scene(
            effect, self._client.speed if speed is None else speed, self._color_order, percent
        )

    async def async_turn_on(self, **kwargs):
        value = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)
        if value == 0:
            await self.async_turn_off()
            return
        percent = _percent(value)
        effect = kwargs.get(ATTR_EFFECT)
        hs = kwargs.get(ATTR_HS_COLOR)
        if effect is not None and effect not in self._attr_effect_list:
            raise HomeAssistantError("Unknown MDA rug effect")
        if effect in protocol.SCENES and hs is not None:
            raise HomeAssistantError("Choose either a scene or a solid color in one action")
        commands = [protocol.power(True)]
        requested_effect = self._attr_effect
        requested_hs = self._attr_hs_color
        scene_speed = None
        if effect in protocol.SCENES:
            scene_speed = protocol.default_speed(effect)
            commands.append(self._scene(effect, percent, scene_speed))
            requested_effect, requested_hs = effect, None
        elif hs is not None or effect == EFFECT_OFF:
            requested_hs = tuple(hs or self._attr_hs_color or WHITE)
            commands.append(protocol.color(*requested_hs, percent, self._color_order))
            requested_effect = EFFECT_OFF
        elif ATTR_BRIGHTNESS in kwargs:
            if requested_effect in protocol.SCENES:
                commands.append(self._scene(requested_effect, percent))
            else:
                # Dimming can only resend a color, so an unknown selection starts from white.
                requested_hs = requested_hs or WHITE
                commands.append(protocol.color(*requested_hs, percent, self._color_order))
                requested_effect = EFFECT_OFF
        state = await self._execute(commands)
        if scene_speed is not None:
            self._client.speed = scene_speed
            if self._client.on_speed_stored is not None:
                self._client.on_speed_stored()
        if len(commands) == 1 and requested_effect is not None:
            if state.mode != 0x25 or state.mode_id != _mode_id(requested_effect):
                requested_effect = requested_hs = None
                self._attr_brightness = None
        self._attr_effect = requested_effect
        self._attr_hs_color = requested_hs
        if len(commands) > 1:
            self._attr_brightness = value
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._execute([protocol.power(False)])
        self.async_write_ha_state()

    async def async_apply_speed(self, speed: int) -> None:
        """Resend a running scene at the new speed. The next scene starts at its own speed."""
        if not self._attr_is_on or self._attr_effect not in protocol.SCENES:
            return
        percent = _percent(self._attr_brightness or 255)
        await self._execute([self._scene(self._attr_effect, percent, speed)])
        self.async_write_ha_state()

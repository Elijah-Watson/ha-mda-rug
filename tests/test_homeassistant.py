"""Exercise the HA light and offline setup against real HA classes in Linux CI."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.light import EFFECT_OFF, ColorMode  # noqa: E402
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError  # noqa: E402

from custom_components.mda_rug import async_setup_entry, light, number, protocol  # noqa: E402
from custom_components.mda_rug.client import RugError  # noqa: E402


def make_entry():
    return SimpleNamespace(
        data={"address": "AA:BB:CC:DD:EE:FF"},
        title="Test rug",
        options={},
        runtime_data=SimpleNamespace(
            state=protocol.State(False, 0x25, 110, 30), speed=50, on_speed_change=None
        ),
    )


@pytest.fixture
def rug():
    entity = light.MdaRugLight(make_entry())
    entity._execute = AsyncMock()
    entity.async_write_ha_state = Mock()
    return entity


async def test_solid_dimming_resends_corrected_color(rug):
    await rug.async_turn_on(hs_color=(0, 100), brightness=77)
    assert rug._execute.call_args.args[0][-1] == protocol.color(0, 100, 30, "BGR")
    await rug.async_turn_on(brightness=26)
    commands = rug._execute.call_args.args[0]
    assert commands == [protocol.power(True), protocol.color(0, 100, 10, "BGR")]
    assert rug.hs_color == (0, 100)
    assert rug.brightness == 26


async def test_scene_dimming_preserves_selected_palette(rug):
    await rug.async_turn_on(effect="Northern Lights", brightness=26)
    await rug.async_turn_on(brightness=179)
    assert rug._execute.call_args.args[0][-1] == protocol.scene("Northern Lights", 50, "BGR", 70)
    assert rug.effect == "Northern Lights"


async def test_unknown_selection_dimming_starts_from_white(rug):
    await rug.async_turn_on(brightness=128)
    assert rug._execute.call_args.args[0][-1] == protocol.color(0, 0, 50, "BGR")
    assert rug.effect == EFFECT_OFF
    assert rug.hs_color == (0, 0)


def test_effect_list_follows_ha_convention(rug):
    assert rug.effect_list[0] == EFFECT_OFF
    assert "Solid" not in rug.effect_list
    assert len(rug.effect_list) == 47


def test_power_is_measured_not_assumed(rug):
    assert rug.assumed_state is False


async def test_color_mode_follows_the_selection(rug):
    await rug.async_turn_on(effect="Game")
    assert rug.color_mode == ColorMode.BRIGHTNESS
    await rug.async_turn_on(hs_color=(120, 100))
    assert rug.color_mode == ColorMode.HS
    assert rug.effect == EFFECT_OFF


@pytest.mark.parametrize(
    "effect,hs,expected",
    [("Game", None, ColorMode.BRIGHTNESS), (EFFECT_OFF, (120, 100), ColorMode.HS)],
)
def test_ha_accepts_the_reported_color_mode(rug, effect, hs, expected):
    # state_attributes runs HA's own check that color_mode fits supported_color_modes.
    rug._attr_is_on = True
    rug._attr_effect = effect
    rug._attr_hs_color = hs
    rug._attr_brightness = 128
    attributes = rug.state_attributes
    assert attributes["color_mode"] == expected
    assert attributes["effect"] == effect
    assert attributes["brightness"] == 128


async def test_effect_off_returns_to_solid(rug):
    await rug.async_turn_on(hs_color=(120, 100))
    await rug.async_turn_on(effect="Game")
    await rug.async_turn_on(effect=EFFECT_OFF)
    assert rug._execute.call_args.args[0][-1] == protocol.color(0, 0, 100, "BGR")
    assert rug.effect == EFFECT_OFF


async def test_scene_uses_the_shared_speed(rug):
    rug._client.speed = 35
    await rug.async_turn_on(effect="Game", brightness=255)
    assert rug._execute.call_args.args[0][-1] == protocol.scene("Game", 35, "BGR", 100)


async def test_scene_and_color_together_are_refused(rug):
    with pytest.raises(HomeAssistantError, match="either a scene or a solid color"):
        await rug.async_turn_on(effect="Game", hs_color=(0, 100))
    rug._execute.assert_not_called()


async def test_speed_change_resends_a_running_scene(rug):
    rug._execute = AsyncMock(return_value=protocol.State(True, 0x25, 1, 70))
    rug._attr_is_on = True
    await rug.async_turn_on(effect="Game", brightness=128)
    await rug.async_apply_speed(70)
    assert rug._execute.call_args.args[0] == [protocol.scene("Game", 70, "BGR", 50)]


@pytest.mark.parametrize("on,effect", [(False, "Game"), (True, EFFECT_OFF), (True, None)])
async def test_speed_change_sends_nothing_without_a_running_scene(rug, on, effect):
    rug._attr_is_on = on
    rug._attr_effect = effect
    await rug.async_apply_speed(70)
    rug._execute.assert_not_called()


async def test_failed_command_keeps_the_light_available():
    entry = make_entry()
    entry.runtime_data.execute = AsyncMock(side_effect=RugError("Refused"))
    entity = light.MdaRugLight(entry)
    entity.async_write_ha_state = Mock()
    with pytest.raises(HomeAssistantError, match="Refused"):
        await entity.async_turn_on(hs_color=(120, 100))
    assert entity.available is True


def make_speed(on_change=None):
    entry = make_entry()
    entry.runtime_data.on_speed_change = on_change
    entity = number.MdaRugEffectSpeed(entry)
    entity.async_write_ha_state = Mock()
    return entity


def test_speed_is_a_config_entity_on_the_rug_device():
    entity = make_speed()
    assert entity.entity_category == "config"
    assert entity.unique_id == "AA:BB:CC:DD:EE:FF_effect_speed"
    assert entity.native_value == 50


async def test_speed_applies_then_stores():
    change = AsyncMock()
    entity = make_speed(change)
    await entity.async_set_native_value(70.0)
    change.assert_awaited_once_with(70)
    assert entity.native_value == 70


async def test_refused_speed_keeps_the_old_value():
    entity = make_speed(AsyncMock(side_effect=HomeAssistantError("Refused")))
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(70.0)
    assert entity.native_value == 50


async def test_zero_brightness_is_power_off(rug):
    await rug.async_turn_on(brightness=0)
    rug._execute.assert_awaited_once_with([protocol.power(False)])


async def test_failed_write_does_not_claim_requested_state(rug):
    rug._execute.side_effect = HomeAssistantError("Disconnected")
    with pytest.raises(HomeAssistantError):
        await rug.async_turn_on(hs_color=(120, 100), brightness=77)
    assert rug.hs_color is None
    assert rug.brightness is None
    assert rug.effect is None


async def test_missing_adapter_retries_without_creating_client():
    with (
        patch("custom_components.mda_rug.bluetooth.async_last_service_info", return_value=None),
        patch("custom_components.mda_rug.RugClient") as client,
        pytest.raises(ConfigEntryNotReady, match="No connectable Bluetooth adapter"),
    ):
        await async_setup_entry(Mock(), SimpleNamespace(data={"address": "AA:BB:CC:DD:EE:FF"}))
    client.assert_not_called()

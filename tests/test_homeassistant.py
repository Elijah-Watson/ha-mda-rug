"""Exercise the HA light and offline setup against real HA classes in Linux CI."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError  # noqa: E402

from custom_components.mda_rug import async_setup_entry, light, protocol  # noqa: E402


@pytest.fixture
def rug():
    entry = SimpleNamespace(
        data={"address": "AA:BB:CC:DD:EE:FF"},
        title="Test rug",
        options={},
        runtime_data=SimpleNamespace(state=protocol.State(False, 0x25, 110, 30)),
    )
    entity = light.MdaRugLight(entry)
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


async def test_unknown_selection_dimming_fails_before_writing(rug):
    with pytest.raises(HomeAssistantError, match="Select a color or scene"):
        await rug.async_turn_on(brightness=100)
    rug._execute.assert_not_called()


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

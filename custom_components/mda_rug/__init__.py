"""Local Bluetooth control for MDA LED rugs."""

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import RugClient, RugError
from .const import CONF_SPEED, DEFAULT_SPEED
from .protocol import matches

PLATFORMS = [Platform.LIGHT, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS]
    info = bluetooth.async_last_service_info(hass, address, connectable=True)
    if info is None:
        raise ConfigEntryNotReady("No connectable Bluetooth adapter sees the rug yet")
    if not matches(info.service_data, address):
        raise ConfigEntryNotReady("Waiting for a matching MDA 0x00AD advertisement")
    client = RugClient(
        lambda: bluetooth.async_ble_device_from_address(hass, address, connectable=True),
        entry.title,
        entry.options.get(CONF_SPEED, DEFAULT_SPEED),
    )
    try:
        await client.execute()
    except (BleakError, RugError, TimeoutError, OSError) as exc:
        await client.close()
        raise ConfigEntryNotReady(str(exc)) from exc
    entry.runtime_data = client
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await client.close()
        raise
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.close()
        return True
    return False

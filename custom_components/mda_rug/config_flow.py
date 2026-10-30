"""Discover matching controllers, or save an address before Bluetooth is ready."""

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback

from .const import CONF_COLOR_ORDER, CONF_SPEED, DEFAULT_COLOR_ORDER, DEFAULT_SPEED, DOMAIN
from .protocol import matches


def normalize_address(value: str) -> str:
    compact = value.strip().replace(":", "").replace("-", "")
    if not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        raise ValueError("Invalid Bluetooth MAC address")
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


class MdaRugConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                address = normalize_address(user_input[CONF_ADDRESS])
            except ValueError:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                info = bluetooth.async_last_service_info(self.hass, address, connectable=True)
                if info is not None and not matches(info.service_data, address):
                    errors["base"] = "unsupported_device"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={CONF_ADDRESS: address},
                    )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="MDA Rug"): str,
                    vol.Required(CONF_ADDRESS): str,
                }
            ),
        )

    async def async_step_bluetooth(self, discovery_info):
        if not matches(discovery_info.service_data, discovery_info.address):
            return self.async_abort(reason="unsupported_device")
        self._address = normalize_address(discovery_info.address)
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="MDA Rug", data={CONF_ADDRESS: self._address})
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"address": self._address},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MdaRugOptionsFlow()


class MdaRugOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COLOR_ORDER,
                        default=self.config_entry.options.get(
                            CONF_COLOR_ORDER, DEFAULT_COLOR_ORDER
                        ),
                    ): vol.In(["BGR", "RGB"]),
                    vol.Required(
                        CONF_SPEED, default=self.config_entry.options.get(CONF_SPEED, DEFAULT_SPEED)
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                }
            ),
        )

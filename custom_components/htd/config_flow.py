import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow, OptionsFlowWithConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIQUE_ID
from homeassistant.core import callback, HomeAssistant
from htd_client import async_get_model_info
from htd_client.constants import HtdConstants

from .const import CONF_DEVICE_NAME, CONF_ZONE_NAMES, CONF_SOURCE_NAMES, CONF_CUSTOMIZE_NAMES, DOMAIN

_LOGGER = logging.getLogger(__name__)


def configured_instances(hass: HomeAssistant):
    """Return a set of configured instances."""
    return set(
        entry.title for entry in hass.config_entries.async_entries(DOMAIN)
    )


class HtdConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    host: str = None
    port: int = HtdConstants.DEFAULT_PORT
    unique_id: str = None
    _device_name: str = None
    _model_info: dict = None
    _zone_name_overrides: dict = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ):
        """Handle dhcp discovery."""
        _LOGGER.info("HTD device detected: %s %s" % (discovery_info.ip, self.port))
        host = discovery_info.ip
        network_address = (host, self.port)
        model_info = await async_get_model_info(network_address=network_address)

        if model_info is None:
            return self.async_abort(reason="unknown_model")

        _LOGGER.info("Model identified as: %s" % model_info)

        unique_id = "htd-%s" % discovery_info.macaddress

        await self.async_set_unique_id(unique_id)

        self.unique_id = unique_id
        new_user_input = {
            CONF_HOST: discovery_info.ip,
            CONF_PORT: self.port,
            CONF_UNIQUE_ID: unique_id,
        }

        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_NAME: f"{model_info["friendly_name"]} ({host})",
        }

        return await self.async_step_custom_connection(new_user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        return await self.async_step_custom_connection(user_input)

    async def async_step_custom_connection(
        self, user_input: dict[str, Any] | None = None
    ):
        errors = {}

        if user_input is not None:
            success = False

            host = user_input[CONF_HOST]
            port = int(user_input[CONF_PORT])
            unique_id = user_input[CONF_UNIQUE_ID] if CONF_UNIQUE_ID in user_input else "htd-%s-%s" % (host, port)

            try:
                network_address = host, port
                response = await async_get_model_info(network_address=network_address)

                if response is not None:
                    success = True

            except Exception as e:
                _LOGGER.error("Exception occurred while trying to connect to Htd Gateway")
                _LOGGER.exception(e)
                pass

            if success:
                self.host = host
                self.port = port
                self.unique_id = unique_id

                return await self.async_step_device()

            errors['base'] = "no_connection"

        return self.async_show_form(
            step_id='user',
            data_schema=get_connection_settings_schema(),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HtdOptionsFlowHandler(config_entry)

    async def async_step_device(self, user_input=None):
        if user_input is not None:
            self._device_name = user_input.get(CONF_DEVICE_NAME, "")
            if user_input.get(CONF_CUSTOMIZE_NAMES, False):
                return await self.async_step_zone_names()
            return self.async_create_entry(
                title=self._device_name,
                data={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                    CONF_UNIQUE_ID: self.unique_id,
                    CONF_DEVICE_NAME: self._device_name,
                    CONF_ZONE_NAMES: {},
                    CONF_SOURCE_NAMES: {},
                },
                options={}
            )

        network_address = (self.host, self.port)
        model_info = await async_get_model_info(network_address=network_address)
        self._model_info = model_info

        return self.async_show_form(
            step_id='device',
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_DEVICE_NAME, default=model_info["friendly_name"]
                ): cv.string,
                vol.Optional(CONF_CUSTOMIZE_NAMES, default=False): cv.boolean,
            })
        )


class HtdOptionsFlowHandler(OptionsFlowWithConfigEntry):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            new_title = user_input.get(CONF_DEVICE_NAME, self.config_entry.title)
            options = {
                **self.config_entry.data,
                **user_input
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=options,
                title=new_title,
            )

            return self.async_create_entry(title=new_title, data={})

        return self.async_show_form(
            step_id='init',
            data_schema=get_connection_settings_schema(self.config_entry)
        )


def get_connection_settings_schema(config_entry: ConfigEntry | None = None):
    if config_entry is not None:
        host = config_entry.data.get(CONF_HOST)
        port = config_entry.data.get(CONF_PORT)
        device_name = config_entry.title
    else:
        host = None
        port = HtdConstants.DEFAULT_PORT
        device_name = None

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Optional(CONF_DEVICE_NAME, default=device_name): cv.string,
        }
    )

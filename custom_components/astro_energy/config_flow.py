"""Config flow for the ASTRO Energy integration."""

import asyncio
from typing import Any

from modbus_connection import ModbusError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_LOGGER_SERIAL,
    CONF_UNIT_ID,
    CONNECT_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    LOGGER,
)
from .solarman_v5 import SolarmanV5Unit
from .vendor.astro_modbus import MODEL, AstroInverter

UNIT_ID_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
)

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): probatio.All(
            TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            probatio.Length(min=1),
        ),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        probatio.Optional(CONF_LOGGER_SERIAL, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
    }
)


async def _async_probe(unit: SolarmanV5Unit) -> None:
    """Read the inverter once, and let the caller translate a failure."""
    async with asyncio.timeout(CONNECT_TIMEOUT):
        await AstroInverter(unit).async_update()


class AstroEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect the data logger details, then prove that the inverter answers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect Solarman V5 logger details and probe the inverter."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            unit_id = int(user_input[CONF_UNIT_ID])
            typed_serial = str(user_input.get(CONF_LOGGER_SERIAL) or "").strip()
            serial = self._parse_serial(typed_serial)
            if typed_serial and serial is None:
                errors = {"base": "invalid_serial"}
            else:
                unit = SolarmanV5Unit(
                    host=host, port=port, unit_id=unit_id, serial=serial
                )
                try:
                    await _async_probe(unit)
                except TimeoutError:
                    LOGGER.error("Timed out waiting for the data logger to answer")
                    errors = {"base": "cannot_connect"}
                except ModbusError as err:
                    LOGGER.error("Could not read the inverter: %s", err)
                    errors = {"base": "cannot_connect"}
                finally:
                    await unit.disconnect()
                if not errors:
                    await self.async_set_unique_id(f"v5-{host}-{port}-{unit_id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{MODEL} ({host})",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_UNIT_ID: unit_id,
                            CONF_LOGGER_SERIAL: unit.serial,
                        },
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def _parse_serial(text: str) -> int | None:
        """Return the serial the user typed, or ``None`` to detect it.

        Zero is the serial the logger refuses, so it means "detect" as well.
        """
        if not text.isdigit():
            return None
        return int(text) or None

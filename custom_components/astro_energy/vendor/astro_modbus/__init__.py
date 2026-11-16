"""Device library for ASTRO Energy TM-L series micro inverters.

The library is vendorized inside the integration: it has no Home Assistant
imports and only depends on ``modbus-connection``. It can be lifted into its
own PyPI package unchanged, which is what Home Assistant Core requires if this
integration is ever submitted upstream.

Example::

    from modbus_connection import ModbusTcpParams
    from modbus_connection.tmodbus import ModbusConnection

    from astro_modbus import AstroInverter

    connection = ModbusConnection(ModbusTcpParams(host="192.168.1.50", port=502))
    device = AstroInverter(connection.for_unit(1))
    await device.async_update()
    print(device.readings.ac_power)
"""

from .device import ALL, MANUFACTURER, MODEL, READINGS, AstroInverter
from .readings import Readings

__all__ = [
    "ALL",
    "MANUFACTURER",
    "MODEL",
    "READINGS",
    "AstroInverter",
    "Readings",
]

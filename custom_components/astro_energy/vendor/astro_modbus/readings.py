"""The telemetry block of an ASTRO Energy TM-L800Mi micro inverter.

The inverter serves **input registers** (function code ``0x04``) and, per the
reverse engineering documented in ha-solarman issues #624 and #728, only
answers a read that starts at ``0x0000``. It then returns the whole telemetry
block regardless of the requested count, so the map below is declared as one
readable range and read as a single 60-register block.

Register map (16-bit words, unsigned)::

    address  field            scale   unit   confidence
    0x0000   PV1 voltage      0.1     V      confirmed
    0x0001   PV2 voltage      0.1     V      confirmed
    0x0005   PV1 current      0.01    A      confirmed, scale disputed (0.03?)
    0x0006   PV2 current      0.01    A      confirmed, scale disputed (0.03?)
    0x0009   AC current       0.01    A      confirmed
    0x000B   AC voltage       0.1     V      confirmed
    0x000D   AC frequency     0.01    Hz     confirmed
    0x000F   AC power         0.1     W      community config, plausible
    0x0014   Total energy     0.01    kWh    community config, plausible
    0x0016   Temperature      0.1     degC   unconfirmed, offset disputed
    0x0017   MPPT count       1       -      community config
    0x003B   block end        1       -      forces the full 60-word read

Keep the scales here and the entity layer free of magic numbers: correcting a
scale after a field report is a one-line change in this file.
"""

from __future__ import annotations

from modbus_connection.model import Component, gauge, integer, raw_register


def _product(left: float | None, right: float | None) -> float | None:
    """Multiply two optional readings, or ``None`` while either is missing."""
    if left is None or right is None:
        return None
    return left * right


class Readings(Component):
    """Everything the inverter reports, in one 60-register block."""

    #: Function code 0x04. The input space is not the holding space.
    register_space = "input"

    #: The device only answers reads that start at 0x0000 and serves this map.
    register_ranges = ((0x0000, 0x003B),)

    pv1_voltage = gauge(0x0000, 0.1, signed=False, unit="V")
    """PV string 1 voltage."""

    pv2_voltage = gauge(0x0001, 0.1, signed=False, unit="V")
    """PV string 2 voltage."""

    pv1_current = gauge(0x0005, 0.01, signed=False, unit="A")
    """PV string 1 current."""

    pv2_current = gauge(0x0006, 0.01, signed=False, unit="A")
    """PV string 2 current."""

    ac_current = gauge(0x0009, 0.01, signed=False, unit="A")
    """AC output current."""

    ac_voltage = gauge(0x000B, 0.1, signed=False, unit="V")
    """AC output voltage."""

    ac_frequency = gauge(0x000D, 0.01, signed=False, unit="Hz")
    """AC output frequency."""

    ac_power = gauge(0x000F, 0.1, signed=False, unit="W")
    """AC output power."""

    total_energy = gauge(0x0014, 0.01, signed=False, unit="kWh")
    """Lifetime energy delivered, monotonic across the device's life."""

    temperature = gauge(0x0016, 0.1, signed=False, unit="degC")
    """Internal temperature. The community has not settled an offset for this."""

    mppt_count = integer(0x0017, signed=False)
    """Number of MPPT trackers the device serves."""

    block_end = raw_register(0x003B)
    """End of the telemetry block. Its only job is to widen the read to 60 words."""

    @property
    def pv1_power(self) -> float | None:
        """Power on PV string 1, computed from voltage and current."""
        return _product(self.pv1_voltage, self.pv1_current)

    @property
    def pv2_power(self) -> float | None:
        """Power on PV string 2, computed from voltage and current."""
        return _product(self.pv2_voltage, self.pv2_current)

    @property
    def dc_power(self) -> float | None:
        """Total DC input power, computed from both strings."""
        pv1 = self.pv1_power
        pv2 = self.pv2_power
        if pv1 is None or pv2 is None:
            return None
        return pv1 + pv2

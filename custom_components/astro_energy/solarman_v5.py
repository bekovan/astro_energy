"""Solarman V5 transport for an inverter behind a data logging stick.

The inverter's RS485 port is bridged by a Solarman V5 data logger, which serves
Modbus RTU rather than Modbus TCP: every exchange is a V5 frame whose payload is
a complete RTU ADU. ``modbus_connection`` has no backend for that, so this module
carries the RTU frame itself and hands the device library the same ``ModbusUnit``
interface the other transports provide.

Only the parts of that interface the ASTRO device library uses are implemented:
the four register and bit reads, the timeout the inverter asks for, and the link
lifecycle. Writes are not offered, because nothing in this integration writes.

The logger serial is not a secret but it is not guessable either, and the logger
ignores any frame that carries a different one. It does, however, stamp its own
serial into every reply, so an unrecognised serial is learned from the first
answer instead of being taken from the user.
"""

import asyncio
from collections.abc import Callable
import struct
from typing import Final

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)

from .const import LOGGER

_START: Final = 0xA5
"""First byte of every V5 frame."""

_END: Final = 0x15
"""Last byte of every V5 frame."""

_SUFFIX: Final = 0x10
"""Byte the logger expects between the declared length and the control code."""

_REQUEST: Final = 0x45
"""Control code of a V5 request."""

_RESPONSE: Final = 0x15
"""Control code of the answer to a request. Keep-alives and reports differ."""

_FRAME_TYPE: Final = 0x02
"""Frame type of a V5 frame that carries a Modbus RTU ADU."""

_CONTROL: Final = 4
"""Index of the control code in a V5 frame."""

_SEQUENCE: Final = 5
"""Index of the low byte of the sequence number in a V5 frame.

Only that byte is compared: the logger increments the high byte of the echo on
its way back, so the pair is not reliable.
"""

_SERIAL: Final = slice(7, 11)
"""Slice of the little-endian data logger serial in a V5 frame."""

_RTU_OFFSET: Final = 25
"""Where a reply carries the wrapped RTU frame.

The request prefix is one byte longer than the reply prefix, and the reply's
exact field widths vary between logger firmwares, so both offsets are tried and
the CRC decides.
"""

_MIN_FRAME: Final = 13
"""Bytes outside the declared payload: eleven header bytes, checksum and end."""

_MAX_PAYLOAD: Final = 4096
"""Guard against a corrupt length reading as a huge allocation."""

_MIN_PAYLOAD: Final = 5
"""One header byte plus the four the length field itself occupies."""

_MIN_RTU: Final = 5
"""Shortest usable RTU ADU: address, function, and a CRC."""

_TIMEOUT: Final = 10.0
"""The timeout a request gets before the inverter asks for a longer one."""

_MAX_REGISTERS: Final = 125
"""The most registers one Modbus read may ask for."""

_MAX_BITS: Final = 2000
"""The most coils or discrete inputs one Modbus read may ask for."""

_READ_COILS: Final = 0x01
_READ_DISCRETE_INPUTS: Final = 0x02
_READ_HOLDING_REGISTERS: Final = 0x03
_READ_INPUT_REGISTERS: Final = 0x04


def _crc16(data: bytes) -> bytes:
    """Return the Modbus CRC of ``data``, low byte first."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack("<H", crc)


def _rtu_request(unit_id: int, function: int, address: int, count: int) -> bytes:
    """Build the RTU ADU for one read."""
    body = struct.pack(">BBHH", unit_id, function, address, count)
    return body + _crc16(body)


def _v5_frame(rtu: bytes, serial: int, sequence: int) -> bytes:
    """Wrap an RTU ADU in the V5 request frame the logger accepts."""
    header = (
        bytes([_START])
        + struct.pack("<H", 15 + len(rtu))
        + bytes([_SUFFIX, _REQUEST])
        + struct.pack("<H", sequence)
        + struct.pack("<I", serial)
    )
    payload = (
        bytes([_FRAME_TYPE])
        + b"\x00\x00"  # sensor type
        + b"\x00\x00\x00\x00"  # delivery time
        + b"\x00\x00\x00\x00"  # power-on time
        + b"\x00\x00\x00\x00"  # offset time
        + rtu
    )
    frame = header + payload
    return frame + bytes([sum(frame[1:]) & 0xFF, _END])


def _unwrap_rtu(frame: bytes) -> bytes:
    """Return the RTU ADU carried by a V5 reply."""
    if frame[-1] != _END:
        raise ModbusProtocolError("The data logger answered without the V5 end byte")
    if frame[-2] != sum(frame[1:-2]) & 0xFF:
        raise ModbusProtocolError("The data logger answered with a bad V5 checksum")

    for offset in (_RTU_OFFSET, _RTU_OFFSET + 1):
        rtu = frame[offset:-2]
        if len(rtu) >= _MIN_RTU and _crc16(rtu[:-2]) == rtu[-2:]:
            return rtu

    payload = frame[_RTU_OFFSET:-2]
    if 0 < len(payload) < _MIN_RTU:
        # Too short to be a Modbus answer: the logger itself refused the request.
        raise ModbusError(
            f"The data logger refused the request with error code {payload[0]}"
        )
    raise ModbusProtocolError("The data logger answered without a valid Modbus frame")


class SolarmanV5Unit:
    """One inverter on a Solarman V5 data logger.

    Implements the part of ``modbus_connection.ModbusUnit`` the ASTRO device
    library uses. Requests are serialized on one stream, and a failed exchange
    drops the stream so the next request starts from a clean buffer.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        unit_id: int,
        serial: int | None = None,
        timeout: float = _TIMEOUT,
    ) -> None:
        """Bind the unit to one logger and one inverter slave address."""
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._serial = serial
        self._timeout = timeout
        self._message_spacing = 0.0
        self._connect_delay = 0.0
        self._sequence = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._io_lock = asyncio.Lock()
        self._lost_callbacks: list[Callable[[], None]] = []

    @property
    def serial(self) -> int | None:
        """The data logger serial, learned from its first answer if unknown."""
        return self._serial

    @property
    def connected(self) -> bool:
        """Whether the stream to the logger is up."""
        return self._writer is not None and not self._writer.is_closing()

    def set_message_spacing(self, seconds: float) -> None:
        """Keep the link quiet for ``seconds`` before this unit's requests."""
        self._message_spacing = seconds

    def require_timeout(self, seconds: float | None) -> None:
        """Ask for a per-request timeout of at least ``seconds``."""
        self._timeout = _TIMEOUT if seconds is None else max(_TIMEOUT, seconds)

    def require_connect_delay(self, seconds: float | None) -> None:
        """Ask for a pause of at least ``seconds`` after the link opens."""
        self._connect_delay = 0.0 if seconds is None else max(0.0, seconds)

    def on_connection_lost(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback fired when the link drops; returns an unsubscribe."""
        self._lost_callbacks.append(callback)

        def remove() -> None:
            try:
                self._lost_callbacks.remove(callback)
            except ValueError:
                pass

        return remove

    async def disconnect(self) -> None:
        """Close the stream; the next request opens a new one."""
        writer, self._writer = self._writer, None
        self._reader = None
        if writer is None:
            return
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        """Read ``count`` input registers from ``address`` (function 04)."""
        return await self._async_read_registers(
            _READ_INPUT_REGISTERS, address, count
        )

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read ``count`` holding registers from ``address`` (function 03)."""
        return await self._async_read_registers(
            _READ_HOLDING_REGISTERS, address, count
        )

    async def read_coils(self, address: int, count: int) -> list[bool]:
        """Read ``count`` coils from ``address`` (function 01)."""
        return await self._async_read_bits(_READ_COILS, address, count)

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        """Read ``count`` discrete inputs from ``address`` (function 02)."""
        return await self._async_read_bits(_READ_DISCRETE_INPUTS, address, count)

    # -- internals -----------------------------------------------------------

    def _next_sequence(self) -> int:
        """Return the next sequence number for a request."""
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence

    async def _async_connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Return the stream pair, opening it if needed."""
        if self._reader is not None and self.connected:
            return self._reader, self._writer  # type: ignore[return-value]
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self._reader, self._writer = reader, writer
        self._sequence = 0
        LOGGER.debug(
            "Connected to the Solarman V5 data logger at %s:%s", self._host, self._port
        )
        if self._connect_delay:
            await asyncio.sleep(self._connect_delay)
        return reader, writer

    def _notify_connection_lost(self) -> None:
        """Tell listeners the link went away."""
        for callback in list(self._lost_callbacks):
            callback()

    async def _async_read_frame(self, reader: asyncio.StreamReader) -> bytes:
        """Read one complete V5 frame, whatever it carries."""
        # Try to resync if we get out of alignment
        # Read byte by byte to find start
        for _ in range(512):  # limit resync attempts
            b = await reader.readexactly(1)
            if b[0] == _START:
                head_rest = await reader.readexactly(2)
                head = b + head_rest
                break
        else:
            raise ModbusProtocolError(
                "The data logger sent a frame without the V5 start byte"
            )
        length = struct.unpack("<H", head[1:3])[0]
        if not _MIN_PAYLOAD <= length <= _MAX_PAYLOAD:
            raise ModbusProtocolError(
                f"The data logger announced an implausible frame length: {length}"
            )
        return head + await reader.readexactly(length + _MIN_FRAME - 3)

    async def _async_read_reply(
        self, reader: asyncio.StreamReader, sequence: int
    ) -> bytes:
        """Read frames until the answer to ``sequence`` arrives."""
        while True:
            frame = await self._async_read_frame(reader)
            if frame[_CONTROL] != _RESPONSE:
                # Keep-alives and reports arrive unsolicited on the same stream.
                continue
            if frame[_SEQUENCE] != sequence & 0xFF:
                continue
            return frame

    async def _async_detect_serial(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> int:
        """Learn the logger serial from the reply to a frame addressed to zero."""
        writer.write(
            _v5_frame(
                _rtu_request(self._unit_id, _READ_INPUT_REGISTERS, 0, 1),
                0,
                self._next_sequence(),
            )
        )
        await writer.drain()
        while True:
            frame = await self._async_read_frame(reader)
            if frame[_CONTROL] != _RESPONSE:
                continue
            serial = struct.unpack("<I", frame[_SERIAL])[0]
            if serial:
                LOGGER.debug("Learned the Solarman V5 data logger serial %d", serial)
                return serial

    async def _async_request(self, function: int, address: int, count: int) -> bytes:
        """Send one read and return the RTU answer."""
        async with self._io_lock:
            try:
                async with asyncio.timeout(self._timeout):
                    reader, writer = await self._async_connect()
                    if self._serial is None:
                        self._serial = await self._async_detect_serial(reader, writer)
                    if self._message_spacing:
                        await asyncio.sleep(self._message_spacing)
                    sequence = self._next_sequence()
                    writer.write(
                        _v5_frame(
                            _rtu_request(self._unit_id, function, address, count),
                            self._serial,
                            sequence,
                        )
                    )
                    await writer.drain()
                    reply = await self._async_read_reply(reader, sequence)
                return _unwrap_rtu(reply)
            except TimeoutError as err:
                await self.disconnect()
                raise ModbusTimeoutError(
                    f"No answer from the data logger at {self._host}:{self._port}"
                ) from err
            except (OSError, EOFError) as err:
                await self.disconnect()
                self._notify_connection_lost()
                raise ModbusConnectionError(
                    f"Lost the link to the data logger at "
                    f"{self._host}:{self._port}: {err}"
                ) from err
            except ModbusProtocolError as err:
                await self.disconnect()
                self._notify_connection_lost()
                raise ModbusConnectionError(
                    f"Protocol error on the link to the data logger at "
                    f"{self._host}:{self._port}: {err}"
                ) from err

    def _check_answer(self, rtu: bytes, function: int) -> None:
        """Reject an answer from another unit, and raise a Modbus exception."""
        if rtu[0] != self._unit_id:
            raise ModbusProtocolError(
                f"The answer came from unit {rtu[0]}, not {self._unit_id}"
            )
        if rtu[1] == function | 0x80:
            raise ModbusExceptionError.from_code(rtu[2])
        if rtu[1] != function:
            raise ModbusProtocolError(
                f"The data logger answered function {rtu[1]:#04x}, "
                f"not {function:#04x}"
            )

    async def _async_read_registers(
        self, function: int, address: int, count: int
    ) -> list[int]:
        """Read registers with one of the two register functions."""
        if not 1 <= count <= _MAX_REGISTERS:
            raise ModbusError(
                f"A read of {count} registers is outside the Modbus limit "
                f"of {_MAX_REGISTERS}"
            )
        rtu = await self._async_request(function, address, count)
        self._check_answer(rtu, function)
        expected = count * 2
        if rtu[2] < expected or len(rtu) != rtu[2] + 5:
            raise ModbusProtocolError(
                f"The data logger answered a read of {count} registers "
                f"with {rtu[2]} bytes"
            )
        if rtu[2] > expected:
            # This inverter answers any read that starts at zero with the whole
            # telemetry block, so return the registers that were asked for.
            LOGGER.debug(
                "The inverter answered %d registers for a read of %d",
                rtu[2] // 2,
                count,
            )
        return list(struct.unpack(f">{count}H", rtu[3 : 3 + expected]))

    async def _async_read_bits(
        self, function: int, address: int, count: int
    ) -> list[bool]:
        """Read coils or discrete inputs with one of the two bit functions."""
        if not 1 <= count <= _MAX_BITS:
            raise ModbusError(
                f"A read of {count} bits is outside the Modbus limit of {_MAX_BITS}"
            )
        rtu = await self._async_request(function, address, count)
        self._check_answer(rtu, function)
        expected = (count + 7) // 8
        if rtu[2] != expected or len(rtu) != expected + 5:
            raise ModbusProtocolError(
                f"The data logger answered a read of {count} bits with "
                f"{rtu[2]} bytes"
            )
        data = rtu[3 : 3 + expected]
        return [bool(data[index // 8] >> (index % 8) & 1) for index in range(count)]

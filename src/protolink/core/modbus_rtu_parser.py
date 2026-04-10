from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModbusRtuFrameKind(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ModbusRtuParseResult:
    is_frame: bool
    crc_ok: bool
    kind: ModbusRtuFrameKind
    address: int | None
    function_code: int | None
    data: bytes
    crc_actual: int | None
    crc_expected: int | None
    summary: str
    details: tuple[str, ...]


def crc16_modbus(payload: bytes) -> int:
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def parse_modbus_rtu_frame(payload: bytes | None) -> ModbusRtuParseResult:
    if payload is None or len(payload) < 4:
        return ModbusRtuParseResult(
            is_frame=False,
            crc_ok=False,
            kind=ModbusRtuFrameKind.UNKNOWN,
            address=None,
            function_code=None,
            data=b"",
            crc_actual=None,
            crc_expected=None,
            summary="Not a Modbus RTU frame (requires at least 4 bytes).",
            details=(),
        )

    address = payload[0]
    function_code = payload[1]
    data = payload[2:-2]
    crc_actual = int.from_bytes(payload[-2:], "little")
    crc_expected = crc16_modbus(payload[:-2])
    crc_ok = crc_actual == crc_expected
    kind = _infer_kind(function_code, data)

    details = (
        f"Address: {address}",
        f"Function: 0x{function_code:02X}",
        f"Data Length: {len(data)}",
        f"CRC: {'OK' if crc_ok else 'MISMATCH'} (actual=0x{crc_actual:04X}, expected=0x{crc_expected:04X})",
        *_decode_function_details(function_code, data, kind),
    )
    return ModbusRtuParseResult(
        is_frame=True,
        crc_ok=crc_ok,
        kind=kind,
        address=address,
        function_code=function_code,
        data=data,
        crc_actual=crc_actual,
        crc_expected=crc_expected,
        summary=f"Modbus RTU {kind.value}: addr={address}, func=0x{function_code:02X}, data={len(data)} bytes",
        details=details,
    )


def render_modbus_rtu_result(result: ModbusRtuParseResult) -> str:
    if not result.details:
        return result.summary
    return "\n".join((result.summary, "", *result.details))


def _infer_kind(function_code: int, data: bytes) -> ModbusRtuFrameKind:
    if function_code & 0x80:
        return ModbusRtuFrameKind.EXCEPTION
    if function_code in {0x01, 0x02, 0x03, 0x04} and len(data) == 4:
        return ModbusRtuFrameKind.REQUEST
    if function_code in {0x05, 0x06} and len(data) == 4:
        return ModbusRtuFrameKind.REQUEST
    if function_code in {0x0F, 0x10} and len(data) >= 5:
        return ModbusRtuFrameKind.REQUEST
    if data:
        return ModbusRtuFrameKind.RESPONSE
    return ModbusRtuFrameKind.UNKNOWN


def _decode_function_details(
    function_code: int,
    data: bytes,
    kind: ModbusRtuFrameKind,
) -> tuple[str, ...]:
    if kind == ModbusRtuFrameKind.EXCEPTION:
        if data:
            return (f"Exception Code: 0x{data[0]:02X}",)
        return ("Exception response without code byte.",)

    if function_code in {0x01, 0x02, 0x03, 0x04}:
        if kind == ModbusRtuFrameKind.REQUEST and len(data) >= 4:
            start = int.from_bytes(data[0:2], "big")
            count = int.from_bytes(data[2:4], "big")
            return (f"Start Address: {start}", f"Quantity: {count}")
        if len(data) >= 1:
            byte_count = data[0]
            return (f"Byte Count: {byte_count}",)
        return ("No payload body for read response.",)

    if function_code in {0x05, 0x06} and len(data) >= 4:
        address = int.from_bytes(data[0:2], "big")
        value = int.from_bytes(data[2:4], "big")
        return (f"Write Address: {address}", f"Write Value: 0x{value:04X}")

    if function_code in {0x0F, 0x10} and len(data) >= 5:
        start = int.from_bytes(data[0:2], "big")
        count = int.from_bytes(data[2:4], "big")
        byte_count = data[4]
        return (f"Start Address: {start}", f"Quantity: {count}", f"Byte Count: {byte_count}")

    return ()

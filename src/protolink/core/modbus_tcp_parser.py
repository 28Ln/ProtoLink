from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModbusTcpFrameKind(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ModbusTcpParseResult:
    is_frame: bool
    kind: ModbusTcpFrameKind
    transaction_id: int | None
    protocol_id: int | None
    declared_length: int | None
    unit_id: int | None
    function_code: int | None
    data: bytes
    summary: str
    details: tuple[str, ...]


def parse_modbus_tcp_frame(payload: bytes | None) -> ModbusTcpParseResult:
    if payload is None or len(payload) < 8:
        return ModbusTcpParseResult(
            is_frame=False,
            kind=ModbusTcpFrameKind.UNKNOWN,
            transaction_id=None,
            protocol_id=None,
            declared_length=None,
            unit_id=None,
            function_code=None,
            data=b"",
            summary="Not a Modbus TCP frame (requires at least 8 bytes).",
            details=(),
        )

    transaction_id = int.from_bytes(payload[0:2], "big")
    protocol_id = int.from_bytes(payload[2:4], "big")
    declared_length = int.from_bytes(payload[4:6], "big")
    expected_total_length = 6 + declared_length
    if protocol_id != 0:
        return ModbusTcpParseResult(
            is_frame=False,
            kind=ModbusTcpFrameKind.UNKNOWN,
            transaction_id=transaction_id,
            protocol_id=protocol_id,
            declared_length=declared_length,
            unit_id=None,
            function_code=None,
            data=b"",
            summary=f"Not a Modbus TCP frame (protocol id must be 0, got {protocol_id}).",
            details=(),
        )
    if len(payload) != expected_total_length:
        return ModbusTcpParseResult(
            is_frame=False,
            kind=ModbusTcpFrameKind.UNKNOWN,
            transaction_id=transaction_id,
            protocol_id=protocol_id,
            declared_length=declared_length,
            unit_id=None,
            function_code=None,
            data=b"",
            summary=(
                "Not a Modbus TCP frame "
                f"(length mismatch: payload={len(payload)}, expected={expected_total_length})."
            ),
            details=(),
        )

    unit_id = payload[6]
    function_code = payload[7]
    data = payload[8:]
    kind = _infer_kind(function_code, data)

    details = (
        f"Transaction ID: {transaction_id}",
        f"Protocol ID: {protocol_id}",
        f"Length: {declared_length}",
        f"Unit ID: {unit_id}",
        f"Function: 0x{function_code:02X}",
        f"Data Length: {len(data)}",
        *_decode_function_details(function_code, data, kind),
    )
    return ModbusTcpParseResult(
        is_frame=True,
        kind=kind,
        transaction_id=transaction_id,
        protocol_id=protocol_id,
        declared_length=declared_length,
        unit_id=unit_id,
        function_code=function_code,
        data=data,
        summary=f"Modbus TCP {kind.value}: tx={transaction_id}, unit={unit_id}, func=0x{function_code:02X}, data={len(data)} bytes",
        details=details,
    )


def render_modbus_tcp_result(result: ModbusTcpParseResult) -> str:
    if not result.details:
        return result.summary
    return "\n".join((result.summary, "", *result.details))


def _infer_kind(function_code: int, data: bytes) -> ModbusTcpFrameKind:
    if function_code & 0x80:
        return ModbusTcpFrameKind.EXCEPTION
    if function_code in {0x01, 0x02, 0x03, 0x04} and len(data) == 4:
        return ModbusTcpFrameKind.REQUEST
    if function_code in {0x05, 0x06} and len(data) == 4:
        return ModbusTcpFrameKind.REQUEST
    if function_code in {0x0F, 0x10} and len(data) >= 5:
        return ModbusTcpFrameKind.REQUEST
    if data:
        return ModbusTcpFrameKind.RESPONSE
    return ModbusTcpFrameKind.UNKNOWN


def _decode_function_details(
    function_code: int,
    data: bytes,
    kind: ModbusTcpFrameKind,
) -> tuple[str, ...]:
    if kind == ModbusTcpFrameKind.EXCEPTION:
        if data:
            return (f"Exception Code: 0x{data[0]:02X}",)
        return ("Exception response without code byte.",)

    if function_code in {0x01, 0x02, 0x03, 0x04}:
        if kind == ModbusTcpFrameKind.REQUEST and len(data) >= 4:
            start = int.from_bytes(data[0:2], "big")
            count = int.from_bytes(data[2:4], "big")
            return (f"Start Address: {start}", f"Quantity: {count}")
        if len(data) >= 1:
            return (f"Byte Count: {data[0]}",)
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

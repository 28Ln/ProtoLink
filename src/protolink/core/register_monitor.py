from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import StrEnum


class RegisterDataType(StrEnum):
    UINT16 = "uint16"
    INT16 = "int16"
    UINT32 = "uint32"
    INT32 = "int32"
    FLOAT32 = "float32"


class RegisterByteOrder(StrEnum):
    AB = "AB"
    BA = "BA"
    CDAB = "CDAB"
    BADC = "BADC"


@dataclass(frozen=True, slots=True)
class RegisterPoint:
    name: str
    address: int
    data_type: RegisterDataType
    byte_order: RegisterByteOrder = RegisterByteOrder.AB
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""

    @property
    def register_count(self) -> int:
        if self.data_type in {RegisterDataType.UINT16, RegisterDataType.INT16}:
            return 1
        return 2


def decode_register_point(point: RegisterPoint, registers: tuple[int, ...] | list[int]) -> float | int:
    if len(registers) < point.register_count:
        raise ValueError(
            f"Register point '{point.name}' requires {point.register_count} register(s), got {len(registers)}."
        )
    if any(not 0 <= value <= 0xFFFF for value in registers[: point.register_count]):
        raise ValueError("Registers must contain 16-bit unsigned values.")

    word_bytes = b"".join(int(register).to_bytes(2, "big") for register in registers[: point.register_count])
    ordered = _apply_byte_order(word_bytes, point.byte_order)

    if point.data_type == RegisterDataType.UINT16:
        value: float | int = int.from_bytes(ordered, "big", signed=False)
    elif point.data_type == RegisterDataType.INT16:
        value = int.from_bytes(ordered, "big", signed=True)
    elif point.data_type == RegisterDataType.UINT32:
        value = int.from_bytes(ordered, "big", signed=False)
    elif point.data_type == RegisterDataType.INT32:
        value = int.from_bytes(ordered, "big", signed=True)
    else:
        value = struct.unpack(">f", ordered)[0]

    scaled = (float(value) * point.scale) + point.offset
    if _is_int_like(value) and _is_int_like(scaled):
        return int(round(scaled))
    return scaled


def _apply_byte_order(raw: bytes, byte_order: RegisterByteOrder) -> bytes:
    if len(raw) == 2:
        if byte_order in {RegisterByteOrder.AB, RegisterByteOrder.CDAB}:
            return raw
        return bytes((raw[1], raw[0]))

    if len(raw) != 4:
        raise ValueError("Only 16-bit and 32-bit register values are supported.")

    a, b, c, d = raw
    if byte_order == RegisterByteOrder.AB:
        return bytes((a, b, c, d))
    if byte_order == RegisterByteOrder.BA:
        return bytes((b, a, d, c))
    if byte_order == RegisterByteOrder.CDAB:
        return bytes((c, d, a, b))
    return bytes((d, c, b, a))


def _is_int_like(value: float | int) -> bool:
    if isinstance(value, int):
        return True
    return float(value).is_integer()

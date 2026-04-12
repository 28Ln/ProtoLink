from __future__ import annotations

import base64
import json

from protolink.core.modbus_rtu_parser import crc16_modbus


def utf8_to_hex(text: str) -> str:
    return text.encode("utf-8").hex(" ")


def hex_to_utf8(text: str) -> str:
    return bytes.fromhex(text).decode("utf-8", errors="strict")


def hex_modbus_crc16(text: str) -> str:
    payload = bytes.fromhex(text)
    checksum = crc16_modbus(payload)
    return checksum.to_bytes(2, "little").hex(" ")


def pretty_json(text: str) -> str:
    payload = json.loads(text)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def utf8_to_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")

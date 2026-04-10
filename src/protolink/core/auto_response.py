from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from protolink.core.modbus_rtu_parser import ModbusRtuFrameKind, parse_modbus_rtu_frame
from protolink.core.modbus_tcp_parser import ModbusTcpFrameKind, parse_modbus_tcp_frame


class AutoResponseProtocol(StrEnum):
    RAW_BYTES = "raw_bytes"
    MODBUS_RTU = "modbus_rtu"
    MODBUS_TCP = "modbus_tcp"


@dataclass(frozen=True, slots=True)
class AutoResponseRule:
    name: str
    protocol: AutoResponseProtocol
    response_payload: bytes
    enabled: bool = True
    raw_match_payload: bytes = b""
    unit_id: int | None = None
    function_code: int | None = None
    data_prefix: bytes = b""


@dataclass(frozen=True, slots=True)
class AutoResponseAction:
    rule_name: str
    protocol: AutoResponseProtocol
    response_payload: bytes


def select_auto_response_action(
    rules: Iterable[AutoResponseRule],
    payload: bytes,
) -> AutoResponseAction | None:
    for rule in rules:
        if not rule.enabled:
            continue
        if _rule_matches_payload(rule, payload):
            return AutoResponseAction(
                rule_name=rule.name,
                protocol=rule.protocol,
                response_payload=rule.response_payload,
            )
    return None


def _rule_matches_payload(rule: AutoResponseRule, payload: bytes) -> bool:
    if rule.protocol == AutoResponseProtocol.RAW_BYTES:
        if not rule.raw_match_payload:
            return False
        return payload == rule.raw_match_payload

    if rule.protocol == AutoResponseProtocol.MODBUS_RTU:
        parsed = parse_modbus_rtu_frame(payload)
        if not parsed.is_frame or not parsed.crc_ok:
            return False
        if parsed.kind not in {ModbusRtuFrameKind.REQUEST, ModbusRtuFrameKind.UNKNOWN}:
            return False
        if rule.unit_id is not None and parsed.address != rule.unit_id:
            return False
        if rule.function_code is not None and parsed.function_code != rule.function_code:
            return False
        if rule.data_prefix and not parsed.data.startswith(rule.data_prefix):
            return False
        return True

    parsed = parse_modbus_tcp_frame(payload)
    if not parsed.is_frame:
        return False
    if parsed.kind not in {ModbusTcpFrameKind.REQUEST, ModbusTcpFrameKind.UNKNOWN}:
        return False
    if rule.unit_id is not None and parsed.unit_id != rule.unit_id:
        return False
    if rule.function_code is not None and parsed.function_code != rule.function_code:
        return False
    if rule.data_prefix and not parsed.data.startswith(rule.data_prefix):
        return False
    return True

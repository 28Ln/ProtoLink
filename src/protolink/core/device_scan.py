from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.core.modbus_rtu_parser import ModbusRtuFrameKind, crc16_modbus, parse_modbus_rtu_frame
from protolink.core.modbus_tcp_parser import ModbusTcpFrameKind, parse_modbus_tcp_frame


class DeviceScanTransportKind(StrEnum):
    MODBUS_RTU = "modbus_rtu"
    MODBUS_TCP = "modbus_tcp"


@dataclass(frozen=True, slots=True)
class DeviceScanConfig:
    transport_kind: DeviceScanTransportKind
    target: str
    unit_id_start: int = 1
    unit_id_end: int = 16
    function_code: int = 0x03
    start_address: int = 0
    quantity: int = 1
    timeout_ms: int = 500

    @property
    def unit_ids(self) -> tuple[int, ...]:
        begin = max(self.unit_id_start, 0)
        end = min(self.unit_id_end, 247)
        if end < begin:
            return ()
        return tuple(range(begin, end + 1))


@dataclass(frozen=True, slots=True)
class DeviceScanRequest:
    unit_id: int
    payload: bytes
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class DeviceScanOutcome:
    unit_id: int
    reachable: bool
    exception_code: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceScanSummary:
    target: str
    transport_kind: DeviceScanTransportKind
    total_units: int
    discovered_units: tuple[int, ...]
    exception_units: tuple[int, ...]
    missing_units: tuple[int, ...]
    errors: tuple[str, ...]


def build_device_scan_requests(config: DeviceScanConfig) -> tuple[DeviceScanRequest, ...]:
    requests: list[DeviceScanRequest] = []
    for index, unit_id in enumerate(config.unit_ids, start=1):
        if config.transport_kind == DeviceScanTransportKind.MODBUS_RTU:
            payload = build_modbus_rtu_probe_request(
                unit_id=unit_id,
                function_code=config.function_code,
                start_address=config.start_address,
                quantity=config.quantity,
            )
        else:
            payload = build_modbus_tcp_probe_request(
                transaction_id=index,
                unit_id=unit_id,
                function_code=config.function_code,
                start_address=config.start_address,
                quantity=config.quantity,
            )
        requests.append(
            DeviceScanRequest(
                unit_id=unit_id,
                payload=payload,
                metadata={
                    "transport_kind": config.transport_kind.value,
                    "target": config.target,
                    "timeout_ms": str(config.timeout_ms),
                    "scan_unit_id": str(unit_id),
                },
            )
        )
    return tuple(requests)


def build_modbus_rtu_probe_request(
    *,
    unit_id: int,
    function_code: int,
    start_address: int,
    quantity: int,
) -> bytes:
    pdu = bytes(
        (
            unit_id & 0xFF,
            function_code & 0xFF,
            (start_address >> 8) & 0xFF,
            start_address & 0xFF,
            (quantity >> 8) & 0xFF,
            quantity & 0xFF,
        )
    )
    crc = crc16_modbus(pdu).to_bytes(2, "little")
    return pdu + crc


def build_modbus_tcp_probe_request(
    *,
    transaction_id: int,
    unit_id: int,
    function_code: int,
    start_address: int,
    quantity: int,
) -> bytes:
    mbap = bytes(
        (
            (transaction_id >> 8) & 0xFF,
            transaction_id & 0xFF,
            0x00,
            0x00,
            0x00,
            0x06,
            unit_id & 0xFF,
        )
    )
    pdu = bytes(
        (
            function_code & 0xFF,
            (start_address >> 8) & 0xFF,
            start_address & 0xFF,
            (quantity >> 8) & 0xFF,
            quantity & 0xFF,
        )
    )
    return mbap + pdu


def evaluate_device_scan_response(
    transport_kind: DeviceScanTransportKind,
    *,
    expected_unit_id: int,
    payload: bytes,
) -> DeviceScanOutcome:
    if transport_kind == DeviceScanTransportKind.MODBUS_RTU:
        parsed = parse_modbus_rtu_frame(payload)
        if not parsed.is_frame:
            return DeviceScanOutcome(expected_unit_id, reachable=False, error=parsed.summary)
        if not parsed.crc_ok:
            return DeviceScanOutcome(expected_unit_id, reachable=False, error="CRC 校验不匹配。")
        if parsed.address != expected_unit_id:
            return DeviceScanOutcome(
                expected_unit_id,
                reachable=False,
                error=f"单元 ID 不匹配：期望 {expected_unit_id}，实际 {parsed.address}。",
            )
        if parsed.kind == ModbusRtuFrameKind.EXCEPTION:
            code = parsed.data[0] if parsed.data else None
            return DeviceScanOutcome(expected_unit_id, reachable=False, exception_code=code)
        return DeviceScanOutcome(expected_unit_id, reachable=True)

    parsed = parse_modbus_tcp_frame(payload)
    if not parsed.is_frame:
        return DeviceScanOutcome(expected_unit_id, reachable=False, error=parsed.summary)
    if parsed.unit_id != expected_unit_id:
        return DeviceScanOutcome(
            expected_unit_id,
            reachable=False,
            error=f"单元 ID 不匹配：期望 {expected_unit_id}，实际 {parsed.unit_id}。",
        )
    if parsed.kind == ModbusTcpFrameKind.EXCEPTION:
        code = parsed.data[0] if parsed.data else None
        return DeviceScanOutcome(expected_unit_id, reachable=False, exception_code=code)
    return DeviceScanOutcome(expected_unit_id, reachable=True)


def build_device_scan_summary(
    config: DeviceScanConfig,
    outcomes: tuple[DeviceScanOutcome, ...],
) -> DeviceScanSummary:
    reachable = sorted(outcome.unit_id for outcome in outcomes if outcome.reachable)
    exception_units = sorted(outcome.unit_id for outcome in outcomes if outcome.exception_code is not None)
    responded = {outcome.unit_id for outcome in outcomes if outcome.reachable or outcome.exception_code is not None}
    missing = sorted(unit_id for unit_id in config.unit_ids if unit_id not in responded)
    errors = tuple(outcome.error for outcome in outcomes if outcome.error)
    return DeviceScanSummary(
        target=config.target,
        transport_kind=config.transport_kind,
        total_units=len(config.unit_ids),
        discovered_units=tuple(reachable),
        exception_units=tuple(exception_units),
        missing_units=tuple(missing),
        errors=errors,
    )

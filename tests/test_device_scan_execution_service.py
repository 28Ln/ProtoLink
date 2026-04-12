from collections.abc import Mapping

from protolink.application.device_scan_execution_service import DeviceScanExecutionService
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.core.transport import TransportKind


class _FakeScanTarget:
    def __init__(self, *, connected: bool = True, session_id: str | None = None, peer: str | None = None) -> None:
        self.connected = connected
        self.sent: list[tuple[bytes, dict[str, str]]] = []
        self.snapshot = type(
            "Snapshot",
            (),
            {
                "active_session_id": session_id,
                "selected_client_peer": peer,
            },
        )()

    def is_connected(self) -> bool:
        return self.connected

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        self.sent.append((payload, dict(metadata or {})))


def test_device_scan_execution_service_dispatches_requests_and_summarizes_tcp_responses() -> None:
    event_bus = EventBus()
    target = _FakeScanTarget()
    service = DeviceScanExecutionService(event_bus, {TransportKind.TCP_CLIENT: target})
    config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_TCP,
        target="127.0.0.1:502",
        unit_id_start=1,
        unit_id_end=3,
    )

    service.execute_scan(config, TransportKind.TCP_CLIENT)

    assert service.snapshot.running is True
    assert service.snapshot.dispatched_requests == 3
    assert len(target.sent) == 3
    assert all(metadata["source"] == "device_scan" for _, metadata in target.sent)

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x01, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (9 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            raw_payload=bytes([0x00, 0x02, 0x00, 0x00, 0x00, 0x03, 0x02, 0x83, 0x02]),
        )
    )

    summary = service.finalize_current_scan()

    assert summary is not None
    assert summary.discovered_units == (1,)
    assert summary.exception_units == (2,)
    assert summary.missing_units == (3,)
    assert service.snapshot.running is False


def test_device_scan_execution_service_handles_rtu_and_connection_errors() -> None:
    event_bus = EventBus()
    disconnected = _FakeScanTarget(connected=False)
    service = DeviceScanExecutionService(event_bus, {TransportKind.SERIAL: disconnected})
    config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_RTU,
        target="COM7@115200",
        unit_id_start=1,
        unit_id_end=1,
    )

    service.execute_scan(config, TransportKind.SERIAL)
    assert service.snapshot.last_error == "Device scan target 'serial' is not connected."

    connected = _FakeScanTarget()
    service = DeviceScanExecutionService(event_bus, {TransportKind.SERIAL: connected})
    service.execute_scan(config, TransportKind.SERIAL)
    body = bytes([0x01, 0x03, 0x02, 0x00, 0x2A])
    frame = body + crc16_modbus(body).to_bytes(2, "little")
    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (7 bytes)",
            transport_kind=TransportKind.SERIAL.value,
            raw_payload=frame,
        )
    )

    summary = service.finalize_current_scan()
    assert summary is not None
    assert summary.discovered_units == (1,)


def test_device_scan_execution_service_filters_inbound_matches_by_active_session() -> None:
    event_bus = EventBus()
    target = _FakeScanTarget(session_id="session-a")
    service = DeviceScanExecutionService(event_bus, {TransportKind.TCP_CLIENT: target})
    config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_TCP,
        target="127.0.0.1:502",
        unit_id_start=1,
        unit_id_end=1,
    )

    service.execute_scan(config, TransportKind.TCP_CLIENT)

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            session_id="session-b",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x01, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    assert service.snapshot.discovered_unit_ids == ()

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            session_id="session-a",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x01, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    assert service.snapshot.discovered_unit_ids == (1,)

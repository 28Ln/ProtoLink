from collections.abc import Mapping

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, StructuredLogEntry, create_log_entry
from protolink.core.transport import TransportKind


class _FakeTarget:
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


class _FailingTarget(_FakeTarget):
    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        raise RuntimeError("sink offline")


def test_auto_response_runtime_service_dispatches_matching_inbound_messages() -> None:
    event_bus = EventBus()
    target = _FakeTarget()
    service = AutoResponseRuntimeService(event_bus, {TransportKind.SERIAL: target})
    service.set_rules(
        (
            AutoResponseRule(
                name="Ping Rule",
                protocol=AutoResponseProtocol.RAW_BYTES,
                raw_match_payload=b"PING",
                response_payload=b"PONG",
            ),
        )
    )

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.SERIAL.value,
            raw_payload=b"PING",
        )
    )

    assert target.sent == [
        (
            b"PONG",
            {
                "source": "auto_response",
                "rule_name": "Ping Rule",
                "protocol": "raw_bytes",
            },
        )
    ]
    assert service.snapshot.matched_count == 1
    assert service.snapshot.last_rule_name == "Ping Rule"


def test_auto_response_runtime_service_ignores_outbound_or_disabled_paths() -> None:
    event_bus = EventBus()
    target = _FakeTarget()
    service = AutoResponseRuntimeService(event_bus, {TransportKind.TCP_CLIENT: target})
    service.set_rules(
        (
            AutoResponseRule(
                name="Echo",
                protocol=AutoResponseProtocol.RAW_BYTES,
                raw_match_payload=b"HELLO",
                response_payload=b"WORLD",
            ),
        )
    )

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Outbound payload (5 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            raw_payload=b"HELLO",
        )
    )
    assert target.sent == []

    service.set_enabled(False)
    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (5 bytes)",
            transport_kind=TransportKind.TCP_CLIENT.value,
            raw_payload=b"HELLO",
        )
    )
    assert target.sent == []


def test_auto_response_runtime_service_logs_send_failures() -> None:
    event_bus = EventBus()
    target = _FailingTarget()
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    service = AutoResponseRuntimeService(event_bus, {TransportKind.SERIAL: target})
    service.set_rules(
        (
            AutoResponseRule(
                name="Ping Rule",
                protocol=AutoResponseProtocol.RAW_BYTES,
                raw_match_payload=b"PING",
                response_payload=b"PONG",
            ),
        )
    )

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.SERIAL.value,
            raw_payload=b"PING",
        )
    )

    assert service.snapshot.last_error == "自动响应发送失败：sink offline"
    error_entries = [entry for entry in captured if entry.category == "automation.auto_response.error"]
    assert len(error_entries) == 1
    assert error_entries[0].message == "自动响应发送失败：sink offline"
    assert error_entries[0].metadata == {
        "rule_name": "Ping Rule",
        "protocol": "raw_bytes",
        "transport_kind": "serial",
    }


def test_auto_response_runtime_service_filters_inbound_messages_by_active_session() -> None:
    event_bus = EventBus()
    target = _FakeTarget(session_id="session-a")
    service = AutoResponseRuntimeService(event_bus, {TransportKind.SERIAL: target})
    service.set_rules(
        (
            AutoResponseRule(
                name="Ping Rule",
                protocol=AutoResponseProtocol.RAW_BYTES,
                raw_match_payload=b"PING",
                response_payload=b"PONG",
            ),
        )
    )

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.SERIAL.value,
            session_id="session-b",
            raw_payload=b"PING",
        )
    )
    assert target.sent == []

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.SERIAL.value,
            session_id="session-a",
            raw_payload=b"PING",
        )
    )
    assert len(target.sent) == 1

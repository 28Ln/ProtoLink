from collections.abc import Mapping

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.transport import TransportKind


class _FakeTarget:
    def __init__(self, *, connected: bool = True) -> None:
        self.connected = connected
        self.sent: list[tuple[bytes, dict[str, str]]] = []

    def is_connected(self) -> bool:
        return self.connected

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        self.sent.append((payload, dict(metadata or {})))


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

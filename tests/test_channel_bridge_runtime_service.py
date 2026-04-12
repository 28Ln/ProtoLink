import time
from collections.abc import Mapping

from protolink.application.channel_bridge_runtime_service import ChannelBridgeRuntimeService
from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, StructuredLogEntry, create_log_entry
from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import TransportKind


class _FakeBridgeTarget:
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


class _FailingBridgeTarget(_FakeBridgeTarget):
    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        raise RuntimeError("bridge sink offline")


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for channel bridge condition.")


def test_channel_bridge_runtime_service_bridges_inbound_messages() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: target},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="UDP->TCP",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)

        assert target.sent == [
            (
                b"PING",
                {
                    "source": "channel_bridge",
                    "bridge_name": "UDP->TCP",
                    "source_transport_kind": "udp",
                    "target_transport_kind": "tcp_client",
                },
            )
        ]
        assert service.snapshot.last_bridge_name == "UDP->TCP"
        assert service.snapshot.bridged_count == 1
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_applies_script_transform_and_rejects_invalid_bridge() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {
            TransportKind.TCP_SERVER: target,
            TransportKind.UDP: target,
        },
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="MQTT->TCP",
                source_transport_kind=TransportKind.MQTT_CLIENT,
                target_transport_kind=TransportKind.TCP_SERVER,
                script_language=ScriptLanguage.PYTHON,
                script_code="result = payload[::-1]",
            ),
            ChannelBridgeConfig(
                name="Invalid Loop",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.UDP,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.MQTT_CLIENT.value,
                raw_payload=b"ABCD",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)
        assert target.sent[0][0] == b"DCBA"

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (3 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"XYZ",
            )
        )
        _wait_until(lambda: service.snapshot.last_error is not None)
        assert service.snapshot.last_error == "Bridge 'Invalid Loop' cannot bridge a transport kind to itself."
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_logs_script_and_send_failures() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    failing_target = _FailingBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: failing_target},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="Broken Script",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="raise RuntimeError('boom')",
            ),
            ChannelBridgeConfig(
                name="Send Failure",
                source_transport_kind=TransportKind.MQTT_CLIENT,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: service.snapshot.last_error is not None)
        assert service.snapshot.last_error == "Bridge 'Broken Script' script failed: boom"

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.MQTT_CLIENT.value,
                raw_payload=b"PONG",
            )
        )
        _wait_until(lambda: any(entry.message == "Bridge 'Send Failure' send failed: bridge sink offline" for entry in captured))

        error_entries = [entry for entry in captured if entry.category == "automation.channel_bridge.error"]
        assert [entry.message for entry in error_entries] == [
            "Bridge 'Broken Script' script failed: boom",
            "Bridge 'Send Failure' send failed: bridge sink offline",
        ]
        assert error_entries[0].metadata == {
            "bridge_name": "Broken Script",
            "source_transport_kind": "udp",
            "target_transport_kind": "tcp_client",
        }
        assert error_entries[1].metadata == {
            "bridge_name": "Send Failure",
            "source_transport_kind": "mqtt_client",
            "target_transport_kind": "tcp_client",
        }
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_times_out_scripts_without_blocking_publish() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: _FakeBridgeTarget()},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="Timeout Bridge",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="while True:\n    pass",
            ),
        )
    )

    try:
        started = time.monotonic()
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        elapsed = time.monotonic() - started

        _wait_until(lambda: any(entry.category == "automation.channel_bridge.error" for entry in captured))

        assert elapsed < 0.2
        assert "timed out" in (service.snapshot.last_error or "")
        assert any("timed out" in entry.message for entry in captured if entry.category == "automation.channel_bridge.error")
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_filters_source_messages_by_active_session() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    source_scope = _FakeBridgeTarget(session_id="session-a")
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {
            TransportKind.UDP: source_scope,
            TransportKind.TCP_CLIENT: target,
        },
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="UDP->TCP",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                session_id="session-b",
                raw_payload=b"PING",
            )
        )
        time.sleep(0.05)
        assert target.sent == []

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                session_id="session-a",
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)
        assert target.sent[0][0] == b"PING"
    finally:
        service.shutdown()

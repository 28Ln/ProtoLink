from collections.abc import Mapping

from protolink.application.channel_bridge_runtime_service import ChannelBridgeRuntimeService
from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import TransportKind


class _FakeBridgeTarget:
    def __init__(self, *, connected: bool = True) -> None:
        self.connected = connected
        self.sent: list[tuple[bytes, dict[str, str]]] = []

    def is_connected(self) -> bool:
        return self.connected

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        self.sent.append((payload, dict(metadata or {})))


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

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.UDP.value,
            raw_payload=b"PING",
        )
    )

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

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (4 bytes)",
            transport_kind=TransportKind.MQTT_CLIENT.value,
            raw_payload=b"ABCD",
        )
    )
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
    assert service.snapshot.last_error == "Bridge 'Invalid Loop' cannot bridge a transport kind to itself."

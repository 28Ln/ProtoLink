from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    RawTransportMessage,
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportEventType,
    TransportKind,
    TransportRegistry,
)


class DummyAdapter(TransportAdapter):
    def __init__(self) -> None:
        super().__init__(
            TransportDescriptor(
                kind=TransportKind.SERIAL,
                display_name="Dummy Serial",
                capabilities=TransportCapabilities(supports_reconnect=True),
            )
        )

    async def open(self, config: TransportConfig) -> None:
        self.bind_session(config)
        self.emit_state(ConnectionState.CONNECTED)

    async def close(self) -> None:
        self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata=None) -> None:
        self.emit_message(MessageDirection.OUTBOUND, payload, metadata)


def test_transport_registry_creates_registered_adapter() -> None:
    registry = TransportRegistry()
    registry.register(TransportKind.SERIAL, DummyAdapter)

    adapter = registry.create(TransportKind.SERIAL)

    assert isinstance(adapter, DummyAdapter)
    assert registry.registered_kinds() == (TransportKind.SERIAL,)


def test_adapter_emits_state_and_message_events() -> None:
    adapter = DummyAdapter()
    events = []
    adapter.set_event_handler(events.append)
    config = TransportConfig(
        kind=TransportKind.SERIAL,
        name="Bench Port",
        target="COM3",
    )

    adapter.bind_session(config)
    adapter.emit_state(ConnectionState.CONNECTED)
    adapter.emit_message(MessageDirection.OUTBOUND, b"\x01\x03", {"format": "hex"})

    assert events[0].event_type == TransportEventType.STATE_CHANGED
    assert events[0].session.state == ConnectionState.CONNECTED
    assert events[1].event_type == TransportEventType.MESSAGE
    assert events[1].message.payload == b"\x01\x03"
    assert events[1].message.metadata["format"] == "hex"


def test_raw_transport_message_keeps_payload_untouched() -> None:
    message = RawTransportMessage(
        session_id="session-1",
        kind=TransportKind.TCP_CLIENT,
        direction=MessageDirection.INBOUND,
        payload=b"\x00\x10\xff",
    )

    assert message.payload == b"\x00\x10\xff"


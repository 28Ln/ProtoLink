from protolink.core.event_bus import EventBus
from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportKind
from protolink.core.wiring import bind_transport_to_event_bus
from tests.test_transport import DummyAdapter


def test_event_bus_publishes_to_subscribers() -> None:
    bus = EventBus()
    received = []

    bus.subscribe(str, received.append)
    bus.publish("hello")

    assert received == ["hello"]


def test_event_bus_isolates_handler_failures() -> None:
    bus = EventBus()
    received = []

    def broken_handler(_event: str) -> None:
        raise RuntimeError("handler failed")

    bus.subscribe(str, broken_handler)
    bus.subscribe(str, received.append)

    bus.publish("hello")

    assert received == ["hello"]
    assert len(bus.handler_errors) == 1
    assert bus.handler_errors[0].event_type is str
    assert bus.handler_errors[0].error == "handler failed"


def test_transport_can_publish_events_into_event_bus() -> None:
    bus = EventBus()
    adapter = DummyAdapter()
    received = []
    bus.subscribe(type_hint(), received.append)
    bind_transport_to_event_bus(adapter, bus)

    config = TransportConfig(kind=TransportKind.SERIAL, name="Bench", target="COM8")
    adapter.bind_session(config)
    adapter.emit_state(ConnectionState.CONNECTED)
    adapter.emit_message(MessageDirection.OUTBOUND, b"\xAA")

    assert len(received) == 2
    assert received[0].session.state == ConnectionState.CONNECTED
    assert received[1].message.payload == b"\xAA"


def type_hint():
    from protolink.core.transport import TransportEvent

    return TransportEvent

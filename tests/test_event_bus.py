import json

from protolink.core.event_bus import EventBus
from protolink.core.logging import RuntimeFailureEvidenceRecorder, default_runtime_failure_evidence_path
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


def test_event_bus_persists_handler_failures_when_recorder_is_configured(tmp_path) -> None:
    recorder = RuntimeFailureEvidenceRecorder(default_runtime_failure_evidence_path(tmp_path))
    bus = EventBus(
        failure_recorder=lambda error: recorder.append_handler_error(
            event_type=error.event_type.__name__,
            handler_name=getattr(error.handler, "__name__", repr(error.handler)),
            error=error.error,
        )
    )

    def broken_handler(_event: str) -> None:
        raise RuntimeError("handler failed")

    bus.subscribe(str, broken_handler)
    bus.publish("hello")

    lines = default_runtime_failure_evidence_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["source"] == "event_bus"
    assert payload["code"] == "event_handler_error"
    assert payload["message"] == "handler failed"
    assert payload["details"]["event_type"] == "str"


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

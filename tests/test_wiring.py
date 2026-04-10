from pathlib import Path

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportKind
from protolink.core.wiring import bind_transport_to_event_bus
from tests.test_transport import DummyAdapter


def test_transport_events_are_logged_through_event_bus(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    adapter = DummyAdapter()
    bind_transport_to_event_bus(adapter, context.event_bus)

    config = TransportConfig(kind=TransportKind.SERIAL, name="Bench", target="COM9")
    adapter.bind_session(config)
    adapter.emit_state(ConnectionState.CONNECTED)
    adapter.emit_message(MessageDirection.INBOUND, b"\x01\x03\x00\x01")

    entries = context.log_store.latest(2)

    assert entries[0].category == "transport.state"
    assert entries[1].category == "transport.message"
    assert entries[1].raw_payload == b"\x01\x03\x00\x01"
    workspace_log_path = context.workspace.logs / "transport-events.jsonl"
    assert workspace_log_path.exists()
    lines = workspace_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert '"category": "transport.message"' in lines[-1]

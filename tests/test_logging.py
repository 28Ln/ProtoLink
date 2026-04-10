import json

from protolink.core.logging import (
    InMemoryLogStore,
    LogLevel,
    WorkspaceJsonlLogWriter,
    create_log_entry_from_transport_event,
    default_workspace_log_path,
    serialize_log_entry,
)
from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    TransportEvent,
    TransportEventType,
    TransportKind,
    TransportSession,
)


def test_transport_message_event_becomes_structured_log_with_raw_payload() -> None:
    session = TransportSession.new(TransportKind.SERIAL, "Bench Port", "COM5").with_state(ConnectionState.CONNECTED)
    message_event = TransportEvent(
        event_type=TransportEventType.MESSAGE,
        session=session,
        message=session_message(session.session_id),
    )

    entry = create_log_entry_from_transport_event(message_event)

    assert entry.level == LogLevel.INFO
    assert entry.category == "transport.message"
    assert entry.raw_payload == b"\x01\x03\x00\x00"


def test_transport_error_event_becomes_error_log() -> None:
    session = TransportSession.new(TransportKind.TCP_CLIENT, "Bench TCP", "127.0.0.1:502")
    error_event = TransportEvent(
        event_type=TransportEventType.ERROR,
        session=session.with_state(ConnectionState.ERROR),
        error="Connection refused",
    )

    entry = create_log_entry_from_transport_event(error_event)

    assert entry.level == LogLevel.ERROR
    assert entry.category == "transport.error"
    assert entry.message == "Connection refused"


def test_in_memory_log_store_filters_by_session() -> None:
    store = InMemoryLogStore()
    session = TransportSession.new(TransportKind.UDP, "UDP Lab", "0.0.0.0:9000")
    entry = create_log_entry_from_transport_event(
        TransportEvent(
            event_type=TransportEventType.STATE_CHANGED,
            session=session.with_state(ConnectionState.CONNECTED),
        )
    )

    store.append(entry)

    assert len(store) == 1
    assert store.by_session(session.session_id)[0].session_id == session.session_id


def test_workspace_jsonl_log_writer_persists_serialized_entries(tmp_path) -> None:
    session = TransportSession.new(TransportKind.SERIAL, "Bench Port", "COM5").with_state(ConnectionState.CONNECTED)
    entry = create_log_entry_from_transport_event(
        TransportEvent(
            event_type=TransportEventType.MESSAGE,
            session=session,
            message=session_message(session.session_id),
        )
    )
    writer = WorkspaceJsonlLogWriter(default_workspace_log_path(tmp_path))

    writer.append(entry)

    payload = default_workspace_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(payload) == 1
    assert json.loads(payload[0]) == serialize_log_entry(entry)


def test_workspace_jsonl_log_writer_isolates_write_failures(tmp_path, monkeypatch) -> None:
    session = TransportSession.new(TransportKind.SERIAL, "Bench Port", "COM5").with_state(ConnectionState.CONNECTED)
    entry = create_log_entry_from_transport_event(
        TransportEvent(
            event_type=TransportEventType.MESSAGE,
            session=session,
            message=session_message(session.session_id),
        )
    )
    writer = WorkspaceJsonlLogWriter(default_workspace_log_path(tmp_path))

    def fail_open(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(type(writer.path), "open", fail_open)

    writer.append(entry)

    assert writer.failed_write_count == 1
    assert writer.last_error == "disk full"


def test_serialize_log_entry_truncates_large_raw_payload() -> None:
    session = TransportSession.new(TransportKind.SERIAL, "Bench Port", "COM5").with_state(ConnectionState.CONNECTED)
    entry = create_log_entry_from_transport_event(
        TransportEvent(
            event_type=TransportEventType.MESSAGE,
            session=session,
            message=session_message(session.session_id, payload=b"\xAA\xBB\xCC\xDD"),
        )
    )

    payload = serialize_log_entry(entry, max_raw_payload_bytes=2)

    assert payload["raw_payload_hex"] == "aabb"
    assert payload["metadata"] == {
        "format": "hex",
        "raw_payload_truncated": "true",
        "raw_payload_original_bytes": "4",
        "raw_payload_serialized_bytes": "2",
    }


def session_message(session_id: str, *, payload: bytes = b"\x01\x03\x00\x00"):
    from protolink.core.transport import RawTransportMessage

    return RawTransportMessage(
        session_id=session_id,
        kind=TransportKind.SERIAL,
        direction=MessageDirection.INBOUND,
        payload=payload,
        metadata={"format": "hex"},
    )

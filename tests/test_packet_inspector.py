from pathlib import Path

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.logging import LogLevel, StructuredLogEntry, create_log_entry
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.core.packet_inspector import PacketInspectorFilter, PacketInspectorState, PayloadViewMode
from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportKind
from protolink.core.wiring import bind_transport_to_event_bus
from tests.test_transport import DummyAdapter


def test_packet_inspector_renders_hex_ascii_and_utf8_views() -> None:
    inspector = PacketInspectorState()
    entry = create_log_entry(
        level=LogLevel.INFO,
        category="transport.message",
        message="Inbound payload",
        raw_payload=b"ABC\x00",
    )
    inspector.append(entry)

    assert inspector.selected_payload_text() == "41 42 43 00"

    inspector.set_payload_view_mode(PayloadViewMode.ASCII)
    assert inspector.selected_payload_text() == "ABC."

    inspector.set_payload_view_mode(PayloadViewMode.UTF8)
    assert inspector.selected_payload_text() == "ABC\u0000"


def test_packet_inspector_filters_by_category_and_text() -> None:
    inspector = PacketInspectorState()
    info_entry = create_log_entry(level=LogLevel.INFO, category="transport.state", message="Serial connected")
    error_entry = create_log_entry(level=LogLevel.ERROR, category="transport.error", message="Port denied")
    inspector.extend([info_entry, error_entry])

    inspector.set_filter(PacketInspectorFilter(category_query="error"))
    assert [row.entry_id for row in inspector.rows()] == [error_entry.entry_id]

    inspector.set_filter(PacketInspectorFilter(text_query="serial"))
    assert [row.entry_id for row in inspector.rows()] == [info_entry.entry_id]


def test_packet_inspector_tracks_sessions_and_reselects_visible_entries() -> None:
    inspector = PacketInspectorState()
    entry_a = create_log_entry(
        level=LogLevel.INFO,
        category="transport.state",
        message="Session A connected",
        session_id="session-a",
    )
    entry_b = create_log_entry(
        level=LogLevel.ERROR,
        category="transport.error",
        message="Session B failed",
        session_id="session-b",
    )
    inspector.extend([entry_a, entry_b])
    inspector.select(entry_a.entry_id)

    inspector.set_filter(PacketInspectorFilter(session_id="session-b"))

    assert inspector.available_session_ids() == ("session-a", "session-b")
    assert inspector.selected_entry_id == entry_b.entry_id
    assert inspector.filter_is_active() is True

    inspector.clear_filter()

    assert inspector.filter_is_active() is False


def test_packet_inspector_receives_logged_transport_entries_via_event_bus(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    adapter = DummyAdapter()
    bind_transport_to_event_bus(adapter, context.event_bus)

    config = TransportConfig(kind=TransportKind.SERIAL, name="Bench", target="COM7")
    adapter.bind_session(config)
    adapter.emit_state(ConnectionState.CONNECTED)
    adapter.emit_message(MessageDirection.INBOUND, b"\x01\x03\x00\x01")

    rows = context.packet_inspector.rows()

    assert len(rows) >= 2
    assert rows[-1].category == "transport.message"
    assert context.packet_inspector.selected_entry() is not None


def test_packet_inspector_exposes_selected_modbus_rtu_decode_text() -> None:
    inspector = PacketInspectorState()
    payload_without_crc = bytes([0x01, 0x03, 0x00, 0x0A, 0x00, 0x02])
    crc = crc16_modbus(payload_without_crc).to_bytes(2, "little")
    entry = create_log_entry(
        level=LogLevel.INFO,
        category="transport.message",
        message="Outbound payload (8 bytes)",
        raw_payload=payload_without_crc + crc,
    )
    inspector.append(entry)

    decode = inspector.selected_modbus_rtu_text()
    assert "Modbus RTU request" in decode
    assert "Function: 0x03" in decode


def test_packet_inspector_prefers_modbus_tcp_decode_when_mbap_is_present() -> None:
    inspector = PacketInspectorState()
    payload = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x0A, 0x00, 0x02])
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Outbound payload (12 bytes)",
            raw_payload=payload,
        )
    )

    decode = inspector.selected_protocol_decode_text()
    assert "Modbus TCP request" in decode
    assert "Transaction ID: 1" in decode

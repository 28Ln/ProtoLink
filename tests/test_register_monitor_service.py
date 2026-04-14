from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType


def test_register_monitor_service_can_upsert_decode_and_remove_point() -> None:
    service = RegisterMonitorService()
    service.upsert_point(
        name="Flow",
        address=300,
        data_type=RegisterDataType.FLOAT32,
        byte_order=RegisterByteOrder.CDAB,
        scale=1.0,
        offset=0.0,
        unit="L/s",
    )
    service.set_register_words_text("0x0000 0x3FC0")
    service.decode_current_words()

    assert service.snapshot.point_names == ("Flow",)
    assert service.snapshot.selected_point_name == "Flow"
    assert service.snapshot.decoded_value == "1.5 L/s"
    assert service.snapshot.last_error is None

    service.remove_point("Flow")
    assert service.snapshot.point_names == ()
    assert service.snapshot.selected_point_name is None


def test_register_monitor_service_validates_point_and_register_inputs() -> None:
    service = RegisterMonitorService()

    service.upsert_point(
        name="",
        address=10,
        data_type=RegisterDataType.UINT16,
        byte_order=RegisterByteOrder.AB,
        scale=1.0,
        offset=0.0,
    )
    assert service.snapshot.last_error == "点位名称不能为空。"

    service.upsert_point(
        name="Counter",
        address=10,
        data_type=RegisterDataType.UINT32,
        byte_order=RegisterByteOrder.AB,
        scale=1.0,
        offset=0.0,
    )
    service.set_register_words_text("0x0001")
    service.decode_current_words()
    assert "requires 2 register(s)" in (service.snapshot.last_error or "")

    service.set_register_words_text("xyz")
    service.decode_current_words()
    assert service.snapshot.last_error == "寄存器字“xyz”无效。"


def test_register_monitor_service_decodes_live_modbus_tcp_and_rtu_entries() -> None:
    event_bus = EventBus()
    service = RegisterMonitorService(event_bus)
    service.upsert_point(
        name="HoldingValue",
        address=10,
        data_type=RegisterDataType.UINT16,
        byte_order=RegisterByteOrder.AB,
        scale=1.0,
        offset=0.0,
        unit="rpm",
    )

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x11, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    assert service.snapshot.decoded_value == "42 rpm"
    assert service.snapshot.last_live_source == "Modbus TCP 响应"

    rtu_body = bytes([0x01, 0x03, 0x02, 0x00, 0x2B])
    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (7 bytes)",
            raw_payload=rtu_body + crc16_modbus(rtu_body).to_bytes(2, "little"),
        )
    )
    assert service.snapshot.decoded_value == "43 rpm"
    assert service.snapshot.last_live_source == "Modbus RTU 响应"


def test_register_monitor_service_filters_live_updates_by_bound_session_scope() -> None:
    event_bus = EventBus()
    service = RegisterMonitorService(event_bus)
    service.upsert_point(
        name="HoldingValue",
        address=10,
        data_type=RegisterDataType.UINT16,
        byte_order=RegisterByteOrder.AB,
        scale=1.0,
        offset=0.0,
        unit="rpm",
    )
    service.set_live_scope(transport_kind="tcp_client", session_id="session-a")

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            transport_kind="tcp_client",
            session_id="session-b",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x11, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    assert service.snapshot.decoded_value == ""

    event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            transport_kind="tcp_client",
            session_id="session-a",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x11, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    assert service.snapshot.decoded_value == "42 rpm"

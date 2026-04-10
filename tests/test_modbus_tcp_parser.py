from protolink.core.modbus_tcp_parser import (
    ModbusTcpFrameKind,
    parse_modbus_tcp_frame,
    render_modbus_tcp_result,
)


def test_modbus_tcp_parser_parses_read_request() -> None:
    # tx=1, protocol=0, length=6 (unit + func + 4 data)
    frame = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x0A, 0x00, 0x02])

    result = parse_modbus_tcp_frame(frame)

    assert result.is_frame is True
    assert result.kind == ModbusTcpFrameKind.REQUEST
    assert result.transaction_id == 1
    assert result.protocol_id == 0
    assert result.unit_id == 0x11
    assert result.function_code == 0x03
    assert "Quantity: 2" in render_modbus_tcp_result(result)


def test_modbus_tcp_parser_parses_exception_response() -> None:
    # tx=5, protocol=0, length=3 (unit + func + exception)
    frame = bytes([0x00, 0x05, 0x00, 0x00, 0x00, 0x03, 0x01, 0x83, 0x02])

    result = parse_modbus_tcp_frame(frame)

    assert result.is_frame is True
    assert result.kind == ModbusTcpFrameKind.EXCEPTION
    assert "Exception Code: 0x02" in render_modbus_tcp_result(result)


def test_modbus_tcp_parser_rejects_protocol_or_length_mismatch() -> None:
    bad_protocol = bytes([0x00, 0x01, 0x12, 0x34, 0x00, 0x03, 0x01, 0x03, 0x00])
    bad_length = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x0A])

    assert parse_modbus_tcp_frame(bad_protocol).is_frame is False
    mismatch = parse_modbus_tcp_frame(bad_length)
    assert mismatch.is_frame is False
    assert "length mismatch" in mismatch.summary

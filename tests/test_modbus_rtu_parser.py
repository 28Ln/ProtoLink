from protolink.core.modbus_rtu_parser import (
    ModbusRtuFrameKind,
    crc16_modbus,
    parse_modbus_rtu_frame,
    render_modbus_rtu_result,
)


def _frame(data: bytes) -> bytes:
    crc = crc16_modbus(data).to_bytes(2, "little")
    return data + crc


def test_modbus_rtu_parser_parses_read_request_with_crc() -> None:
    frame = _frame(bytes([0x01, 0x03, 0x00, 0x0A, 0x00, 0x02]))

    result = parse_modbus_rtu_frame(frame)

    assert result.is_frame is True
    assert result.crc_ok is True
    assert result.kind == ModbusRtuFrameKind.REQUEST
    assert result.address == 1
    assert result.function_code == 0x03
    assert "Quantity: 2" in render_modbus_rtu_result(result)


def test_modbus_rtu_parser_parses_exception_response() -> None:
    frame = _frame(bytes([0x11, 0x83, 0x02]))

    result = parse_modbus_rtu_frame(frame)

    assert result.is_frame is True
    assert result.crc_ok is True
    assert result.kind == ModbusRtuFrameKind.EXCEPTION
    assert "Exception Code: 0x02" in render_modbus_rtu_result(result)


def test_modbus_rtu_parser_flags_crc_mismatch_and_short_payload() -> None:
    valid = _frame(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x03]))
    broken = valid[:-1] + bytes([valid[-1] ^ 0xFF])
    mismatch = parse_modbus_rtu_frame(broken)
    short = parse_modbus_rtu_frame(b"\x01\x03\x00")

    assert mismatch.is_frame is True
    assert mismatch.crc_ok is False
    assert "MISMATCH" in render_modbus_rtu_result(mismatch)
    assert short.is_frame is False
    assert short.summary.startswith("Not a Modbus RTU frame")

from __future__ import annotations

from protolink.application.data_tools_service import DataToolMode, DataToolsService


def test_data_tools_service_runs_utf8_hex_and_crc_modes() -> None:
    service = DataToolsService()

    service.set_input_text("ProtoLink")
    assert service.run() == "50 72 6f 74 6f 4c 69 6e 6b"
    assert service.snapshot.output_text == "50 72 6f 74 6f 4c 69 6e 6b"

    service.set_mode(DataToolMode.HEX_MODBUS_CRC16)
    service.set_input_text("01 03 00 0A 00 02")
    assert service.run() == "e4 09"


def test_data_tools_service_runs_json_and_surfaces_errors() -> None:
    service = DataToolsService()
    service.set_mode(DataToolMode.PRETTY_JSON)
    service.set_input_text('{"b":2,"a":1}')
    assert service.run() == '{\n  "a": 1,\n  "b": 2\n}'

    service.set_mode(DataToolMode.HEX_TO_UTF8)
    service.set_input_text("zz")
    assert service.run() is None
    assert service.snapshot.last_error is not None

from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule, select_auto_response_action
from protolink.core.modbus_rtu_parser import crc16_modbus


def test_auto_response_selects_raw_bytes_rule() -> None:
    rules = (
        AutoResponseRule(
            name="Raw Ping",
            protocol=AutoResponseProtocol.RAW_BYTES,
            raw_match_payload=b"PING",
            response_payload=b"PONG",
        ),
    )

    action = select_auto_response_action(rules, b"PING")

    assert action is not None
    assert action.rule_name == "Raw Ping"
    assert action.response_payload == b"PONG"


def test_auto_response_matches_modbus_rtu_rule_and_rejects_bad_crc() -> None:
    request_body = bytes([0x01, 0x03, 0x00, 0x0A, 0x00, 0x01])
    request = request_body + crc16_modbus(request_body).to_bytes(2, "little")
    bad_crc = request[:-1] + bytes([request[-1] ^ 0xFF])
    rules = (
        AutoResponseRule(
            name="RTU Read Holding",
            protocol=AutoResponseProtocol.MODBUS_RTU,
            unit_id=1,
            function_code=0x03,
            data_prefix=b"\x00\x0A",
            response_payload=b"\x01\x03\x02\x00\x2A",
        ),
    )

    ok = select_auto_response_action(rules, request)
    bad = select_auto_response_action(rules, bad_crc)

    assert ok is not None
    assert ok.rule_name == "RTU Read Holding"
    assert bad is None


def test_auto_response_matches_modbus_tcp_rule() -> None:
    request = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x10, 0x00, 0x02])
    rules = (
        AutoResponseRule(
            name="TCP Read Holding",
            protocol=AutoResponseProtocol.MODBUS_TCP,
            unit_id=0x11,
            function_code=0x03,
            data_prefix=b"\x00\x10",
            response_payload=b"\x00\x01\x00\x00\x00\x07\x11\x03\x04\x00\x2A\x00\x2B",
        ),
    )

    action = select_auto_response_action(rules, request)

    assert action is not None
    assert action.rule_name == "TCP Read Holding"


def test_auto_response_uses_first_enabled_matching_rule() -> None:
    rules = (
        AutoResponseRule(
            name="Disabled Match",
            protocol=AutoResponseProtocol.RAW_BYTES,
            enabled=False,
            raw_match_payload=b"HELLO",
            response_payload=b"A",
        ),
        AutoResponseRule(
            name="Enabled Match",
            protocol=AutoResponseProtocol.RAW_BYTES,
            raw_match_payload=b"HELLO",
            response_payload=b"B",
        ),
    )

    action = select_auto_response_action(rules, b"HELLO")

    assert action is not None
    assert action.rule_name == "Enabled Match"
    assert action.response_payload == b"B"

from protolink.core.raw_packet_composer import (
    RawPacketComposerState,
    RawPacketInputMode,
    RawPacketLineEnding,
)


def test_raw_packet_composer_builds_hex_payload_with_line_ending() -> None:
    composer = RawPacketComposerState()
    composer.set_draft_text("01 03 00 10")
    composer.set_line_ending(RawPacketLineEnding.CRLF)

    snapshot = composer.snapshot
    assert snapshot.last_error is None
    assert snapshot.payload == b"\x01\x03\x00\x10\r\n"
    assert snapshot.payload_hex == "01 03 00 10 0D 0A"


def test_raw_packet_composer_surfaces_invalid_ascii_and_hex_errors() -> None:
    composer = RawPacketComposerState()
    composer.set_input_mode(RawPacketInputMode.ASCII)
    composer.set_draft_text("Ping\u4e2d")
    assert composer.snapshot.last_error == "ASCII 报文只能包含 7 位 ASCII 字符。"

    composer.set_input_mode(RawPacketInputMode.HEX)
    composer.set_draft_text("0")
    assert composer.snapshot.last_error == "HEX 报文必须由完整的十六进制字节组成。"


def test_raw_packet_composer_loads_existing_payload_as_hex_draft() -> None:
    composer = RawPacketComposerState()
    composer.set_input_mode(RawPacketInputMode.UTF8)
    composer.set_draft_text("abc")

    composer.load_payload(b"\x10\x20\x30")
    snapshot = composer.snapshot
    assert snapshot.input_mode == RawPacketInputMode.HEX
    assert snapshot.line_ending == RawPacketLineEnding.NONE
    assert snapshot.draft_text == "10 20 30"
    assert snapshot.payload == b"\x10\x20\x30"
    assert snapshot.last_error is None

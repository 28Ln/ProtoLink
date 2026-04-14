import time
from pathlib import Path

from protolink.application.serial_service import SerialLineEnding, SerialSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def test_serial_session_service_drives_loopback_open_send_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service
    service.set_target("loop://")
    service.set_baudrate("19200")
    service.set_send_mode(SerialSendEncoding.HEX)
    service.set_send_text("01 03 00 01")

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)

    service.send_current_payload()
    _wait_until(lambda: len([entry for entry in context.log_store.latest(10) if entry.category == "transport.message"]) >= 2)

    service.close_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    message_entries = [entry for entry in context.log_store.latest(10) if entry.category == "transport.message"]
    assert len(message_entries) >= 2
    assert context.packet_inspector.rows()
    service.shutdown()


def test_serial_session_service_requires_open_session_before_send(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service
    service.set_target("loop://")
    service.set_send_mode(SerialSendEncoding.HEX)
    service.set_send_text("0")

    service.send_current_payload()

    assert "发送前请先打开串口会话。" == service.snapshot.last_error
    service.shutdown()


def test_serial_session_service_surfaces_open_errors_in_snapshot_and_logs(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service
    service.set_target("missing://")

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.ERROR)

    assert service.snapshot.last_error is not None
    assert service.snapshot.last_error.startswith("打开失败：")
    assert any(entry.category == "transport.error" for entry in context.log_store.latest(10))
    service.shutdown()


def test_serial_session_service_persists_presets_and_applies_ascii_line_endings(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service
    service.set_target("loop://")
    service.set_baudrate("38400")
    service.set_send_mode(SerialSendEncoding.ASCII)
    service.set_line_ending(SerialLineEnding.CRLF)
    service.set_send_text("PING")
    service.save_preset("Bench Loop")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.serial_session_service
    assert reloaded.snapshot.preset_names == ("Bench Loop",)
    reloaded.load_preset("Bench Loop")

    assert reloaded.snapshot.selected_preset_name == "Bench Loop"
    assert reloaded.snapshot.send_mode == SerialSendEncoding.ASCII
    assert reloaded.snapshot.line_ending == SerialLineEnding.CRLF

    reloaded.open_session()
    _wait_until(lambda: reloaded.snapshot.connection_state == ConnectionState.CONNECTED)
    reloaded.send_current_payload()
    _wait_until(lambda: len([entry for entry in reloaded_context.log_store.latest(10) if entry.category == "transport.message"]) >= 2)

    payloads = [entry.raw_payload for entry in reloaded_context.log_store.latest(10) if entry.category == "transport.message"]
    assert b"PING\r\n" in payloads
    reloaded.close_session()
    _wait_until(lambda: reloaded.snapshot.connection_state == ConnectionState.DISCONNECTED)
    service.shutdown()
    reloaded.shutdown()

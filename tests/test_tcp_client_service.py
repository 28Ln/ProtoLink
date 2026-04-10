import socket
import time
from pathlib import Path

from protolink.application.tcp_client_service import TcpClientLineEnding, TcpClientSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from tests.support import TcpEchoServer


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def _find_unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_tcp_client_service_open_send_receive_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_client_service

    with TcpEchoServer() as server:
        service.set_host(server.host)
        service.set_port(server.port)
        service.set_send_mode(TcpClientSendEncoding.ASCII)
        service.set_line_ending(TcpClientLineEnding.CRLF)
        service.set_send_text("PING")

        service.open_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)

        service.send_current_payload()
        _wait_until(lambda: len([entry for entry in context.log_store.latest(10) if entry.category == "transport.message"]) >= 2)

        payloads = [entry.raw_payload for entry in context.log_store.latest(10) if entry.category == "transport.message"]
        assert b"PING\r\n" in payloads
        assert context.packet_inspector.rows()

        service.close_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    service.shutdown()


def test_tcp_client_service_surfaces_open_errors(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_client_service
    service.set_host("127.0.0.1")
    service.set_port(_find_unused_port())

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.ERROR)

    assert service.snapshot.last_error is not None
    assert service.snapshot.last_error.startswith("Open failed:")
    assert any(entry.category == "transport.error" for entry in context.log_store.latest(10))
    service.shutdown()


def test_tcp_client_service_persists_presets_and_applies_ascii_line_endings(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_client_service
    service.set_host("127.0.0.1")
    service.set_port(9001)
    service.set_send_mode(TcpClientSendEncoding.ASCII)
    service.set_line_ending(TcpClientLineEnding.CRLF)
    service.set_send_text("PING")
    service.save_preset("Bench Echo")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.tcp_client_service
    assert reloaded.snapshot.preset_names == ("Bench Echo",)
    reloaded.load_preset("Bench Echo")

    assert reloaded.snapshot.selected_preset_name == "Bench Echo"
    assert reloaded.snapshot.send_mode == TcpClientSendEncoding.ASCII
    assert reloaded.snapshot.line_ending == TcpClientLineEnding.CRLF

    with TcpEchoServer() as server:
        reloaded.set_host(server.host)
        reloaded.set_port(server.port)
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

import socket
import time
from pathlib import Path

from protolink.application.tcp_server_service import TcpServerLineEnding, TcpServerSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from tests.support import TcpSocketClient


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


def test_tcp_server_service_open_receive_broadcast_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_server_service
    listen_port = _find_unused_port()
    service.set_host("127.0.0.1")
    service.set_port(listen_port)
    service.set_send_mode(TcpServerSendEncoding.ASCII)
    service.set_line_ending(TcpServerLineEnding.CRLF)
    service.set_send_text("READY")

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)

    with TcpSocketClient("127.0.0.1", listen_port) as client:
        _wait_until(lambda: service.snapshot.client_count == 1)
        client.send(b"PING")
        _wait_until(lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 1)

        service.send_current_payload()
        assert client.recv() == b"READY\r\n"
        _wait_until(lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 2)

    _wait_until(lambda: service.snapshot.client_count == 0)
    service.close_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    service.shutdown()


def test_tcp_server_service_tracks_clients_and_can_target_single_peer(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_server_service
    listen_port = _find_unused_port()
    service.set_host("127.0.0.1")
    service.set_port(listen_port)
    service.set_send_mode(TcpServerSendEncoding.ASCII)
    service.set_send_text("TARGET")

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)

    with TcpSocketClient("127.0.0.1", listen_port) as client_a, TcpSocketClient("127.0.0.1", listen_port) as client_b:
        _wait_until(lambda: service.snapshot.client_count == 2)
        assert len(service.snapshot.connected_clients) == 2

        target_peer = service.snapshot.connected_clients[0]
        service.set_selected_client_peer(target_peer)
        service.send_current_payload()

        if client_a._socket.getsockname()[1] == int(target_peer.rsplit(":", 1)[1]):
            assert client_a.recv() == b"TARGET"
            client_b._socket.settimeout(0.2)
            try:
                payload = client_b.recv()
            except (TimeoutError, socket.timeout):
                payload = b""
            assert payload == b""
        else:
            assert client_b.recv() == b"TARGET"
            client_a._socket.settimeout(0.2)
            try:
                payload = client_a.recv()
            except (TimeoutError, socket.timeout):
                payload = b""
            assert payload == b""

    _wait_until(lambda: service.snapshot.client_count == 0)
    assert service.snapshot.selected_client_peer is None
    service.close_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    service.shutdown()


def test_tcp_server_service_surfaces_open_errors(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_server_service
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    listen_port = int(blocker.getsockname()[1])
    blocker.listen(1)

    try:
        service.set_host("127.0.0.1")
        service.set_port(listen_port)
        service.open_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.ERROR)

        assert service.snapshot.last_error is not None
        assert service.snapshot.last_error.startswith("打开失败：")
        assert any(entry.category == "transport.error" for entry in context.log_store.latest(10))
    finally:
        blocker.close()
        service.shutdown()


def test_tcp_server_service_persists_presets_and_reloads_send_defaults(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.tcp_server_service
    service.set_host("127.0.0.1")
    service.set_port(9012)
    service.set_send_mode(TcpServerSendEncoding.ASCII)
    service.set_line_ending(TcpServerLineEnding.CRLF)
    service.set_send_text("READY")
    service.save_preset("Bench Server")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.tcp_server_service
    assert reloaded.snapshot.preset_names == ("Bench Server",)
    reloaded.load_preset("Bench Server")

    assert reloaded.snapshot.selected_preset_name == "Bench Server"
    assert reloaded.snapshot.host == "127.0.0.1"
    assert reloaded.snapshot.port == 9012
    assert reloaded.snapshot.send_mode == TcpServerSendEncoding.ASCII
    assert reloaded.snapshot.line_ending == TcpServerLineEnding.CRLF
    assert reloaded.snapshot.send_text == "READY"

    service.shutdown()
    reloaded.shutdown()

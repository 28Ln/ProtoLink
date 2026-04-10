import socket
import time
from pathlib import Path

from protolink.application.udp_service import UdpLineEnding, UdpSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from tests.support import UdpEchoServer


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def test_udp_service_open_send_receive_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.udp_service

    with UdpEchoServer() as server:
        service.set_local_host("127.0.0.1")
        service.set_local_port(0)
        service.set_remote_host(server.host)
        service.set_remote_port(server.port)
        service.set_send_mode(UdpSendEncoding.ASCII)
        service.set_line_ending(UdpLineEnding.CRLF)
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


def test_udp_service_persists_presets_and_applies_ascii_line_endings(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.udp_service
    service.set_local_host("127.0.0.1")
    service.set_local_port(0)
    service.set_remote_host("127.0.0.1")
    service.set_remote_port(3000)
    service.set_send_mode(UdpSendEncoding.ASCII)
    service.set_line_ending(UdpLineEnding.CRLF)
    service.set_send_text("PING")
    service.save_preset("Bench UDP")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.udp_service
    assert reloaded.snapshot.preset_names == ("Bench UDP",)
    reloaded.load_preset("Bench UDP")

    assert reloaded.snapshot.selected_preset_name == "Bench UDP"
    assert reloaded.snapshot.send_mode == UdpSendEncoding.ASCII
    assert reloaded.snapshot.line_ending == UdpLineEnding.CRLF

    with UdpEchoServer() as server:
        reloaded.set_remote_host(server.host)
        reloaded.set_remote_port(server.port)
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

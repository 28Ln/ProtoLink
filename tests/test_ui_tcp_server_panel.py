from __future__ import annotations

import os
import socket

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.tcp_server_service import TcpServerLineEnding, TcpServerSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.tcp_server_panel import TcpServerPanel
from tests.support import TcpSocketClient


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _wait_until(qapp: QApplication, predicate, timeout: float = 3.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def test_tcp_server_panel_can_open_broadcast_and_close(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = TcpServerPanel(context.tcp_server_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(0)
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(TcpServerSendEncoding.ASCII.value))
    panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(TcpServerLineEnding.CRLF.value))
    panel.send_text.setPlainText("READY")
    panel.open_button.click()
    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.connection_state == ConnectionState.CONNECTED)

    bound_target = context.tcp_server_service._adapter.session.target  # type: ignore[attr-defined]
    host, port = bound_target.rsplit(":", 1)
    with TcpSocketClient(host, int(port)) as client:
        _wait_until(qapp, lambda: context.tcp_server_service.snapshot.client_count == 1)
        _wait_until(qapp, panel.send_button.isEnabled)
        panel.send_button.click()
        assert client.recv() == b"READY\r\n"

    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.client_count == 0)
    panel.close_button.click()
    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    context.tcp_server_service.shutdown()
    panel.close()


def test_tcp_server_panel_exposes_client_targets(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = TcpServerPanel(context.tcp_server_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(0)
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(TcpServerSendEncoding.ASCII.value))
    panel.send_text.setPlainText("TARGET")
    panel.open_button.click()
    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.connection_state == ConnectionState.CONNECTED)

    bound_target = context.tcp_server_service._adapter.session.target  # type: ignore[attr-defined]
    host, port = bound_target.rsplit(":", 1)
    with TcpSocketClient(host, int(port)) as client_a, TcpSocketClient(host, int(port)) as client_b:
        _wait_until(qapp, lambda: context.tcp_server_service.snapshot.client_count == 2)
        _wait_until(qapp, lambda: panel.client_target_combo.count() == 3)

        target_peer = context.tcp_server_service.snapshot.connected_clients[0]
        panel.client_target_combo.setCurrentIndex(panel.client_target_combo.findData(target_peer))
        qapp.processEvents()
        assert context.tcp_server_service.snapshot.selected_client_peer == target_peer

        panel.send_button.click()
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

    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.client_count == 0)
    context.tcp_server_service.shutdown()
    panel.close()


def test_tcp_server_panel_can_save_and_load_presets(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = TcpServerPanel(context.tcp_server_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(9022)
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(TcpServerSendEncoding.ASCII.value))
    panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(TcpServerLineEnding.CRLF.value))
    panel.send_text.setPlainText("READY")
    panel.preset_name_input.setText("Bench Server")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: context.tcp_server_service.snapshot.preset_names == ("Bench Server",))

    panel.host_input.setText("0.0.0.0")
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench Server"))
    qapp.processEvents()

    assert context.tcp_server_service.snapshot.selected_preset_name == "Bench Server"
    assert context.tcp_server_service.snapshot.host == "127.0.0.1"
    assert context.tcp_server_service.snapshot.port == 9022

    panel.delete_preset_button.click()
    qapp.processEvents()
    assert context.tcp_server_service.snapshot.preset_names == ()
    context.tcp_server_service.shutdown()
    panel.close()

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.udp_service import UdpLineEnding, UdpSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.udp_panel import UdpPanel
from tests.support import UdpEchoServer


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


def test_udp_panel_can_open_send_and_close(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = UdpPanel(context.udp_service)

    with UdpEchoServer() as server:
        panel.local_host_input.setText("127.0.0.1")
        panel.local_port_input.setValue(0)
        panel.remote_host_input.setText(server.host)
        panel.remote_port_input.setValue(server.port)
        panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(UdpSendEncoding.ASCII.value))
        panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(UdpLineEnding.CRLF.value))
        panel.send_text.setPlainText("PING")
        panel.open_button.click()
        _wait_until(qapp, lambda: context.udp_service.snapshot.connection_state == ConnectionState.CONNECTED)
        _wait_until(qapp, panel.send_button.isEnabled)

        panel.send_button.click()
        _wait_until(qapp, lambda: len([entry for entry in context.log_store.latest(10) if entry.category == "transport.message"]) >= 2)

        panel.close_button.click()
        _wait_until(qapp, lambda: context.udp_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.udp_service.shutdown()
    panel.close()


def test_udp_panel_can_save_and_load_preset(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = UdpPanel(context.udp_service)

    panel.local_host_input.setText("127.0.0.1")
    panel.local_port_input.setValue(2001)
    panel.remote_host_input.setText("127.0.0.1")
    panel.remote_port_input.setValue(3001)
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(UdpSendEncoding.ASCII.value))
    panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(UdpLineEnding.CRLF.value))
    panel.send_text.setPlainText("HELLO")
    panel.preset_name_input.setText("Bench UDP")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: "Bench UDP" in context.udp_service.snapshot.preset_names)

    panel.remote_host_input.setText("192.168.0.50")
    panel.preset_combo.setCurrentIndex(0)
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench UDP"))
    qapp.processEvents()

    assert context.udp_service.snapshot.selected_preset_name == "Bench UDP"
    assert context.udp_service.snapshot.remote_host == "127.0.0.1"
    assert context.udp_service.snapshot.send_mode == UdpSendEncoding.ASCII
    assert context.udp_service.snapshot.line_ending == UdpLineEnding.CRLF

    panel.delete_preset_button.click()
    _wait_until(qapp, lambda: "Bench UDP" not in context.udp_service.snapshot.preset_names)
    context.udp_service.shutdown()
    panel.close()

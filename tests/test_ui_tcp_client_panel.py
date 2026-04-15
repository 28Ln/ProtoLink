from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.tcp_client_service import TcpClientLineEnding, TcpClientSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.tcp_client_panel import TcpClientPanel
from tests.support import TcpEchoServer


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


def test_tcp_client_panel_can_open_send_and_close(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = TcpClientPanel(context.tcp_client_service)

    with TcpEchoServer() as server:
        panel.host_input.setText(server.host)
        panel.port_input.setValue(server.port)
        panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(TcpClientSendEncoding.ASCII.value))
        panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(TcpClientLineEnding.CRLF.value))
        panel.send_text.setPlainText("PING")
        panel.open_button.click()
        _wait_until(qapp, lambda: context.tcp_client_service.snapshot.connection_state == ConnectionState.CONNECTED)
        _wait_until(qapp, panel.send_button.isEnabled)

        panel.send_button.click()
        _wait_until(qapp, lambda: len([entry for entry in context.log_store.latest(10) if entry.category == "transport.message"]) >= 2)

        panel.close_button.click()
        _wait_until(qapp, lambda: context.tcp_client_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.tcp_client_service.shutdown()
    panel.close()


def test_tcp_client_panel_can_save_and_load_preset(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = TcpClientPanel(context.tcp_client_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(9002)
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(TcpClientSendEncoding.ASCII.value))
    panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(TcpClientLineEnding.CRLF.value))
    panel.send_text.setPlainText("HELLO")
    panel.preset_name_input.setText("Bench TCP")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: "Bench TCP" in context.tcp_client_service.snapshot.preset_names)

    panel.host_input.setText("192.168.0.10")
    panel.preset_combo.setCurrentIndex(0)
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench TCP"))
    qapp.processEvents()

    assert context.tcp_client_service.snapshot.selected_preset_name == "Bench TCP"
    assert context.tcp_client_service.snapshot.host == "127.0.0.1"
    assert context.tcp_client_service.snapshot.send_mode == TcpClientSendEncoding.ASCII
    assert context.tcp_client_service.snapshot.line_ending == TcpClientLineEnding.CRLF

    panel.delete_preset_button.click()
    _wait_until(qapp, lambda: "Bench TCP" not in context.tcp_client_service.snapshot.preset_names)
    context.tcp_client_service.shutdown()
    panel.close()


def test_tcp_client_panel_uses_tabbed_layout_for_compact_workspace(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = TcpClientPanel(context.tcp_client_service)
    panel.resize(1366, 768)
    panel.show()
    qapp.processEvents()

    assert panel.status_label.wordWrap() is True
    assert [panel.content_tabs.tabText(index) for index in range(panel.content_tabs.count())] == [
        "连接配置",
        "发送与预设",
    ]
    assert panel.minimumSizeHint().height() < 600
    assert panel.content_tabs.height() > 420

    context.tcp_client_service.shutdown()
    panel.close()

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtWidgets import QApplication

from protolink.application.serial_service import SerialLineEnding, SerialSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.serial_panel import SerialStudioPanel


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


def test_serial_panel_can_open_loopback_and_send_payload(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = SerialStudioPanel(context.serial_session_service)
    context.serial_session_service.set_target("loop://")
    qapp.processEvents()

    panel.baudrate_combo.setCurrentText("38400")
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(SerialSendEncoding.HEX))
    panel.send_text.setPlainText("01 03 00 01")
    panel.open_button.click()
    _wait_until(qapp, lambda: context.serial_session_service.snapshot.connection_state == ConnectionState.CONNECTED)
    _wait_until(qapp, panel.send_button.isEnabled)

    panel.send_button.click()
    _wait_until(qapp, lambda: len(context.log_store.latest(10)) >= 3)

    panel.close_button.click()
    _wait_until(qapp, lambda: context.serial_session_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.serial_session_service.shutdown()
    panel.close()


def test_serial_panel_can_save_and_load_preset(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = SerialStudioPanel(context.serial_session_service)

    panel.target_combo.setEditText("loop://")
    panel.baudrate_combo.setCurrentText("57600")
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(SerialSendEncoding.ASCII))
    panel.line_ending_combo.setCurrentIndex(panel.line_ending_combo.findData(SerialLineEnding.CRLF))
    panel.send_text.setPlainText("HELLO")
    panel.preset_name_input.setText("Bench ASCII")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: "Bench ASCII" in context.serial_session_service.snapshot.preset_names)

    panel.target_combo.setEditText("COM9")
    panel.preset_combo.setCurrentIndex(0)
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench ASCII"))
    qapp.processEvents()

    assert context.serial_session_service.snapshot.selected_preset_name == "Bench ASCII"
    assert context.serial_session_service.snapshot.target == "loop://"
    assert context.serial_session_service.snapshot.send_mode == SerialSendEncoding.ASCII
    assert context.serial_session_service.snapshot.line_ending == SerialLineEnding.CRLF

    panel.delete_preset_button.click()
    _wait_until(qapp, lambda: "Bench ASCII" not in context.serial_session_service.snapshot.preset_names)
    context.serial_session_service.shutdown()
    panel.close()


def test_serial_panel_uses_tabbed_layout_for_compact_workspace(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = SerialStudioPanel(context.serial_session_service)
    panel.resize(1366, 768)
    panel.show()
    qapp.processEvents()

    assert panel.status_label.wordWrap() is True
    assert [panel.content_tabs.tabText(index) for index in range(panel.content_tabs.count())] == [
        "连接配置",
        "负载与预设",
    ]
    assert panel.minimumSizeHint().height() < 560
    assert panel.content_tabs.height() > 420

    context.serial_session_service.shutdown()
    panel.close()

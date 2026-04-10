from __future__ import annotations

import os
import socket
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.mqtt_server_service import MqttServerSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.mqtt_server_panel import MqttServerPanel
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from tests.support import MqttExternalClient


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _wait_until(qapp: QApplication, predicate, timeout: float = 5.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def test_mqtt_server_panel_can_open_publish_and_close(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = MqttServerPanel(context.mqtt_server_service)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(port)
    panel.publish_topic_input.setText("bench/topic")
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(MqttServerSendEncoding.ASCII.value))
    panel.send_text.setPlainText("READY")
    panel.open_button.click()
    _wait_until(qapp, lambda: context.mqtt_server_service.snapshot.connection_state == ConnectionState.CONNECTED)

    with MqttExternalClient("127.0.0.1", port, client_id="external-mqtt") as client:
        client.subscribe("bench/topic")
        time.sleep(1.0)
        _wait_until(qapp, panel.send_button.isEnabled)
        panel.send_button.click()
        _wait_until(qapp, lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 2)
        topic, payload = client.recv(timeout=3.0)
        assert topic == "bench/topic"
        assert payload == b"READY"

    panel.close_button.click()
    _wait_until(qapp, lambda: context.mqtt_server_service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    context.mqtt_server_service.shutdown()
    panel.close()


def test_mqtt_server_panel_can_save_and_load_preset(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = MqttServerPanel(context.mqtt_server_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(1884)
    panel.publish_topic_input.setText("bench/out")
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(MqttServerSendEncoding.ASCII.value))
    panel.send_text.setPlainText("READY")
    panel.preset_name_input.setText("Bench Broker")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: "Bench Broker" in context.mqtt_server_service.snapshot.preset_names)

    panel.publish_topic_input.setText("override/topic")
    panel.preset_combo.setCurrentIndex(0)
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench Broker"))
    qapp.processEvents()

    assert context.mqtt_server_service.snapshot.selected_preset_name == "Bench Broker"
    assert context.mqtt_server_service.snapshot.publish_topic == "bench/out"
    assert context.mqtt_server_service.snapshot.send_mode == MqttServerSendEncoding.ASCII

    panel.delete_preset_button.click()
    _wait_until(qapp, lambda: "Bench Broker" not in context.mqtt_server_service.snapshot.preset_names)
    context.mqtt_server_service.shutdown()
    panel.close()

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.mqtt_client_service import MqttClientSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from protolink.ui.mqtt_client_panel import MqttClientPanel
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from tests.support import MqttTestBroker


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


def test_mqtt_client_panel_can_open_subscribe_publish_and_close(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = MqttClientPanel(context.mqtt_client_service)

    with MqttTestBroker() as broker:
        panel.host_input.setText(broker.host)
        panel.port_input.setValue(broker.port)
        panel.client_id_input.setText("bench-mqtt")
        panel.publish_topic_input.setText("bench/topic")
        panel.subscribe_topic_input.setText("bench/topic")
        panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(MqttClientSendEncoding.ASCII.value))
        panel.send_text.setPlainText("PING")
        panel.open_button.click()
        _wait_until(qapp, lambda: context.mqtt_client_service.snapshot.connection_state == ConnectionState.CONNECTED)
        _wait_until(qapp, panel.subscribe_button.isEnabled)

        panel.subscribe_button.click()
        _wait_until(qapp, lambda: "bench/topic" in context.mqtt_client_service.snapshot.subscribed_topics)
        panel.send_button.click()
        _wait_until(qapp, lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 3)

        panel.close_button.click()
        _wait_until(qapp, lambda: context.mqtt_client_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.mqtt_client_service.shutdown()
    panel.close()


def test_mqtt_client_panel_can_save_and_load_preset(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = MqttClientPanel(context.mqtt_client_service)

    panel.host_input.setText("127.0.0.1")
    panel.port_input.setValue(1883)
    panel.client_id_input.setText("bench-mqtt")
    panel.publish_topic_input.setText("bench/out")
    panel.subscribe_topic_input.setText("bench/in")
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(MqttClientSendEncoding.ASCII.value))
    panel.send_text.setPlainText("PING")
    panel.preset_name_input.setText("Bench MQTT")
    panel.save_preset_button.click()
    _wait_until(qapp, lambda: "Bench MQTT" in context.mqtt_client_service.snapshot.preset_names)

    panel.publish_topic_input.setText("override/topic")
    panel.preset_combo.setCurrentIndex(0)
    qapp.processEvents()
    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("Bench MQTT"))
    qapp.processEvents()

    assert context.mqtt_client_service.snapshot.selected_preset_name == "Bench MQTT"
    assert context.mqtt_client_service.snapshot.publish_topic == "bench/out"
    assert context.mqtt_client_service.snapshot.subscribe_topic == "bench/in"
    assert context.mqtt_client_service.snapshot.send_mode == MqttClientSendEncoding.ASCII

    panel.delete_preset_button.click()
    _wait_until(qapp, lambda: "Bench MQTT" not in context.mqtt_client_service.snapshot.preset_names)
    context.mqtt_client_service.shutdown()
    panel.close()


def test_mqtt_client_panel_uses_tabbed_layout_for_compact_workspace(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = MqttClientPanel(context.mqtt_client_service)
    panel.resize(1366, 768)
    panel.show()
    qapp.processEvents()

    assert panel.status_label.wordWrap() is True
    assert panel.subscribed_topics_label.wordWrap() is True
    assert [panel.content_tabs.tabText(index) for index in range(panel.content_tabs.count())] == [
        "连接配置",
        "主题订阅",
        "负载与预设",
    ]
    assert panel.minimumSizeHint().height() < 620
    assert panel.content_tabs.height() > 420

    context.mqtt_client_service.shutdown()
    panel.close()

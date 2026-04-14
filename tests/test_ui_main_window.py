from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.packet_inspector import PacketInspectorState
from protolink.presentation import APPLICATION_TITLE
from protolink.ui.main_window import ProtoLinkMainWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_exposes_packet_console_as_dock(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    window = ProtoLinkMainWindow(
        workspace=context.workspace,
        inspector=context.packet_inspector,
        data_tools_service=context.data_tools_service,
        network_tools_service=context.network_tools_service,
        serial_service=context.serial_session_service,
        mqtt_client_service=context.mqtt_client_service,
        mqtt_server_service=context.mqtt_server_service,
        tcp_client_service=context.tcp_client_service,
        tcp_server_service=context.tcp_server_service,
        udp_service=context.udp_service,
        packet_replay_service=context.packet_replay_service,
        register_monitor_service=context.register_monitor_service,
        rule_engine_service=context.rule_engine_service,
        auto_response_runtime_service=context.auto_response_runtime_service,
        script_console_service=context.script_console_service,
        timed_task_service=context.timed_task_service,
        channel_bridge_runtime_service=context.channel_bridge_runtime_service,
    )
    window.show()
    qapp.processEvents()

    dock = window.findChild(QDockWidget, "PacketInspectorDock")

    assert dock is not None
    assert dock.windowTitle() == "报文分析台"
    assert dock.widget() is window.packet_console
    labels = [label.text() for label in window.findChildren(QLabel)]
    assert any("docs/MAINLINE_STATUS.md" in text for text in labels)
    assert window.windowTitle() == APPLICATION_TITLE
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.title_bar.context_label.text() == "工作台总览"
    assert window.title_bar.maximize_button.text() == "□"
    modbus_rtu_index = next(index for index, module in enumerate(window.modules) if module.key == "modbus_rtu_lab")
    window.module_list.setCurrentRow(modbus_rtu_index)
    qapp.processEvents()
    assert window.name_label.text() == "Modbus RTU 调试台"
    assert window.title_bar.context_label.text() == "Modbus RTU 调试台"
    assert window.modbus_rtu_panel.isVisible() is True
    assert window.serial_panel.isVisible() is False
    tcp_index = next(index for index, module in enumerate(window.modules) if module.key == "tcp_client")
    window.module_list.setCurrentRow(tcp_index)
    qapp.processEvents()
    assert window.name_label.text() == "TCP 客户端"
    assert window.tcp_client_panel.isVisible() is True
    assert window.modbus_rtu_panel.isVisible() is False
    mqtt_index = next(index for index, module in enumerate(window.modules) if module.key == "mqtt_client")
    window.module_list.setCurrentRow(mqtt_index)
    qapp.processEvents()
    assert window.mqtt_client_panel.isVisible() is True
    assert window.tcp_client_panel.isVisible() is False
    mqtt_server_index = next(index for index, module in enumerate(window.modules) if module.key == "mqtt_server")
    window.module_list.setCurrentRow(mqtt_server_index)
    qapp.processEvents()
    assert window.mqtt_server_panel.isVisible() is True
    assert window.mqtt_client_panel.isVisible() is False
    modbus_tcp_index = next(index for index, module in enumerate(window.modules) if module.key == "modbus_tcp_lab")
    window.module_list.setCurrentRow(modbus_tcp_index)
    qapp.processEvents()
    assert window.modbus_tcp_panel.isVisible() is True
    assert window.mqtt_server_panel.isVisible() is False
    tcp_server_index = next(index for index, module in enumerate(window.modules) if module.key == "tcp_server")
    window.module_list.setCurrentRow(tcp_server_index)
    qapp.processEvents()
    assert window.tcp_server_panel.isVisible() is True
    assert window.modbus_tcp_panel.isVisible() is False
    udp_index = next(index for index, module in enumerate(window.modules) if module.key == "udp_lab")
    window.module_list.setCurrentRow(udp_index)
    qapp.processEvents()
    assert window.udp_panel.isVisible() is True
    assert window.tcp_server_panel.isVisible() is False
    register_index = next(index for index, module in enumerate(window.modules) if module.key == "register_monitor")
    window.module_list.setCurrentRow(register_index)
    qapp.processEvents()
    assert window.register_monitor_panel.isVisible() is True
    assert window.udp_panel.isVisible() is False
    automation_index = next(index for index, module in enumerate(window.modules) if module.key == "automation_rules")
    window.module_list.setCurrentRow(automation_index)
    qapp.processEvents()
    assert window.automation_rules_panel.isVisible() is True
    assert window.register_monitor_panel.isVisible() is False
    data_tools_index = next(index for index, module in enumerate(window.modules) if module.key == "data_tools")
    window.module_list.setCurrentRow(data_tools_index)
    qapp.processEvents()
    assert window.data_tools_panel.isVisible() is True
    assert window.automation_rules_panel.isVisible() is False
    network_tools_index = next(index for index, module in enumerate(window.modules) if module.key == "network_tools")
    window.module_list.setCurrentRow(network_tools_index)
    qapp.processEvents()
    assert window.name_label.text() == "网络诊断"
    assert window.network_tools_panel.isVisible() is True
    assert window.data_tools_panel.isVisible() is False
    script_index = next(index for index, module in enumerate(window.modules) if module.key == "script_console")
    window.module_list.setCurrentRow(script_index)
    qapp.processEvents()
    assert window.name_label.text() == "脚本控制台"
    assert window.script_console_panel is not None
    assert window.script_console_panel.isVisible() is True
    assert window.network_tools_panel.isVisible() is False
    context.serial_session_service.shutdown()
    context.mqtt_client_service.shutdown()
    context.mqtt_server_service.shutdown()
    context.tcp_client_service.shutdown()
    context.tcp_server_service.shutdown()
    context.udp_service.shutdown()
    context.packet_replay_service.shutdown()
    context.timed_task_service.shutdown()
    context.channel_bridge_runtime_service.shutdown()
    window.close()

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QWidget

from protolink.core.bootstrap import AppContext, bootstrap_app_context
from protolink.ui.main_window import ProtoLinkMainWindow
from protolink.ui.text import READY_TEXT


@dataclass(frozen=True, slots=True)
class OwnerSurfaceExpectation:
    module_name: str
    panel_attr: str
    notice_snippet: str


OWNER_SURFACES = (
    OwnerSurfaceExpectation(
        module_name="自动化规则",
        panel_attr="automation_rules_panel",
        notice_snippet="受控自动化",
    ),
    OwnerSurfaceExpectation(
        module_name="脚本控制台",
        panel_attr="script_console_panel",
        notice_snippet="受控执行",
    ),
    OwnerSurfaceExpectation(
        module_name="数据工具",
        panel_attr="data_tools_panel",
        notice_snippet="确定性辅助",
    ),
    OwnerSurfaceExpectation(
        module_name="网络诊断",
        panel_attr="network_tools_panel",
        notice_snippet="只读诊断",
    ),
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _build_window(tmp_path: Path) -> tuple[AppContext, ProtoLinkMainWindow]:
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
    return context, window


def _shutdown_context(context: AppContext) -> None:
    context.serial_session_service.shutdown()
    context.mqtt_client_service.shutdown()
    context.mqtt_server_service.shutdown()
    context.tcp_client_service.shutdown()
    context.tcp_server_service.shutdown()
    context.udp_service.shutdown()
    context.packet_replay_service.shutdown()
    context.timed_task_service.shutdown()
    context.channel_bridge_runtime_service.shutdown()


def _select_module(window: ProtoLinkMainWindow, module_name: str, qapp: QApplication) -> None:
    module_index = next(index for index, module in enumerate(window.modules) if module.name == module_name)
    window.module_list.setCurrentRow(module_index)
    qapp.processEvents()


def _section_titles(widget: QWidget) -> set[str]:
    return {
        label.text()
        for label in widget.findChildren(QLabel)
        if label.objectName() == "SectionTitle"
    }


def test_owner_surfaces_share_primary_chrome_status_and_boundary_guidance(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context, window = _build_window(tmp_path)
    owner_panels = {
        spec.module_name: getattr(window, spec.panel_attr)
        for spec in OWNER_SURFACES
    }

    try:
        for spec in OWNER_SURFACES:
            panel = owner_panels[spec.module_name]
            assert panel is not None

            _select_module(window, spec.module_name, qapp)

            visible_owner_surfaces = [
                name
                for name, candidate_panel in owner_panels.items()
                if candidate_panel is not None and candidate_panel.isVisible()
            ]

            assert visible_owner_surfaces == [spec.module_name]
            assert window.name_label.text() == spec.module_name
            assert spec.module_name in _section_titles(panel)
            assert any(frame.objectName() == "Panel" for frame in panel.findChildren(QFrame))
            assert panel.status_label.objectName() == "MetaLabel"
            assert re.search(r"\d+", panel.status_label.text())
            assert panel.notice_label.objectName() == "MetaLabel"
            assert panel.notice_label.wordWrap() is True
            assert spec.notice_snippet in panel.notice_label.text()
            assert panel.error_label.objectName() == "MetaLabel"
            assert panel.error_label.text() == READY_TEXT

            if spec.panel_attr == "automation_rules_panel":
                assert panel.run_button.isEnabled() is False
                assert panel.clear_jobs_button.isEnabled() is False
            elif spec.panel_attr in {"script_console_panel", "data_tools_panel"}:
                assert panel.run_button.isEnabled() is False
            elif spec.panel_attr == "network_tools_panel":
                assert panel.resolve_button.isEnabled() is True
                assert panel.probe_button.isEnabled() is True
                panel.host_input.clear()
                qapp.processEvents()
                assert panel.resolve_button.isEnabled() is False
                assert panel.probe_button.isEnabled() is False
                panel.host_input.setText("127.0.0.1")
                qapp.processEvents()
                assert panel.resolve_button.isEnabled() is True
                assert panel.probe_button.isEnabled() is True
    finally:
        window.close()
        _shutdown_context(context)

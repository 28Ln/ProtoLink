from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.packet_replay import PacketReplayPlan, PacketReplayStep, ReplayDirection, save_packet_replay_plan
from protolink.core.rule_engine import AutomationActionKind
from protolink.core.script_host import ScriptLanguage
from protolink.core.timed_tasks import TimedTask
from protolink.core.transport import TransportKind
from protolink.ui.automation_rules_panel import AutomationRulesPanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_automation_rules_panel_can_save_and_run_replay_rule(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = AutomationRulesPanel(context.rule_engine_service)
    assert panel.notice_label.wordWrap() is True
    assert panel.run_button.isEnabled() is False
    assert panel.clear_jobs_button.isEnabled() is False
    replay_path = tmp_path / "plan.json"
    save_packet_replay_plan(
        replay_path,
        PacketReplayPlan(
            name="ui-panel-replay",
            created_at=context.packet_replay_service.snapshot.started_at or datetime.now(UTC),
            steps=(PacketReplayStep(delay_ms=0, payload=b"PING", direction=ReplayDirection.OUTBOUND),),
        ),
    )

    panel.name_input.setText("Replay Rule")
    panel.action_combo.setCurrentIndex(panel.action_combo.findData(AutomationActionKind.RUN_REPLAY_PLAN))
    panel.replay_path_input.setText(str(replay_path))
    panel.replay_target_combo.setCurrentIndex(panel.replay_target_combo.findData(TransportKind.TCP_CLIENT))
    panel.save_button.click()
    qapp.processEvents()

    assert context.rule_engine_service.snapshot.rule_names == ("Replay Rule",)
    assert panel.run_button.isEnabled() is False

    panel.rule_combo.setCurrentIndex(panel.rule_combo.findData("Replay Rule"))
    qapp.processEvents()
    assert panel.run_button.isEnabled() is True
    panel.run_button.click()
    qapp.processEvents()

    assert context.rule_engine_service.snapshot.last_run_rule_name == "Replay Rule"
    panel.close()


def test_automation_rules_panel_can_save_scan_rule_and_clear_jobs(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = AutomationRulesPanel(context.rule_engine_service)
    assert panel.clear_jobs_button.isEnabled() is False

    panel.name_input.setText("Scan Rule")
    panel.action_combo.setCurrentIndex(panel.action_combo.findData(AutomationActionKind.PREPARE_DEVICE_SCAN))
    panel.scan_target_input.setText("127.0.0.1:502")
    panel.scan_unit_start.setValue(1)
    panel.scan_unit_end.setValue(2)
    panel.save_button.click()
    qapp.processEvents()

    panel.rule_combo.setCurrentIndex(panel.rule_combo.findData("Scan Rule"))
    qapp.processEvents()
    assert panel.run_button.isEnabled() is True
    panel.run_button.click()
    qapp.processEvents()
    assert context.rule_engine_service.snapshot.prepared_device_scan_job_count == 1
    assert panel.clear_jobs_button.isEnabled() is True

    panel.clear_jobs_button.click()
    qapp.processEvents()
    assert context.rule_engine_service.snapshot.prepared_device_scan_job_count == 0
    assert panel.clear_jobs_button.isEnabled() is False
    panel.close()


def test_automation_rules_panel_exposes_runtime_safety_controls(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    context.auto_response_runtime_service.set_rules(
        (
            AutoResponseRule(
                name="Ping Rule",
                protocol=AutoResponseProtocol.RAW_BYTES,
                raw_match_payload=b"PING",
                response_payload=b"PONG",
            ),
        )
    )
    context.timed_task_service.set_tasks((TimedTask(name="Heartbeat", rule_name="Ping Rule", interval_seconds=1.0),))
    context.channel_bridge_runtime_service.set_bridges(
        (
            ChannelBridgeConfig(
                name="UDP->TCP",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="result = payload",
            ),
        )
    )

    panel = AutomationRulesPanel(
        context.rule_engine_service,
        auto_response_service=context.auto_response_runtime_service,
        timed_task_service=context.timed_task_service,
        channel_bridge_service=context.channel_bridge_runtime_service,
    )
    qapp.processEvents()

    assert "自动响应：" in panel.auto_response_status_label.text()
    assert "定时任务：" in panel.timed_task_status_label.text()
    assert "通道桥：" in panel.channel_bridge_status_label.text()
    assert "受控自动化" in panel.notice_label.text()

    panel.disable_auto_response_button.click()
    qapp.processEvents()
    assert context.auto_response_runtime_service.snapshot.enabled is False

    panel.start_timed_tasks_button.click()
    qapp.processEvents()
    assert context.timed_task_service.snapshot.running is True

    panel.stop_timed_tasks_button.click()
    qapp.processEvents()
    assert context.timed_task_service.snapshot.running is False

    panel.clear_bridges_button.click()
    qapp.processEvents()
    assert context.channel_bridge_runtime_service.snapshot.bridge_names == ()

    panel.close()
    context.timed_task_service.shutdown()
    context.channel_bridge_runtime_service.shutdown()

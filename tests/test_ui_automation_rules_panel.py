from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.packet_replay import PacketReplayPlan, PacketReplayStep, ReplayDirection, save_packet_replay_plan
from protolink.core.rule_engine import AutomationActionKind
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

    panel.rule_combo.setCurrentIndex(panel.rule_combo.findData("Replay Rule"))
    panel.run_button.click()
    qapp.processEvents()

    assert context.rule_engine_service.snapshot.last_run_rule_name == "Replay Rule"
    panel.close()


def test_automation_rules_panel_can_save_scan_rule_and_clear_jobs(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = AutomationRulesPanel(context.rule_engine_service)

    panel.name_input.setText("Scan Rule")
    panel.action_combo.setCurrentIndex(panel.action_combo.findData(AutomationActionKind.PREPARE_DEVICE_SCAN))
    panel.scan_target_input.setText("127.0.0.1:502")
    panel.scan_unit_start.setValue(1)
    panel.scan_unit_end.setValue(2)
    panel.save_button.click()
    qapp.processEvents()

    panel.rule_combo.setCurrentIndex(panel.rule_combo.findData("Scan Rule"))
    panel.run_button.click()
    qapp.processEvents()
    assert context.rule_engine_service.snapshot.prepared_device_scan_job_count == 1

    panel.clear_jobs_button.click()
    qapp.processEvents()
    assert context.rule_engine_service.snapshot.prepared_device_scan_job_count == 0
    panel.close()

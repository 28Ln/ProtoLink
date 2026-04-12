from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.core.bootstrap import bootstrap_app_context
from protolink.ui.script_console_panel import ScriptConsolePanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_script_console_panel_runs_script_and_persists_workspace_artifact(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = ScriptConsolePanel(context.script_console_service)
    assert panel.notice_label.wordWrap() is True
    assert panel.run_button.isEnabled() is False

    panel.context_input.setText('{"value": 21}')
    panel.code_input.setPlainText("print(value * 2)\nresult = value + 1")
    qapp.processEvents()
    assert panel.run_button.isEnabled() is True
    panel.run_button.click()
    qapp.processEvents()

    assert panel.output_text.toPlainText().strip() == "42"
    assert panel.result_label.text() == "22"
    assert context.script_console_service.snapshot.last_script_file is not None
    assert Path(context.script_console_service.snapshot.last_script_file).exists()
    assert "Controlled execution only" in panel.notice_label.text()
    panel.close()

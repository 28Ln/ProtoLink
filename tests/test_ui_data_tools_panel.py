from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.data_tools_service import DataToolMode, DataToolsService
from protolink.ui.data_tools_panel import DataToolsPanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_data_tools_panel_runs_selected_tool(qapp: QApplication) -> None:
    service = DataToolsService()
    panel = DataToolsPanel(service)
    assert panel.notice_label.wordWrap() is True
    assert panel.run_button.isEnabled() is False

    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(DataToolMode.UTF8_TO_BASE64))
    panel.input_text.setPlainText("ProtoLink")
    qapp.processEvents()
    assert panel.run_button.isEnabled() is True
    panel.run_button.click()
    qapp.processEvents()

    assert panel.output_text.toPlainText() == "UHJvdG9MaW5r"
    assert "No live transport session is required" in panel.notice_label.text()
    panel.close()

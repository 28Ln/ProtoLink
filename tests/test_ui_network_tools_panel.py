from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.network_tools_service import NetworkToolsService
from protolink.ui.network_tools_panel import NetworkToolsPanel
from tests.support import TcpEchoServer


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_network_tools_panel_runs_resolve_and_probe(qapp: QApplication) -> None:
    service = NetworkToolsService()
    panel = NetworkToolsPanel(service)
    assert panel.notice_label is panel.read_only_notice
    assert panel.notice_label.wordWrap() is True
    assert "执行次数: 0" in panel.status_label.text()
    assert panel.resolve_button.isEnabled() is True
    assert panel.probe_button.isEnabled() is True
    with TcpEchoServer() as server:
        panel.host_input.clear()
        qapp.processEvents()
        assert panel.resolve_button.isEnabled() is False
        assert panel.probe_button.isEnabled() is False
        panel.host_input.setText(server.host)
        panel.port_spin.setValue(server.port)
        qapp.processEvents()
        assert panel.resolve_button.isEnabled() is True
        assert panel.probe_button.isEnabled() is True
        panel.resolve_button.click()
        qapp.processEvents()
        panel.probe_button.click()
        qapp.processEvents()
        assert panel.resolve_text.toPlainText()
        assert "reachable" in panel.probe_label.text().lower() or "可达" in panel.probe_label.text()
        assert "只读诊断面板" in panel.notice_label.text()
    panel.close()

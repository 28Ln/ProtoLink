from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.logging import default_workspace_log_path
from protolink.core.transport import ConnectionState
from protolink.ui.modbus_tcp_panel import ModbusTcpLabPanel
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from tests.support import TcpEchoServer


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
    raise AssertionError("Timed out waiting for acceptance condition.")


def test_modbus_tcp_workflow_acceptance_path(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = ModbusTcpLabPanel(
        context.tcp_client_service,
        context.register_monitor_service,
        context.packet_inspector,
        replay_service=context.packet_replay_service,
        workspace=context.workspace,
    )

    with TcpEchoServer() as server:
        context.tcp_client_service.set_host(server.host)
        context.tcp_client_service.set_port(server.port)
        qapp.processEvents()
        context.tcp_client_service.open_session()
        _wait_until(qapp, lambda: context.tcp_client_service.snapshot.connection_state == ConnectionState.CONNECTED)
        _wait_until(qapp, panel.send_request_button.isEnabled)

        log_path = default_workspace_log_path(context.workspace.logs)
        panel.transaction_id_spin.setValue(7)
        panel.unit_id_spin.setValue(1)
        panel.start_address_spin.setValue(30)
        panel.quantity_spin.setValue(2)
        panel.send_request_button.click()
        _wait_until(qapp, lambda: bool(server.received_payloads()))
        _wait_until(qapp, lambda: log_path.exists())
        _wait_until(qapp, lambda: "transport.message" in log_path.read_text(encoding="utf-8"))

        panel.replay_plan_name_input.setText("mtcp-acceptance")
        panel.export_replay_button.click()
        qapp.processEvents()
        replay_path = Path(panel.replay_file_input.text())
        assert replay_path.exists()
        assert replay_path.parent == context.workspace.captures

        panel.export_capture_bundle_button.click()
        qapp.processEvents()
        export_dirs = sorted(context.workspace.exports.iterdir())
        assert export_dirs
        latest_bundle = export_dirs[-1]
        assert latest_bundle.joinpath("manifest.json").exists()
        payload_files = [path for path in latest_bundle.iterdir() if path.name != "manifest.json"]
        assert len(payload_files) == 1
        assert payload_files[0].read_bytes() == replay_path.read_bytes()

        count_before = len(server.received_payloads())
        panel.run_replay_button.click()
        _wait_until(
            qapp,
            lambda: (
                context.packet_replay_service.snapshot.running is False
                and context.packet_replay_service.snapshot.dispatched_steps == 1
            ),
        )
        _wait_until(qapp, lambda: len(server.received_payloads()) > count_before)
        assert "Replay completed:" in panel.replay_status_label.text()

        context.tcp_client_service.close_session()
        _wait_until(qapp, lambda: context.tcp_client_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.tcp_client_service.shutdown()
    context.packet_replay_service.shutdown()
    panel.close()

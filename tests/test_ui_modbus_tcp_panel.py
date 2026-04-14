from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.packet_replay_service import PacketReplayExecutionSnapshot
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.application.tcp_client_service import TcpClientSessionSnapshot
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.transport import ConnectionState
from protolink.core.workspace import ensure_workspace_layout
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
    raise AssertionError("Timed out waiting for condition.")


@dataclass
class _TcpClientServiceStub:
    snapshot: TcpClientSessionSnapshot

    def __post_init__(self) -> None:
        self.calls: list[tuple[bytes, dict[str, str] | None]] = []
        self._listeners = []

    def subscribe(self, listener):
        self._listeners.append(listener)
        listener(self.snapshot)
        return lambda: None

    def send_replay_payload(self, payload: bytes, metadata=None) -> None:
        self.calls.append((payload, dict(metadata or {})))


class _ReplayServiceStub:
    def __init__(self) -> None:
        self.snapshot = PacketReplayExecutionSnapshot()
        self.calls: list[tuple[str, str]] = []
        self._listeners = []

    def subscribe(self, listener):
        self._listeners.append(listener)
        listener(self.snapshot)
        return lambda: None

    def execute_saved_plan(self, path, target_kind) -> None:
        self.calls.append((str(path), getattr(target_kind, "value", str(target_kind))))
        self.snapshot = PacketReplayExecutionSnapshot(
            running=False,
            plan_name=Path(path).stem,
            target_kind=target_kind,
            total_steps=1,
            dispatched_steps=1,
            skipped_steps=0,
        )
        for listener in list(self._listeners):
            listener(self.snapshot)


def test_modbus_tcp_panel_can_preview_and_send_request(qapp: QApplication) -> None:
    tcp_service = _TcpClientServiceStub(
        TcpClientSessionSnapshot(
            host="127.0.0.1",
            port=502,
            connection_state=ConnectionState.CONNECTED,
            active_session_id="bench-session",
        )
    )
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    panel = ModbusTcpLabPanel(tcp_service, register_monitor, inspector)  # type: ignore[arg-type]

    panel.transaction_id_spin.setValue(3)
    panel.unit_id_spin.setValue(17)
    panel.start_address_spin.setValue(10)
    panel.quantity_spin.setValue(2)
    qapp.processEvents()

    assert "00 03 00 00 00 06 11 03 00 0A 00 02" in panel.request_preview.toPlainText()

    panel.send_request_button.click()
    qapp.processEvents()

    assert len(tcp_service.calls) == 1
    assert tcp_service.calls[0][0] == bytes([0x00, 0x03, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x0A, 0x00, 0x02])
    assert tcp_service.calls[0][1]["source"] == "modbus_tcp_lab"
    panel.close()


def test_modbus_tcp_panel_can_seed_register_monitor_and_render_decode(qapp: QApplication) -> None:
    tcp_service = _TcpClientServiceStub(TcpClientSessionSnapshot())
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    panel = ModbusTcpLabPanel(tcp_service, register_monitor, inspector)  # type: ignore[arg-type]

    panel.point_name_input.setText("TCP Holding Value")
    panel.start_address_spin.setValue(300)
    panel.apply_point_button.click()
    qapp.processEvents()

    assert register_monitor.snapshot.point_names == ("TCP Holding Value",)
    assert register_monitor.snapshot.selected_point_name == "TCP Holding Value"

    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (11 bytes)",
            raw_payload=bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x11, 0x03, 0x02, 0x00, 0x2A]),
        )
    )
    qapp.processEvents()

    assert "Modbus TCP response" in panel.decode_preview.toPlainText()
    panel.close()


def test_modbus_tcp_panel_can_export_and_run_replay_plan(qapp: QApplication, tmp_path: Path) -> None:
    tcp_service = _TcpClientServiceStub(
        TcpClientSessionSnapshot(
            host="127.0.0.1",
            port=502,
            connection_state=ConnectionState.CONNECTED,
            active_session_id="bench-session",
        )
    )
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    replay_service = _ReplayServiceStub()
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    panel = ModbusTcpLabPanel(
        tcp_service,  # type: ignore[arg-type]
        register_monitor,
        inspector,
        replay_service=replay_service,  # type: ignore[arg-type]
        workspace=workspace,
    )

    panel.replay_plan_name_input.setText("mtcp replay")
    panel.export_replay_button.click()
    qapp.processEvents()
    replay_path = Path(panel.replay_file_input.text())
    assert replay_path.exists()

    panel.export_capture_bundle_button.click()
    qapp.processEvents()
    export_dirs = sorted(workspace.exports.iterdir())
    assert export_dirs
    assert any(path.name != "manifest.json" for path in export_dirs[-1].iterdir())

    panel.run_replay_button.click()
    qapp.processEvents()
    assert replay_service.calls == [(str(replay_path), "tcp_client")]
    assert "回放完成：" in panel.replay_status_label.text()
    panel.close()


def test_modbus_tcp_panel_end_to_end_workflow_can_send_export_and_replay(qapp: QApplication, tmp_path: Path) -> None:
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

        panel.transaction_id_spin.setValue(5)
        panel.unit_id_spin.setValue(1)
        panel.start_address_spin.setValue(20)
        panel.quantity_spin.setValue(2)
        panel.send_request_button.click()
        _wait_until(qapp, lambda: bool(server.received_payloads()))

        panel.replay_plan_name_input.setText("mtcp-e2e")
        panel.export_replay_button.click()
        qapp.processEvents()
        replay_path = Path(panel.replay_file_input.text())
        assert replay_path.exists()

        panel.export_capture_bundle_button.click()
        qapp.processEvents()
        assert any(context.workspace.exports.iterdir())

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
        assert "回放完成：" in panel.replay_status_label.text()

        context.tcp_client_service.close_session()
        _wait_until(qapp, lambda: context.tcp_client_service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    context.tcp_client_service.shutdown()
    context.packet_replay_service.shutdown()
    panel.close()

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.packet_replay_service import PacketReplayExecutionSnapshot
from protolink.application.serial_service import SerialSessionSnapshot
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.transport import ConnectionState
from protolink.core.workspace import ensure_workspace_layout
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.modbus_rtu_panel import ModbusRtuLabPanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _wait_until(qapp: QApplication, predicate, timeout: float = 3.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


@dataclass
class _SerialServiceStub:
    snapshot: SerialSessionSnapshot

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


def test_modbus_rtu_panel_can_preview_and_send_request(qapp: QApplication) -> None:
    serial_service = _SerialServiceStub(
        SerialSessionSnapshot(
            target="loop://",
            connection_state=ConnectionState.CONNECTED,
            active_session_id="bench-session",
        )
    )
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    panel = ModbusRtuLabPanel(serial_service, register_monitor, inspector)  # type: ignore[arg-type]

    panel.unit_id_spin.setValue(17)
    panel.start_address_spin.setValue(10)
    panel.quantity_spin.setValue(2)
    qapp.processEvents()

    assert "11 03 00 0A 00 02" in panel.request_preview.toPlainText()

    panel.send_request_button.click()
    qapp.processEvents()

    assert len(serial_service.calls) == 1
    assert serial_service.calls[0][0][:6] == bytes([0x11, 0x03, 0x00, 0x0A, 0x00, 0x02])
    assert serial_service.calls[0][1]["source"] == "modbus_rtu_lab"
    panel.close()


def test_modbus_rtu_panel_can_export_and_run_replay_plan(qapp: QApplication, tmp_path: Path) -> None:
    serial_service = _SerialServiceStub(
        SerialSessionSnapshot(
            target="loop://",
            connection_state=ConnectionState.CONNECTED,
            active_session_id="bench-session",
        )
    )
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    replay_service = _ReplayServiceStub()
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    panel = ModbusRtuLabPanel(
        serial_service,  # type: ignore[arg-type]
        register_monitor,
        inspector,
        replay_service=replay_service,  # type: ignore[arg-type]
        workspace=workspace,
    )

    panel.replay_plan_name_input.setText("bench replay")
    panel.unit_id_spin.setValue(3)
    panel.start_address_spin.setValue(40)
    panel.quantity_spin.setValue(1)
    panel.export_replay_button.click()
    qapp.processEvents()

    replay_path = Path(panel.replay_file_input.text())
    assert replay_path.exists()
    assert replay_path.parent == workspace.captures
    assert "已导出回放计划：" in panel.replay_status_label.text()

    panel.run_replay_button.click()
    qapp.processEvents()

    assert replay_service.calls == [(str(replay_path), "serial")]
    assert "回放完成：" in panel.replay_status_label.text()
    panel.close()


def test_modbus_rtu_panel_can_export_capture_bundle_from_saved_replay(qapp: QApplication, tmp_path: Path) -> None:
    serial_service = _SerialServiceStub(
        SerialSessionSnapshot(
            target="loop://",
            connection_state=ConnectionState.CONNECTED,
            active_session_id="bench-session",
        )
    )
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    replay_service = _ReplayServiceStub()
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    panel = ModbusRtuLabPanel(
        serial_service,  # type: ignore[arg-type]
        register_monitor,
        inspector,
        replay_service=replay_service,  # type: ignore[arg-type]
        workspace=workspace,
    )

    panel.replay_plan_name_input.setText("capture bundle")
    panel.export_replay_button.click()
    qapp.processEvents()
    replay_path = Path(panel.replay_file_input.text())
    assert replay_path.exists()

    panel.export_capture_bundle_button.click()
    qapp.processEvents()

    export_dirs = sorted(workspace.exports.iterdir())
    assert export_dirs
    payload_files = [path for path in export_dirs[-1].iterdir() if path.name != "manifest.json"]
    assert len(payload_files) == 1
    assert payload_files[0].read_bytes() == replay_path.read_bytes()
    assert "抓包已导出：" in panel.replay_status_label.text()
    panel.close()


def test_modbus_rtu_panel_can_seed_register_monitor_and_render_decode(qapp: QApplication) -> None:
    serial_service = _SerialServiceStub(SerialSessionSnapshot())
    register_monitor = RegisterMonitorService()
    inspector = PacketInspectorState()
    panel = ModbusRtuLabPanel(serial_service, register_monitor, inspector)  # type: ignore[arg-type]

    panel.point_name_input.setText("Holding Value")
    panel.start_address_spin.setValue(300)
    panel.apply_point_button.click()
    qapp.processEvents()

    assert register_monitor.snapshot.point_names == ("Holding Value",)
    assert register_monitor.snapshot.selected_point_name == "Holding Value"

    body = bytes([0x01, 0x03, 0x02, 0x00, 0x2A])
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (7 bytes)",
            raw_payload=body + crc16_modbus(body).to_bytes(2, "little"),
        )
    )
    qapp.processEvents()

    assert "Modbus RTU response" in panel.decode_preview.toPlainText()
    panel.close()


def test_modbus_rtu_panel_end_to_end_workflow_can_send_export_and_replay(qapp: QApplication, tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    panel = ModbusRtuLabPanel(
        context.serial_session_service,
        context.register_monitor_service,
        context.packet_inspector,
        replay_service=context.packet_replay_service,
        workspace=context.workspace,
    )

    context.serial_session_service.set_target("loop://")
    qapp.processEvents()
    context.serial_session_service.open_session()
    _wait_until(qapp, lambda: context.serial_session_service.snapshot.connection_state == ConnectionState.CONNECTED)
    _wait_until(qapp, panel.send_request_button.isEnabled)

    log_count_before_send = len(context.log_store.latest(200))
    panel.unit_id_spin.setValue(1)
    panel.start_address_spin.setValue(10)
    panel.quantity_spin.setValue(2)
    panel.send_request_button.click()
    _wait_until(qapp, lambda: len(context.log_store.latest(200)) > log_count_before_send)

    panel.replay_plan_name_input.setText("rtu-e2e")
    panel.export_replay_button.click()
    qapp.processEvents()
    replay_path = Path(panel.replay_file_input.text())
    assert replay_path.exists()

    panel.export_capture_bundle_button.click()
    qapp.processEvents()
    export_dirs = sorted(context.workspace.exports.iterdir())
    assert export_dirs
    assert any(path.name != "manifest.json" for path in export_dirs[-1].iterdir())

    log_count_before_replay = len(context.log_store.latest(400))
    panel.run_replay_button.click()
    _wait_until(
        qapp,
        lambda: (
            context.packet_replay_service.snapshot.running is False
            and context.packet_replay_service.snapshot.dispatched_steps == 1
        ),
        timeout=5.0,
    )
    _wait_until(qapp, lambda: len(context.log_store.latest(400)) > log_count_before_replay, timeout=5.0)

    assert "回放完成：" in panel.replay_status_label.text()
    assert replay_path.parent == context.workspace.captures

    context.serial_session_service.close_session()
    _wait_until(qapp, lambda: context.serial_session_service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    context.serial_session_service.shutdown()
    context.packet_replay_service.shutdown()
    panel.close()

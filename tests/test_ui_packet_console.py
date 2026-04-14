import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.application.packet_replay_service import PacketReplayExecutionSnapshot
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.core.packet_inspector import PacketInspectorState, PayloadViewMode
from protolink.core.packet_replay import load_packet_replay_plan
from protolink.core.raw_packet_composer import RawPacketInputMode, RawPacketLineEnding
from protolink.core.transport import TransportKind
from protolink.core.workspace import ensure_workspace_layout
from protolink.ui.packet_console import PacketConsoleWidget


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def cleanup_widgets(qapp: QApplication):
    yield
    for widget in QApplication.topLevelWidgets():
        try:
            if hasattr(widget, "close"):
                widget.close()
            if hasattr(widget, "deleteLater"):
                widget.deleteLater()
        except (AttributeError, RuntimeError):
            continue
    qapp.processEvents()


def test_packet_console_filter_controls_drive_inspector_state(qapp: QApplication) -> None:
    inspector = PacketInspectorState()
    inspector.extend(
        [
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.state",
                message="Serial connected",
                session_id="session-a",
                raw_payload=b"ABC",
            ),
            create_log_entry(
                level=LogLevel.ERROR,
                category="transport.error",
                message="CRC mismatch",
                session_id="session-b",
                raw_payload=b"\x10\x20",
            ),
        ]
    )

    widget = PacketConsoleWidget(inspector)

    widget.level_filter.setCurrentIndex(widget.level_filter.findData(LogLevel.ERROR))
    qapp.processEvents()
    assert inspector.filter.level == LogLevel.ERROR
    assert widget.entry_list.count() == 1

    widget.session_filter.setCurrentIndex(widget.session_filter.findData("session-b"))
    qapp.processEvents()
    assert inspector.filter.session_id == "session-b"

    widget.category_filter.setText("error")
    qapp.processEvents()
    assert inspector.filter.category_query == "error"

    widget.text_filter.setText("crc")
    qapp.processEvents()
    assert inspector.filter.text_query == "crc"

    widget.clear_filters_button.click()
    qapp.processEvents()

    assert inspector.filter.level is None
    assert inspector.filter.session_id is None
    assert inspector.filter.category_query == ""
    assert inspector.filter.text_query == ""
    assert widget.entry_list.count() == 2
    widget.close()


def test_packet_console_view_mode_control_updates_payload_mode(qapp: QApplication) -> None:
    inspector = PacketInspectorState()
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Loopback payload",
            raw_payload=b"ABC",
        )
    )
    widget = PacketConsoleWidget(inspector)

    widget.view_mode.setCurrentIndex(widget.view_mode.findData(PayloadViewMode.ASCII.value))
    qapp.processEvents()
    assert inspector.payload_view_mode == PayloadViewMode.ASCII
    assert widget.payload_text.toPlainText() == "ABC"

    widget.view_mode.setCurrentIndex(widget.view_mode.findData(PayloadViewMode.UTF8.value))
    qapp.processEvents()
    assert inspector.payload_view_mode == PayloadViewMode.UTF8
    widget.close()


def test_packet_console_composer_controls_build_payload_preview(qapp: QApplication) -> None:
    inspector = PacketInspectorState()
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Loopback payload",
            raw_payload=b"\x10\x20",
        )
    )
    widget = PacketConsoleWidget(inspector)

    widget.composer_mode.setCurrentIndex(widget.composer_mode.findData(RawPacketInputMode.ASCII))
    widget.composer_line_ending.setCurrentIndex(widget.composer_line_ending.findData(RawPacketLineEnding.CRLF))
    widget.composer_input.setPlainText("PING")
    qapp.processEvents()
    assert widget.composer.snapshot.payload == b"PING\r\n"
    assert "50 49 4E 47 0D 0A" in widget.composer_preview.toPlainText()

    widget.load_selected_payload_button.click()
    qapp.processEvents()
    assert widget.composer.snapshot.input_mode == RawPacketInputMode.HEX
    assert widget.composer.snapshot.draft_text == "10 20"
    assert widget.composer.snapshot.payload == b"\x10\x20"
    widget.close()


def test_packet_console_renders_modbus_rtu_decode_panel(qapp: QApplication) -> None:
    payload_without_crc = bytes([0x01, 0x03, 0x00, 0x0A, 0x00, 0x02])
    payload = payload_without_crc + crc16_modbus(payload_without_crc).to_bytes(2, "little")
    inspector = PacketInspectorState()
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Modbus request",
            raw_payload=payload,
        )
    )
    widget = PacketConsoleWidget(inspector)
    qapp.processEvents()

    assert "Modbus RTU request" in widget.modbus_text.toPlainText()
    assert "Function: 0x03" in widget.modbus_text.toPlainText()
    widget.close()


def test_packet_console_renders_modbus_tcp_decode_panel(qapp: QApplication) -> None:
    inspector = PacketInspectorState()
    payload = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x11, 0x03, 0x00, 0x0A, 0x00, 0x02])
    inspector.append(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Modbus TCP request",
            raw_payload=payload,
        )
    )
    widget = PacketConsoleWidget(inspector)
    qapp.processEvents()

    assert "Modbus TCP request" in widget.modbus_text.toPlainText()
    assert "Transaction ID: 1" in widget.modbus_text.toPlainText()
    widget.close()


class _ReplayServiceStub:
    def __init__(self) -> None:
        self.snapshot = PacketReplayExecutionSnapshot()
        self.calls: list[tuple[str, TransportKind]] = []
        self._listeners = []

    def subscribe(self, listener):
        self._listeners.append(listener)
        listener(self.snapshot)
        return lambda: None

    def execute_saved_plan(self, path, target_kind: TransportKind) -> None:
        self.calls.append((str(path), target_kind))
        self.snapshot = PacketReplayExecutionSnapshot(
            running=False,
            plan_name="bench",
            target_kind=target_kind,
            total_steps=2,
            dispatched_steps=2,
            skipped_steps=0,
        )
        for listener in list(self._listeners):
            listener(self.snapshot)


def test_packet_console_replay_controls_dispatch_saved_plan(qapp: QApplication, tmp_path) -> None:
    inspector = PacketInspectorState()
    replay_service = _ReplayServiceStub()
    widget = PacketConsoleWidget(inspector, replay_service=replay_service)
    plan_path = tmp_path / "bench-plan.json"
    plan_path.write_text("{}", encoding="utf-8")

    widget.replay_file_input.setText(str(plan_path))
    widget.replay_target_combo.setCurrentIndex(widget.replay_target_combo.findData(TransportKind.TCP_CLIENT))
    widget.replay_run_button.click()
    qapp.processEvents()

    assert replay_service.calls == [(str(plan_path), TransportKind.TCP_CLIENT)]
    assert "重放完成：bench" in widget.replay_status_label.text()
    widget.close()


def test_packet_console_can_build_replay_plan_from_visible_rows(qapp: QApplication, tmp_path) -> None:
    inspector = PacketInspectorState()
    inspector.extend(
        [
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Outbound payload (4 bytes)",
                raw_payload=b"PING",
            ),
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                raw_payload=b"PONG",
            ),
        ]
    )
    replay_service = _ReplayServiceStub()
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    widget = PacketConsoleWidget(inspector, replay_service=replay_service, workspace=workspace)

    widget.replay_plan_name_input.setText("bench-capture")
    widget.replay_direction_combo.setCurrentIndex(widget.replay_direction_combo.findData("outbound_only"))
    widget.replay_build_button.click()
    qapp.processEvents()

    built_path = Path(widget.replay_file_input.text())
    plan = load_packet_replay_plan(built_path)
    assert len(plan.steps) == 1
    assert plan.steps[0].payload == b"PING"
    assert "重放计划构建完成：" in widget.replay_status_label.text()
    widget.close()

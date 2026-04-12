from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.packet_replay_service import PacketReplayExecutionService, PacketReplayExecutionSnapshot
from protolink.application.register_monitor_service import RegisterMonitorService, RegisterMonitorSnapshot
from protolink.application.serial_service import SerialSessionService, SerialSessionSnapshot
from protolink.core.device_scan import build_modbus_rtu_probe_request
from protolink.core.import_export import sanitize_artifact_name
from protolink.core.import_export import ArtifactKind, build_export_bundle_plan, materialize_export_bundle_from_file
from protolink.core.logging import render_payload_hex
from protolink.core.modbus_rtu_parser import parse_modbus_rtu_frame, render_modbus_rtu_result
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.packet_replay import (
    PacketReplayPlan,
    PacketReplayStep,
    ReplayDirection,
    default_packet_replay_path,
    save_packet_replay_plan,
)
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.core.transport import ConnectionState, TransportKind
from protolink.core.workspace import WorkspaceLayout


class ModbusRtuLabPanel(QWidget):
    def __init__(
        self,
        serial_service: SerialSessionService,
        register_monitor_service: RegisterMonitorService,
        inspector: PacketInspectorState,
        *,
        replay_service: PacketReplayExecutionService | None = None,
        workspace: WorkspaceLayout | None = None,
    ) -> None:
        super().__init__()
        self.serial_service = serial_service
        self.register_monitor_service = register_monitor_service
        self.inspector = inspector
        self.replay_service = replay_service
        self.workspace = workspace
        self._syncing_controls = False
        self._last_action_text = "Ready."
        self._build_ui()
        self.serial_service.subscribe(self._refresh_serial_state)
        self.register_monitor_service.subscribe(self._refresh_monitor_state)
        self.inspector.subscribe(self._refresh_decode_preview)
        if self.replay_service is not None:
            self.replay_service.subscribe(self._on_replay_snapshot)
        self._refresh_request_preview()
        self._refresh_serial_state(self.serial_service.snapshot)
        self._refresh_monitor_state(self.register_monitor_service.snapshot)
        self._refresh_decode_preview()
        if self.replay_service is None or self.workspace is None:
            self._set_replay_controls_enabled(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame = QFrame()
        frame.setObjectName("Panel")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(18, 18, 18, 18)
        frame_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Modbus RTU Lab")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.unit_id_spin = QSpinBox()
        self.unit_id_spin.setRange(0, 247)
        self.unit_id_spin.setValue(1)
        self.unit_id_spin.valueChanged.connect(self._refresh_request_preview)

        self.function_combo = QComboBox()
        self.function_combo.addItem("Read Holding Registers (0x03)", 0x03)
        self.function_combo.addItem("Read Input Registers (0x04)", 0x04)
        self.function_combo.currentIndexChanged.connect(self._refresh_request_preview)

        self.start_address_spin = QSpinBox()
        self.start_address_spin.setRange(0, 65535)
        self.start_address_spin.valueChanged.connect(self._refresh_request_preview)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 125)
        self.quantity_spin.setValue(2)
        self.quantity_spin.valueChanged.connect(self._refresh_request_preview)

        self.send_request_button = QPushButton("Send RTU Request")
        self.send_request_button.clicked.connect(self._on_send_request)

        self.point_name_input = QLineEdit()
        self.point_name_input.setPlaceholderText("Register point name")

        self.data_type_combo = QComboBox()
        for data_type in RegisterDataType:
            self.data_type_combo.addItem(data_type.value, data_type)

        self.byte_order_combo = QComboBox()
        for byte_order in RegisterByteOrder:
            self.byte_order_combo.addItem(byte_order.value, byte_order)

        self.scale_input = QLineEdit("1.0")
        self.offset_input = QLineEdit("0.0")
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("unit")
        self.apply_point_button = QPushButton("Save Point at Start Address")
        self.apply_point_button.clicked.connect(self._on_apply_point)

        self.request_preview = QTextEdit()
        self.request_preview.setReadOnly(True)

        self.decode_preview = QTextEdit()
        self.decode_preview.setReadOnly(True)

        self.replay_plan_name_input = QLineEdit("modbus-rtu-request")
        self.replay_file_input = QLineEdit()
        self.replay_file_input.setPlaceholderText("Replay plan path")
        self.replay_file_input.setReadOnly(True)
        self.export_replay_button = QPushButton("Export Current Request Replay")
        self.export_replay_button.clicked.connect(self._on_export_replay_plan)
        self.run_replay_button = QPushButton("Run Saved Replay")
        self.run_replay_button.clicked.connect(self._on_run_replay)
        self.export_capture_bundle_button = QPushButton("Export Capture Bundle")
        self.export_capture_bundle_button.clicked.connect(self._on_export_capture_bundle)
        self.replay_status_label = QLabel("Replay: idle.")
        self.replay_status_label.setObjectName("MetaLabel")
        self.replay_status_label.setWordWrap(True)

        self.workflow_hint = QLabel(
            "Workflow hint: send requests here, inspect raw bytes in the Packet Inspector dock, export the current RTU "
            "request into a replay plan, replay it through the active serial session, and use the saved point below to "
            "watch inbound Modbus RTU values."
        )
        self.workflow_hint.setObjectName("MetaLabel")
        self.workflow_hint.setWordWrap(True)

        self.monitor_summary_label = QLabel()
        self.monitor_summary_label.setObjectName("MetaLabel")
        self.monitor_summary_label.setWordWrap(True)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("Unit ID"), 0, 0)
        grid.addWidget(self.unit_id_spin, 0, 1)
        grid.addWidget(QLabel("Function"), 0, 2)
        grid.addWidget(self.function_combo, 0, 3)
        grid.addWidget(QLabel("Start Address"), 1, 0)
        grid.addWidget(self.start_address_spin, 1, 1)
        grid.addWidget(QLabel("Quantity"), 1, 2)
        grid.addWidget(self.quantity_spin, 1, 3)
        grid.addWidget(self.send_request_button, 1, 4)
        grid.addWidget(QLabel("Point Name"), 2, 0)
        grid.addWidget(self.point_name_input, 2, 1)
        grid.addWidget(QLabel("Data Type"), 2, 2)
        grid.addWidget(self.data_type_combo, 2, 3)
        grid.addWidget(QLabel("Byte Order"), 3, 0)
        grid.addWidget(self.byte_order_combo, 3, 1)
        grid.addWidget(QLabel("Scale"), 3, 2)
        grid.addWidget(self.scale_input, 3, 3)
        grid.addWidget(QLabel("Offset"), 4, 0)
        grid.addWidget(self.offset_input, 4, 1)
        grid.addWidget(QLabel("Unit"), 4, 2)
        grid.addWidget(self.unit_input, 4, 3)
        grid.addWidget(self.apply_point_button, 4, 4)

        frame_layout.addLayout(header_layout)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(QLabel("Request Preview"))
        frame_layout.addWidget(self.request_preview)
        frame_layout.addWidget(QLabel("Replay Plan Name"))
        frame_layout.addWidget(self.replay_plan_name_input)
        replay_controls = QHBoxLayout()
        replay_controls.addWidget(self.export_replay_button)
        replay_controls.addWidget(self.run_replay_button)
        replay_controls.addWidget(self.export_capture_bundle_button)
        frame_layout.addLayout(replay_controls)
        frame_layout.addWidget(self.replay_file_input)
        frame_layout.addWidget(self.replay_status_label)
        frame_layout.addWidget(QLabel("Selected Packet Decode"))
        frame_layout.addWidget(self.decode_preview)
        frame_layout.addWidget(self.workflow_hint)
        frame_layout.addWidget(self.monitor_summary_label)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def _refresh_request_preview(self) -> None:
        payload = self._build_request_payload()
        self.request_preview.setPlainText(
            "\n".join(
                (
                    render_payload_hex(payload),
                    "",
                    render_modbus_rtu_result(parse_modbus_rtu_frame(payload)),
                )
            )
        )

    def _refresh_serial_state(self, snapshot: SerialSessionSnapshot) -> None:
        state_label = snapshot.connection_state.value.upper()
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        target_label = snapshot.target or "-"
        self.register_monitor_service.set_live_scope(
            transport_kind=TransportKind.SERIAL.value if snapshot.connection_state == ConnectionState.CONNECTED else None,
            session_id=snapshot.active_session_id if snapshot.connection_state == ConnectionState.CONNECTED else None,
        )
        self.status_label.setText(
            f"Serial: {state_label}    Target: {target_label}    Session: {session_label}"
        )
        self.send_request_button.setEnabled(snapshot.connection_state == ConnectionState.CONNECTED)
        self.run_replay_button.setEnabled(
            snapshot.connection_state == ConnectionState.CONNECTED
            and bool(self.replay_file_input.text().strip())
            and self.replay_service is not None
        )
        self._refresh_error_label(snapshot.last_error)

    def _refresh_monitor_state(self, snapshot: RegisterMonitorSnapshot) -> None:
        selected_point = snapshot.selected_point_name or "-"
        decoded_value = snapshot.decoded_value or "-"
        source = snapshot.last_live_source or "-"
        self.monitor_summary_label.setText(
            f"Register Monitor: point={selected_point}    source={source}    decoded={decoded_value}"
        )
        self._refresh_error_label(snapshot.last_error)

    def _refresh_decode_preview(self) -> None:
        self.decode_preview.setPlainText(self.inspector.selected_protocol_decode_text())

    def _refresh_error_label(self, latest_error: str | None) -> None:
        if latest_error:
            self.error_label.setText(latest_error)
            return
        self.error_label.setText(self._last_action_text)

    def _on_send_request(self) -> None:
        payload = self._build_request_payload()
        function_code = self._current_function_code()
        self.register_monitor_service.set_live_scope(
            transport_kind=TransportKind.SERIAL.value,
            session_id=self.serial_service.snapshot.active_session_id,
        )
        self.serial_service.send_replay_payload(
            payload,
            {
                "source": "modbus_rtu_lab",
                "protocol": "modbus_rtu",
                "unit_id": str(self.unit_id_spin.value()),
                "function_code": f"0x{function_code:02X}",
                "start_address": str(self.start_address_spin.value()),
                "quantity": str(self.quantity_spin.value()),
            },
        )
        self._last_action_text = (
            f"Dispatched Modbus RTU request: unit={self.unit_id_spin.value()} "
            f"func=0x{function_code:02X} start={self.start_address_spin.value()} qty={self.quantity_spin.value()}"
        )
        self._refresh_error_label(self.serial_service.snapshot.last_error)

    def _on_apply_point(self) -> None:
        point_name = " ".join(self.point_name_input.text().strip().split())
        if not point_name:
            point_name = f"RTU {self.start_address_spin.value()}"
            self.point_name_input.setText(point_name)

        data_type = self.data_type_combo.currentData()
        byte_order = self.byte_order_combo.currentData()
        if not isinstance(data_type, RegisterDataType):
            data_type = RegisterDataType(str(data_type))
        if not isinstance(byte_order, RegisterByteOrder):
            byte_order = RegisterByteOrder(str(byte_order))

        self.register_monitor_service.upsert_point(
            name=point_name,
            address=self.start_address_spin.value(),
            data_type=data_type,
            byte_order=byte_order,
            scale=self.scale_input.text(),
            offset=self.offset_input.text(),
            unit=self.unit_input.text(),
        )
        self._last_action_text = (
            f"Saved register point '{point_name}' at address {self.start_address_spin.value()} for RTU monitoring."
        )
        self._refresh_error_label(self.register_monitor_service.snapshot.last_error)

    def _on_export_replay_plan(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("Replay export requires a workspace.")
            return

        plan_name = sanitize_artifact_name(self.replay_plan_name_input.text().strip() or "modbus-rtu-request")
        payload = self._build_request_payload()
        function_code = self._current_function_code()
        plan = PacketReplayPlan(
            name=plan_name,
            created_at=datetime.now(UTC),
            steps=(
                PacketReplayStep(
                    delay_ms=0,
                    payload=payload,
                    direction=ReplayDirection.OUTBOUND,
                    transport_kind=TransportKind.SERIAL.value,
                    metadata={
                        "source": "modbus_rtu_lab",
                        "protocol": "modbus_rtu",
                        "unit_id": str(self.unit_id_spin.value()),
                        "function_code": f"0x{function_code:02X}",
                        "start_address": str(self.start_address_spin.value()),
                        "quantity": str(self.quantity_spin.value()),
                    },
                    source_message="Modbus RTU Lab exported request",
                ),
            ),
        )
        plan_path = default_packet_replay_path(self.workspace.captures, plan.name, created_at=plan.created_at)
        save_packet_replay_plan(plan_path, plan)
        self.replay_file_input.setText(str(plan_path))
        self.replay_status_label.setText(f"Replay plan exported: {plan_path.name}")
        self.run_replay_button.setEnabled(self.serial_service.snapshot.connection_state == ConnectionState.CONNECTED)
        self.export_capture_bundle_button.setEnabled(self.workspace is not None)

    def _on_run_replay(self) -> None:
        if self.replay_service is None:
            self.replay_status_label.setText("Replay service is unavailable.")
            return
        replay_path = self.replay_file_input.text().strip()
        if not replay_path:
            self.replay_status_label.setText("Export or choose a replay plan before running.")
            return
        try:
            self.replay_service.execute_saved_plan(replay_path, TransportKind.SERIAL)
        except Exception as exc:
            self.replay_status_label.setText(f"Replay start failed: {exc}")

    def _on_export_capture_bundle(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("Capture export requires a workspace.")
            return
        replay_path_text = self.replay_file_input.text().strip()
        if not replay_path_text:
            self.replay_status_label.setText("Export a replay plan before packaging a capture bundle.")
            return
        replay_path = Path(replay_path_text)
        plan_name = sanitize_artifact_name(self.replay_plan_name_input.text().strip() or replay_path.stem)
        plan = build_export_bundle_plan(
            self.workspace,
            ArtifactKind.CAPTURE,
            plan_name,
            replay_path.suffix or ".json",
        )
        try:
            manifest = materialize_export_bundle_from_file(plan, replay_path)
        except Exception as exc:
            self.replay_status_label.setText(f"Capture export failed: {exc}")
            return
        self.replay_status_label.setText(
            f"Capture bundle exported: {plan.bundle_dir.name} -> {manifest['payload_file']}"
        )

    def _on_replay_snapshot(self, snapshot: PacketReplayExecutionSnapshot) -> None:
        if snapshot.target_kind not in {None, TransportKind.SERIAL}:
            return
        if snapshot.running:
            self.replay_status_label.setText(
                f"Replay running: {snapshot.dispatched_steps}/{snapshot.total_steps}    plan={snapshot.plan_name or '-'}"
            )
            self._set_replay_controls_enabled(False)
            return
        self._set_replay_controls_enabled(True)
        if snapshot.last_error:
            self.replay_status_label.setText(f"Replay error: {snapshot.last_error}")
            return
        if snapshot.plan_name and snapshot.dispatched_steps >= snapshot.total_steps and snapshot.total_steps > 0:
            self.replay_status_label.setText(
                f"Replay completed: {snapshot.plan_name}    {snapshot.dispatched_steps}/{snapshot.total_steps}"
            )
            return
        if self.replay_service is not None:
            self.replay_status_label.setText("Replay: idle.")

    def _set_replay_controls_enabled(self, enabled: bool) -> None:
        has_workspace = self.workspace is not None
        self.replay_plan_name_input.setEnabled(enabled and has_workspace)
        self.export_replay_button.setEnabled(enabled and has_workspace)
        self.export_capture_bundle_button.setEnabled(enabled and has_workspace and bool(self.replay_file_input.text().strip()))
        self.run_replay_button.setEnabled(
            enabled
            and self.replay_service is not None
            and self.serial_service.snapshot.connection_state == ConnectionState.CONNECTED
            and bool(self.replay_file_input.text().strip())
        )

    def _build_request_payload(self) -> bytes:
        return build_modbus_rtu_probe_request(
            unit_id=self.unit_id_spin.value(),
            function_code=self._current_function_code(),
            start_address=self.start_address_spin.value(),
            quantity=self.quantity_spin.value(),
        )

    def _current_function_code(self) -> int:
        data = self.function_combo.currentData()
        return int(data if data is not None else 0x03)

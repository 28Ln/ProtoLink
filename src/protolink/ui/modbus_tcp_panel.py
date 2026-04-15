from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.packet_replay_service import PacketReplayExecutionService, PacketReplayExecutionSnapshot
from protolink.application.register_monitor_service import RegisterMonitorService, RegisterMonitorSnapshot
from protolink.application.tcp_client_service import TcpClientSessionService, TcpClientSessionSnapshot
from protolink.core.device_scan import build_modbus_tcp_probe_request
from protolink.core.import_export import ArtifactKind, build_export_bundle_plan, materialize_export_bundle_from_file, sanitize_artifact_name
from protolink.core.logging import render_payload_hex
from protolink.core.modbus_tcp_parser import parse_modbus_tcp_frame, render_modbus_tcp_result
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.packet_replay import PacketReplayPlan, PacketReplayStep, ReplayDirection, default_packet_replay_path, save_packet_replay_plan
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.core.transport import ConnectionState, TransportKind
from protolink.core.workspace import WorkspaceLayout
from protolink.ui.text import READY_TEXT, connection_state_text, register_byte_order_text, register_data_type_text


class ModbusTcpLabPanel(QWidget):
    _LABEL_COLUMN_MIN_WIDTH = 88

    def __init__(
        self,
        tcp_client_service: TcpClientSessionService,
        register_monitor_service: RegisterMonitorService,
        inspector: PacketInspectorState,
        *,
        replay_service: PacketReplayExecutionService | None = None,
        workspace: WorkspaceLayout | None = None,
    ) -> None:
        super().__init__()
        self.tcp_client_service = tcp_client_service
        self.register_monitor_service = register_monitor_service
        self.inspector = inspector
        self.replay_service = replay_service
        self.workspace = workspace
        self._last_action_text = "准备就绪"
        self._build_ui()
        self.tcp_client_service.subscribe(self._refresh_tcp_state)
        self.register_monitor_service.subscribe(self._refresh_monitor_state)
        self.inspector.subscribe(self._refresh_decode_preview)
        if self.replay_service is not None:
            self.replay_service.subscribe(self._on_replay_snapshot)
        self._refresh_request_preview()
        self._refresh_tcp_state(self.tcp_client_service.snapshot)
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
        title = QLabel("Modbus TCP 调试台")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.status_label.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        frame_layout.addLayout(header_layout)
        frame_layout.addWidget(self.status_label)

        self.transaction_id_spin = QSpinBox()
        self.transaction_id_spin.setRange(0, 65535)
        self.transaction_id_spin.setValue(1)
        self.transaction_id_spin.valueChanged.connect(self._refresh_request_preview)

        self.unit_id_spin = QSpinBox()
        self.unit_id_spin.setRange(0, 247)
        self.unit_id_spin.setValue(1)
        self.unit_id_spin.valueChanged.connect(self._refresh_request_preview)

        self.function_combo = QComboBox()
        self.function_combo.addItem("读保持寄存器 (0x03)", 0x03)
        self.function_combo.addItem("读输入寄存器 (0x04)", 0x04)
        self.function_combo.currentIndexChanged.connect(self._refresh_request_preview)

        self.start_address_spin = QSpinBox()
        self.start_address_spin.setRange(0, 65535)
        self.start_address_spin.valueChanged.connect(self._refresh_request_preview)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 125)
        self.quantity_spin.setValue(2)
        self.quantity_spin.valueChanged.connect(self._refresh_request_preview)

        self.send_request_button = QPushButton("发送 TCP 请求")
        self.send_request_button.clicked.connect(self._on_send_request)

        self.point_name_input = QLineEdit()
        self.point_name_input.setPlaceholderText("寄存器点位名称")

        self.data_type_combo = QComboBox()
        for data_type in RegisterDataType:
            self.data_type_combo.addItem(register_data_type_text(data_type), data_type)

        self.byte_order_combo = QComboBox()
        for byte_order in RegisterByteOrder:
            self.byte_order_combo.addItem(register_byte_order_text(byte_order), byte_order)

        self.scale_input = QLineEdit("1.0")
        self.offset_input = QLineEdit("0.0")
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("单位")
        self.apply_point_button = QPushButton("在起始地址保存点位")
        self.apply_point_button.clicked.connect(self._on_apply_point)

        self.request_preview = QTextEdit()
        self.request_preview.setReadOnly(True)
        self.request_preview.setMinimumHeight(220)

        self.decode_preview = QTextEdit()
        self.decode_preview.setReadOnly(True)
        self.decode_preview.setMinimumHeight(220)

        self.replay_plan_name_input = QLineEdit("modbus-tcp-request")
        self.replay_file_input = QLineEdit()
        self.replay_file_input.setPlaceholderText("回放计划路径")
        self.replay_file_input.setReadOnly(True)
        self.export_replay_button = QPushButton("导出当前请求回放")
        self.export_replay_button.clicked.connect(self._on_export_replay_plan)
        self.run_replay_button = QPushButton("运行已保存回放")
        self.run_replay_button.clicked.connect(self._on_run_replay)
        self.export_capture_bundle_button = QPushButton("导出抓包")
        self.export_capture_bundle_button.clicked.connect(self._on_export_capture_bundle)
        self.replay_status_label = QLabel("回放：空闲。")
        self.replay_status_label.setObjectName("MetaLabel")
        self.replay_status_label.setWordWrap(True)

        self.workflow_hint = QLabel(
            "工作流提示：通过当前 TCP 客户端发送请求，检查原始字节流，导出回放计划与抓包，再用下方保存的点位观察 Modbus TCP 入向值。"
        )
        self.workflow_hint.setObjectName("MetaLabel")
        self.workflow_hint.setWordWrap(True)

        self.monitor_summary_label = QLabel()
        self.monitor_summary_label.setObjectName("MetaLabel")
        self.monitor_summary_label.setWordWrap(True)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("ModbusTcpTabs")
        self.content_tabs.addTab(self._build_request_tab(), "请求配置")
        self.content_tabs.addTab(self._build_preview_tab(), "预览与解析")
        self.content_tabs.addTab(self._build_replay_tab(), "回放与导出")

        frame_layout.addWidget(self.content_tabs)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def _build_request_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        request_frame, request_layout = self._create_section(
            "请求参数",
            "把事务号、功能码与地址数量单独收口，避免和监控点位字段混排后互相挤压。",
        )
        request_grid = self._create_form_grid()
        request_grid.addWidget(QLabel("事务号"), 0, 0)
        request_grid.addWidget(self.transaction_id_spin, 0, 1)
        request_grid.addWidget(QLabel("从站地址"), 0, 2)
        request_grid.addWidget(self.unit_id_spin, 0, 3)
        request_grid.addWidget(QLabel("功能码"), 1, 0)
        request_grid.addWidget(self.function_combo, 1, 1)
        request_grid.addWidget(QLabel("起始地址"), 1, 2)
        request_grid.addWidget(self.start_address_spin, 1, 3)
        request_grid.addWidget(QLabel("数量"), 2, 0)
        request_grid.addWidget(self.quantity_spin, 2, 1)
        request_grid.addWidget(self.send_request_button, 2, 2, 1, 2)
        request_layout.addLayout(request_grid)

        point_frame, point_layout = self._create_section(
            "监控点位",
            "仅保留与当前请求相关的寄存器点位设置，减少一页内的字段数量。",
        )
        point_grid = self._create_form_grid()
        point_grid.addWidget(QLabel("点位名称"), 0, 0)
        point_grid.addWidget(self.point_name_input, 0, 1)
        point_grid.addWidget(QLabel("数据类型"), 0, 2)
        point_grid.addWidget(self.data_type_combo, 0, 3)
        point_grid.addWidget(QLabel("字节序"), 1, 0)
        point_grid.addWidget(self.byte_order_combo, 1, 1)
        point_grid.addWidget(QLabel("缩放"), 1, 2)
        point_grid.addWidget(self.scale_input, 1, 3)
        point_grid.addWidget(QLabel("偏移"), 2, 0)
        point_grid.addWidget(self.offset_input, 2, 1)
        point_grid.addWidget(QLabel("单位"), 2, 2)
        point_grid.addWidget(self.unit_input, 2, 3)
        point_grid.addWidget(self.apply_point_button, 3, 2, 1, 2)
        point_layout.addLayout(point_grid)

        tab_layout.addWidget(request_frame)
        tab_layout.addWidget(point_frame)
        tab_layout.addWidget(self.workflow_hint)
        tab_layout.addStretch(1)
        return tab

    def _build_preview_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        tab_layout.addWidget(self.monitor_summary_label)

        self.preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.preview_splitter.setObjectName("ModbusTcpPreviewSplitter")
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.addWidget(self._create_text_section("请求预览", self.request_preview))
        self.preview_splitter.addWidget(self._create_text_section("选中报文解析", self.decode_preview))
        self.preview_splitter.setStretchFactor(0, 1)
        self.preview_splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(self.preview_splitter, 1)
        return tab

    def _build_replay_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        replay_frame, replay_layout = self._create_section(
            "回放与导出",
            "导出计划、抓包打包与回放执行拆到单独页签，释放主表单高度。",
        )
        replay_grid = self._create_form_grid()
        replay_grid.addWidget(QLabel("计划名称"), 0, 0)
        replay_grid.addWidget(self.replay_plan_name_input, 0, 1, 1, 3)
        replay_layout.addLayout(replay_grid)

        replay_controls = QHBoxLayout()
        replay_controls.setSpacing(8)
        replay_controls.addWidget(self.export_replay_button)
        replay_controls.addWidget(self.run_replay_button)
        replay_controls.addWidget(self.export_capture_bundle_button)
        replay_layout.addLayout(replay_controls)
        replay_layout.addWidget(self.replay_file_input)
        replay_layout.addWidget(self.replay_status_label)

        tab_layout.addWidget(replay_frame)
        tab_layout.addStretch(1)
        return tab

    def _create_text_section(self, title_text: str, editor: QTextEdit) -> QFrame:
        frame, layout = self._create_section(title_text)
        layout.addWidget(editor)
        return frame

    def _create_form_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, self._LABEL_COLUMN_MIN_WIDTH)
        grid.setColumnMinimumWidth(2, self._LABEL_COLUMN_MIN_WIDTH)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return grid

    def _create_section(self, title_text: str, description: str | None = None) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        if description:
            description_label = QLabel(description)
            description_label.setObjectName("MetaLabel")
            description_label.setWordWrap(True)
            layout.addWidget(description_label)
        return frame, layout

    def _refresh_request_preview(self) -> None:
        payload = self._build_request_payload()
        self.request_preview.setPlainText(
            "\n".join(
                (
                    render_payload_hex(payload),
                    "",
                    render_modbus_tcp_result(parse_modbus_tcp_frame(payload)),
                )
            )
        )

    def _refresh_tcp_state(self, snapshot: TcpClientSessionSnapshot) -> None:
        state_label = connection_state_text(snapshot.connection_state)
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        target_label = f"{snapshot.host}:{snapshot.port}"
        self.register_monitor_service.set_live_scope(
            transport_kind=TransportKind.TCP_CLIENT.value if snapshot.connection_state == ConnectionState.CONNECTED else None,
            session_id=snapshot.active_session_id if snapshot.connection_state == ConnectionState.CONNECTED else None,
        )
        self.status_label.setText(
            f"TCP 客户端：{state_label}    目标：{target_label}    会话：{session_label}"
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
            f"寄存器监控：点位={selected_point}    来源={source}    解码={decoded_value}"
        )
        self._refresh_error_label(snapshot.last_error)

    def _refresh_decode_preview(self) -> None:
        self.decode_preview.setPlainText(self.inspector.selected_protocol_decode_text())

    def _refresh_error_label(self, latest_error: str | None) -> None:
        if latest_error:
            self.error_label.setText(latest_error)
            return
        self.error_label.setText(self._last_action_text or READY_TEXT)

    def _on_send_request(self) -> None:
        payload = self._build_request_payload()
        function_code = self._current_function_code()
        self.register_monitor_service.set_live_scope(
            transport_kind=TransportKind.TCP_CLIENT.value,
            session_id=self.tcp_client_service.snapshot.active_session_id,
        )
        self.tcp_client_service.send_replay_payload(
            payload,
            {
                "source": "modbus_tcp_lab",
                "protocol": "modbus_tcp",
                "transaction_id": str(self.transaction_id_spin.value()),
                "unit_id": str(self.unit_id_spin.value()),
                "function_code": f"0x{function_code:02X}",
                "start_address": str(self.start_address_spin.value()),
                "quantity": str(self.quantity_spin.value()),
            },
        )
        self._last_action_text = (
            f"已发送 Modbus TCP 请求：事务={self.transaction_id_spin.value()} "
            f"从站={self.unit_id_spin.value()} 功能=0x{function_code:02X} "
            f"起始={self.start_address_spin.value()} 数量={self.quantity_spin.value()}"
        )
        self._refresh_error_label(self.tcp_client_service.snapshot.last_error)

    def _on_apply_point(self) -> None:
        point_name = " ".join(self.point_name_input.text().strip().split())
        if not point_name:
            point_name = f"MTCP {self.start_address_spin.value()}"
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
            f"已在地址 {self.start_address_spin.value()} 为 TCP 监控保存点位 '{point_name}'。"
        )
        self._refresh_error_label(self.register_monitor_service.snapshot.last_error)

    def _on_export_replay_plan(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("导出回放需要一个工作空间。")
            return

        plan_name = sanitize_artifact_name(self.replay_plan_name_input.text().strip() or "modbus-tcp-request")
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
                    transport_kind=TransportKind.TCP_CLIENT.value,
                    metadata={
                        "source": "modbus_tcp_lab",
                        "protocol": "modbus_tcp",
                        "transaction_id": str(self.transaction_id_spin.value()),
                        "unit_id": str(self.unit_id_spin.value()),
                        "function_code": f"0x{function_code:02X}",
                        "start_address": str(self.start_address_spin.value()),
                        "quantity": str(self.quantity_spin.value()),
                    },
                    source_message="Modbus TCP 调试台导出的请求",
                ),
            ),
        )
        plan_path = default_packet_replay_path(self.workspace.captures, plan.name, created_at=plan.created_at)
        save_packet_replay_plan(plan_path, plan)
        self.replay_file_input.setText(str(plan_path))
        self.replay_status_label.setText(f"已导出回放计划：{plan_path.name}")
        self.run_replay_button.setEnabled(self.tcp_client_service.snapshot.connection_state == ConnectionState.CONNECTED)
        self.export_capture_bundle_button.setEnabled(self.workspace is not None)

    def _on_run_replay(self) -> None:
        if self.replay_service is None:
            self.replay_status_label.setText("回放服务不可用。")
            return
        replay_path = self.replay_file_input.text().strip()
        if not replay_path:
            self.replay_status_label.setText("运行前请先导出或选择一个回放计划。")
            return
        try:
            self.replay_service.execute_saved_plan(replay_path, TransportKind.TCP_CLIENT)
        except Exception as exc:
            self.replay_status_label.setText(f"回放启动失败：{exc}")

    def _on_export_capture_bundle(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("导出抓包需要一个工作空间。")
            return
        replay_path_text = self.replay_file_input.text().strip()
        if not replay_path_text:
            self.replay_status_label.setText("打包抓包前请先导出一个回放计划。")
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
            self.replay_status_label.setText(f"抓包导出失败：{exc}")
            return
        self.replay_status_label.setText(
            f"抓包已导出：{plan.bundle_dir.name} -> {manifest['payload_file']}"
        )

    def _on_replay_snapshot(self, snapshot: PacketReplayExecutionSnapshot) -> None:
        if snapshot.target_kind not in {None, TransportKind.TCP_CLIENT}:
            return
        if snapshot.running:
            self.replay_status_label.setText(
                f"回放运行中：{snapshot.dispatched_steps}/{snapshot.total_steps}    计划={snapshot.plan_name or '-'}"
            )
            self._set_replay_controls_enabled(False)
            return
        self._set_replay_controls_enabled(True)
        if snapshot.last_error:
            self.replay_status_label.setText(f"回放出错：{snapshot.last_error}")
            return
        if snapshot.plan_name and snapshot.dispatched_steps >= snapshot.total_steps and snapshot.total_steps > 0:
            self.replay_status_label.setText(
                f"回放完成：{snapshot.plan_name}    {snapshot.dispatched_steps}/{snapshot.total_steps}"
            )
            return
        if self.replay_service is not None:
            self.replay_status_label.setText("回放：空闲。")

    def _set_replay_controls_enabled(self, enabled: bool) -> None:
        has_workspace = self.workspace is not None
        self.replay_plan_name_input.setEnabled(enabled and has_workspace)
        self.export_replay_button.setEnabled(enabled and has_workspace)
        self.export_capture_bundle_button.setEnabled(enabled and has_workspace and bool(self.replay_file_input.text().strip()))
        self.run_replay_button.setEnabled(
            enabled
            and self.replay_service is not None
            and self.tcp_client_service.snapshot.connection_state == ConnectionState.CONNECTED
            and bool(self.replay_file_input.text().strip())
        )

    def _build_request_payload(self) -> bytes:
        return build_modbus_tcp_probe_request(
            transaction_id=self.transaction_id_spin.value(),
            unit_id=self.unit_id_spin.value(),
            function_code=self._current_function_code(),
            start_address=self.start_address_spin.value(),
            quantity=self.quantity_spin.value(),
        )

    def _current_function_code(self) -> int:
        data = self.function_combo.currentData()
        return int(data if data is not None else 0x03)

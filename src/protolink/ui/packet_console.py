from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from protolink.application.packet_replay_service import PacketReplayExecutionService, PacketReplayExecutionSnapshot
from protolink.core.logging import LogLevel
from protolink.core.packet_inspector import PacketInspectorFilter, PacketInspectorState, PayloadViewMode
from protolink.core.packet_replay import (
    ReplayDirection,
    build_packet_replay_plan,
    default_packet_replay_path,
    save_packet_replay_plan,
)
from protolink.core.raw_packet_composer import RawPacketComposerState, RawPacketInputMode, RawPacketLineEnding
from protolink.core.transport import TransportKind
from protolink.core.workspace import WorkspaceLayout
from protolink.ui.text import line_ending_text, log_level_text, raw_input_mode_text, transport_kind_text


class PacketConsoleWidget(QWidget):
    def __init__(
        self,
        inspector: PacketInspectorState,
        *,
        replay_service: PacketReplayExecutionService | None = None,
        workspace: WorkspaceLayout | None = None,
    ) -> None:
        super().__init__()
        self.inspector = inspector
        self.replay_service = replay_service
        self.workspace = workspace
        self.composer = RawPacketComposerState()
        self._syncing_controls = False
        self._syncing_composer = False
        self._build_ui()
        self.inspector.subscribe(self.refresh)
        self.composer.subscribe(lambda _snapshot: self._refresh_composer())
        if self.replay_service is not None:
            self.replay_service.subscribe(self._on_replay_snapshot)
        else:
            self._set_replay_controls_enabled(False)
        self.refresh()

    def _build_ui(self) -> None:
        self.setObjectName("PacketConsoleWidget")
        self.setMinimumHeight(148)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(8)
        self.console_tabs = QTabWidget()
        self.console_tabs.setObjectName("PacketConsoleTabs")
        self.console_tabs.setDocumentMode(True)
        self.console_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.console_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.console_tabs.addTab(self._build_inspector_tab(), "分析")
        self.console_tabs.addTab(self._build_composer_tab(), "构建")
        self.console_tabs.addTab(self._build_replay_section(), "重放")
        frame_layout.addWidget(self.console_tabs, 1)
        layout.addWidget(frame)

    def _build_inspector_tab(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        controls_layout = QGridLayout()
        controls_layout.setHorizontalSpacing(10)
        controls_layout.setVerticalSpacing(8)

        self.view_mode = QComboBox()
        self.view_mode.addItem("十六进制视图", PayloadViewMode.HEX)
        self.view_mode.addItem("ASCII 视图", PayloadViewMode.ASCII)
        self.view_mode.addItem("UTF-8 视图", PayloadViewMode.UTF8)
        self.view_mode.currentIndexChanged.connect(self._on_view_mode_changed)

        self.level_filter = QComboBox()
        self.level_filter.addItem("全部等级", None)
        self.level_filter.addItem(log_level_text(LogLevel.DEBUG), LogLevel.DEBUG)
        self.level_filter.addItem(log_level_text(LogLevel.INFO), LogLevel.INFO)
        self.level_filter.addItem(log_level_text(LogLevel.WARNING), LogLevel.WARNING)
        self.level_filter.addItem(log_level_text(LogLevel.ERROR), LogLevel.ERROR)
        self.level_filter.currentIndexChanged.connect(self._on_filters_changed)

        self.session_filter = QComboBox()
        self.session_filter.addItem("全部会话", None)
        self.session_filter.currentIndexChanged.connect(self._on_filters_changed)

        self.category_filter = QLineEdit()
        self.category_filter.setPlaceholderText("类别筛选…")
        self.category_filter.textChanged.connect(self._on_filters_changed)

        self.text_filter = QLineEdit()
        self.text_filter.setPlaceholderText("搜索消息或载荷…")
        self.text_filter.textChanged.connect(self._on_filters_changed)

        self.clear_filters_button = QPushButton("清空")
        self.clear_filters_button.clicked.connect(self._on_clear_filters)
        self.filter_toggle_button = QToolButton()
        self.filter_toggle_button.setObjectName("SubtleButton")
        self.filter_toggle_button.setText("筛选")
        self.filter_toggle_button.setToolTip("显示或隐藏筛选条件")
        self.filter_toggle_button.setCheckable(True)
        self.filter_toggle_button.toggled.connect(self._set_filters_visible)

        controls_layout.addWidget(QLabel("负载视图"), 0, 0)
        controls_layout.addWidget(self.view_mode, 0, 1)
        controls_layout.addWidget(QLabel("等级"), 0, 2)
        controls_layout.addWidget(self.level_filter, 0, 3)
        controls_layout.addWidget(QLabel("会话"), 0, 4)
        controls_layout.addWidget(self.session_filter, 0, 5)
        controls_layout.addWidget(self.clear_filters_button, 0, 6)
        controls_layout.addWidget(QLabel("类别"), 1, 0)
        controls_layout.addWidget(self.category_filter, 1, 1, 1, 3)
        controls_layout.addWidget(QLabel("搜索"), 1, 4)
        controls_layout.addWidget(self.text_filter, 1, 5, 1, 2)
        controls_layout.setColumnStretch(1, 1)
        controls_layout.setColumnStretch(3, 1)
        controls_layout.setColumnStretch(5, 1)

        self.entry_summary = QLabel()
        self.entry_summary.setObjectName("MetaLabel")
        self.entry_summary.setWordWrap(True)
        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(8)
        summary_row.addWidget(self.entry_summary, 1)
        summary_row.addWidget(self.filter_toggle_button)
        self.filter_panel = QWidget()
        self.filter_panel.setVisible(False)
        self.filter_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.filter_panel.setLayout(controls_layout)

        self.entry_list = QListWidget()
        self.entry_list.currentItemChanged.connect(self._on_selection_changed)
        self.entry_list.setMinimumWidth(260)
        self.entry_list.setMinimumHeight(160)
        self.entry_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.entry_list.setUniformItemSizes(True)

        self.payload_text = self._create_readonly_text_panel("选择日志条目后查看载荷。")
        self.metadata_text = self._create_readonly_text_panel("选择日志条目后查看元数据。")
        self.modbus_text = self._create_readonly_text_panel("识别到协议后显示解析结果。")

        self.entry_detail_tabs = QTabWidget()
        self.entry_detail_tabs.setObjectName("PacketConsoleInspectorTabs")
        self.entry_detail_tabs.setDocumentMode(True)
        self.entry_detail_tabs.addTab(self.payload_text, "载荷")
        self.entry_detail_tabs.addTab(self.metadata_text, "元数据")
        self.entry_detail_tabs.addTab(self.modbus_text, "协议解析")
        self.entry_detail_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.inspector_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.inspector_splitter.setObjectName("PacketConsoleInspectorSplitter")
        self.inspector_splitter.setChildrenCollapsible(False)
        self.inspector_splitter.addWidget(self.entry_list)
        self.inspector_splitter.addWidget(self.entry_detail_tabs)
        self.inspector_splitter.setStretchFactor(0, 3)
        self.inspector_splitter.setStretchFactor(1, 5)
        self.inspector_splitter.setSizes([380, 520])

        layout.addLayout(summary_row)
        layout.addWidget(self.filter_panel)
        layout.addWidget(self.inspector_splitter, 1)
        return page

    def _build_composer_tab(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        composer_header = QHBoxLayout()
        composer_header.setSpacing(8)

        self.composer_mode = QComboBox()
        self.composer_mode.addItem("十六进制（HEX）", RawPacketInputMode.HEX)
        self.composer_mode.addItem("ASCII 文本", RawPacketInputMode.ASCII)
        self.composer_mode.addItem("UTF-8 文本", RawPacketInputMode.UTF8)
        self.composer_mode.currentIndexChanged.connect(self._on_composer_mode_changed)

        self.composer_line_ending = QComboBox()
        self.composer_line_ending.addItem("无", RawPacketLineEnding.NONE)
        self.composer_line_ending.addItem("CR", RawPacketLineEnding.CR)
        self.composer_line_ending.addItem("LF", RawPacketLineEnding.LF)
        self.composer_line_ending.addItem("CRLF", RawPacketLineEnding.CRLF)
        self.composer_line_ending.currentIndexChanged.connect(self._on_composer_line_ending_changed)

        self.load_selected_payload_button = QPushButton("加载选中载荷")
        self.load_selected_payload_button.clicked.connect(self._on_load_selected_payload)

        self.composer_clear_button = QPushButton("清除草稿")
        self.composer_clear_button.clicked.connect(self._on_composer_clear)

        composer_header.addWidget(QLabel("模式"))
        composer_header.addWidget(self.composer_mode)
        composer_header.addWidget(QLabel("换行"))
        composer_header.addWidget(self.composer_line_ending)
        composer_header.addStretch(1)
        composer_header.addWidget(self.load_selected_payload_button)
        composer_header.addWidget(self.composer_clear_button)

        self.composer_summary = QLabel()
        self.composer_summary.setObjectName("MetaLabel")
        self.composer_summary.setWordWrap(True)
        self.composer_error = QLabel()
        self.composer_error.setObjectName("MetaLabel")
        self.composer_error.setWordWrap(True)

        self.composer_input = QTextEdit()
        self.composer_input.setPlaceholderText("输入十六进制、ASCII 或 UTF-8 文本负载…")
        self.composer_input.textChanged.connect(self._on_composer_text_changed)
        self.composer_input.setMinimumHeight(150)
        self.composer_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.composer_preview = self._create_readonly_text_panel("预览编码后的字节内容。")
        self.composer_preview.setMinimumHeight(150)

        self.composer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.composer_splitter.setObjectName("PacketConsoleComposerSplitter")
        self.composer_splitter.setChildrenCollapsible(False)
        self.composer_splitter.addWidget(self._wrap_labeled_panel("草稿", self.composer_input))
        self.composer_splitter.addWidget(self._wrap_labeled_panel("字节预览", self.composer_preview))
        self.composer_splitter.setStretchFactor(0, 1)
        self.composer_splitter.setStretchFactor(1, 1)
        self.composer_splitter.setSizes([480, 480])

        layout.addLayout(composer_header)
        layout.addWidget(self.composer_summary)
        layout.addWidget(self.composer_error)
        layout.addWidget(self.composer_splitter, 1)
        return page

    def _build_replay_section(self) -> QWidget:
        section = QWidget()
        section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)

        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)

        self.replay_file_input = QLineEdit()
        self.replay_file_input.setPlaceholderText("回放计划路径 (.json)")
        if self.workspace is not None:
            self.replay_file_input.setText(str(self.workspace.captures / "replay-plan.json"))

        self.replay_target_combo = QComboBox()
        for kind in (
            TransportKind.SERIAL,
            TransportKind.TCP_CLIENT,
            TransportKind.TCP_SERVER,
            TransportKind.UDP,
            TransportKind.MQTT_CLIENT,
            TransportKind.MQTT_SERVER,
        ):
            self.replay_target_combo.addItem(transport_kind_text(kind), kind)

        self.replay_run_button = QPushButton("执行重放")
        self.replay_run_button.clicked.connect(self._on_run_replay)

        self.replay_plan_name_input = QLineEdit()
        self.replay_plan_name_input.setPlaceholderText("留空则使用默认回放文件键")
        self.replay_direction_combo = QComboBox()
        self.replay_direction_combo.addItem("仅出站", "outbound_only")
        self.replay_direction_combo.addItem("出入站", "outbound_inbound")
        self.replay_direction_combo.addItem("全部方向", "all")
        self.replay_build_button = QPushButton("以可见构建")
        self.replay_build_button.clicked.connect(self._on_build_replay_plan)

        self.replay_status_label = QLabel("重放空闲。")
        self.replay_status_label.setObjectName("MetaLabel")
        self.replay_status_label.setWordWrap(True)

        controls.addWidget(QLabel("计划"), 0, 0)
        controls.addWidget(self.replay_file_input, 0, 1, 1, 3)
        controls.addWidget(QLabel("目标"), 1, 0)
        controls.addWidget(self.replay_target_combo, 1, 1)
        controls.addWidget(self.replay_run_button, 1, 3)
        controls.addWidget(QLabel("计划名称"), 2, 0)
        controls.addWidget(self.replay_plan_name_input, 2, 1)
        controls.addWidget(self.replay_direction_combo, 2, 2)
        controls.addWidget(self.replay_build_button, 2, 3)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(2, 1)

        hint = QLabel("将捕获记录转成回放计划，或直接执行现有计划。")
        hint.setObjectName("MetaLabel")
        hint.setWordWrap(True)

        section_layout.addWidget(hint)
        section_layout.addLayout(controls)
        section_layout.addWidget(self.replay_status_label)
        section_layout.addStretch(1)
        return section

    def _create_readonly_text_panel(self, placeholder: str) -> QTextEdit:
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlaceholderText(placeholder)
        text_edit.setMinimumHeight(140)
        text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return text_edit

    def _wrap_labeled_panel(self, title: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(QLabel(title))
        layout.addWidget(widget, 1)
        return container

    def refresh(self) -> None:
        rows = self.inspector.rows()
        counts = self.inspector.counts_by_level()
        sessions = self.inspector.available_session_ids()

        self._sync_view_mode_control()
        self._sync_filter_controls(sessions)

        self.entry_summary.setText(
            " · ".join(
                (
                    f"可见 {len(rows)}/{len(self.inspector)}",
                    f"会话 {len(sessions)}",
                    f"警告 {counts.get(LogLevel.WARNING, 0)}",
                    f"错误 {counts.get(LogLevel.ERROR, 0)}",
                )
            )
        )

        self.entry_list.blockSignals(True)
        self.entry_list.clear()
        selected_id = self.inspector.selected_entry_id

        selected_row = None
        for row in rows:
            session_label = row.session_id[:8] if row.session_id else "-"
            text = (
                f"{row.timestamp.strftime('%H:%M:%S')}  "
                f"{log_level_text(row.level)}  "
                f"{session_label}  "
                f"{row.category}  {row.message}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row.entry_id)
            item.setToolTip(text)
            self.entry_list.addItem(item)
            if row.entry_id == selected_id:
                selected_row = item

        if selected_row is not None:
            self.entry_list.setCurrentItem(selected_row)
        elif self.entry_list.count() > 0:
            self.entry_list.setCurrentRow(self.entry_list.count() - 1)
        self.entry_list.blockSignals(False)

        self.payload_text.setPlainText(self.inspector.selected_payload_text())
        self.metadata_text.setPlainText(self.inspector.selected_metadata_text())
        self.modbus_text.setPlainText(self.inspector.selected_protocol_decode_text())
        self._refresh_composer()

    def _on_view_mode_changed(self) -> None:
        if self._syncing_controls:
            return
        mode = self.view_mode.currentData()
        if mode is not None:
            self.inspector.set_payload_view_mode(PayloadViewMode(str(mode)))

    def _on_filters_changed(self) -> None:
        if self._syncing_controls:
            return

        self.inspector.set_filter(
            PacketInspectorFilter(
                level=self.level_filter.currentData(),
                session_id=self.session_filter.currentData(),
                category_query=self.category_filter.text(),
                text_query=self.text_filter.text(),
            )
        )

    def _on_clear_filters(self) -> None:
        self.inspector.clear_filter()
        self.filter_toggle_button.setChecked(False)

    def _on_selection_changed(self, current: QListWidgetItem | None) -> None:
        entry_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self.inspector.select(entry_id)

    def _on_composer_mode_changed(self) -> None:
        if self._syncing_composer:
            return
        mode = self.composer_mode.currentData()
        if mode is None:
            return
        if isinstance(mode, RawPacketInputMode):
            self.composer.set_input_mode(mode)
            return
        self.composer.set_input_mode(RawPacketInputMode(str(mode)))

    def _on_composer_line_ending_changed(self) -> None:
        if self._syncing_composer:
            return
        line_ending = self.composer_line_ending.currentData()
        if line_ending is None:
            return
        if isinstance(line_ending, RawPacketLineEnding):
            self.composer.set_line_ending(line_ending)
            return
        self.composer.set_line_ending(RawPacketLineEnding(str(line_ending)))

    def _on_composer_text_changed(self) -> None:
        if self._syncing_composer:
            return
        self.composer.set_draft_text(self.composer_input.toPlainText())

    def _on_composer_clear(self) -> None:
        self.composer.clear()

    def _on_load_selected_payload(self) -> None:
        entry = self.inspector.selected_entry()
        if entry is None:
            return
        self.composer.load_payload(entry.raw_payload or b"", mode=RawPacketInputMode.HEX)

    def _on_run_replay(self) -> None:
        service = self.replay_service
        if service is None:
            self.replay_status_label.setText("重放服务不可用。")
            return

        replay_path = self.replay_file_input.text().strip()
        if not replay_path:
            self.replay_status_label.setText("需要指定重放计划路径。")
            return

        target_kind = self.replay_target_combo.currentData()
        if target_kind is None:
            self.replay_status_label.setText("请选择重放目标。")
            return
        if not isinstance(target_kind, TransportKind):
            target_kind = TransportKind(str(target_kind))

        self.replay_status_label.setText(
            f"重放请求：{Path(replay_path).name} -> {transport_kind_text(target_kind)}"
        )
        try:
            service.execute_saved_plan(Path(replay_path), target_kind)
        except Exception as exc:
            self.replay_status_label.setText(f"重放加载失败: {exc}")
            return

    def _on_build_replay_plan(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("构建重放计划需要有效的工作区。")
            return

        name = self.replay_plan_name_input.text().strip() or "packet-replay"
        direction_mode = str(self.replay_direction_combo.currentData() or "outbound_only")
        include_directions = {
            "outbound_only": {ReplayDirection.OUTBOUND},
            "outbound_inbound": {ReplayDirection.OUTBOUND, ReplayDirection.INBOUND},
            "all": {
                ReplayDirection.OUTBOUND,
                ReplayDirection.INBOUND,
                ReplayDirection.INTERNAL,
                ReplayDirection.UNKNOWN,
            },
        }.get(direction_mode, {ReplayDirection.OUTBOUND})

        visible_entries = self.inspector.visible_entries()
        if not visible_entries:
            self.replay_status_label.setText("当前无可见条目，无法构建重放计划。")
            return

        plan = build_packet_replay_plan(
            visible_entries,
            name=name,
            include_directions=include_directions,
        )
        if not plan.steps:
            self.replay_status_label.setText("无匹配的传输消息用于构建重放。")
            return

        plan_path = default_packet_replay_path(
            self.workspace.captures,
            plan.name,
            created_at=plan.created_at,
        )
        save_packet_replay_plan(plan_path, plan)
        self.replay_file_input.setText(str(plan_path))
        self.replay_status_label.setText(
            f"重放计划构建完成：{plan_path.name}    步骤：{len(plan.steps)}"
        )

    def _sync_filter_controls(self, sessions: tuple[str, ...]) -> None:
        self._syncing_controls = True
        try:
            self._rebuild_session_filter(sessions)
            self._set_combo_to_data(self.level_filter, self.inspector.filter.level)
            self._set_combo_to_data(self.session_filter, self.inspector.filter.session_id)
            self._set_line_edit_text(self.category_filter, self.inspector.filter.category_query)
            self._set_line_edit_text(self.text_filter, self.inspector.filter.text_query)
            self.clear_filters_button.setEnabled(self.inspector.filter_is_active())
        finally:
            self._syncing_controls = False

    def _sync_view_mode_control(self) -> None:
        self._syncing_controls = True
        try:
            self._set_combo_to_data(self.view_mode, self.inspector.payload_view_mode)
        finally:
            self._syncing_controls = False

    def _rebuild_session_filter(self, sessions: tuple[str, ...]) -> None:
        current_options = [self.session_filter.itemData(index) for index in range(self.session_filter.count())]
        desired_options = [None, *sessions]
        if current_options == desired_options:
            return

        self.session_filter.blockSignals(True)
        self.session_filter.clear()
        self.session_filter.addItem("全部会话", None)
        for session_id in sessions:
            self.session_filter.addItem(self._format_session_label(session_id), session_id)
        self.session_filter.blockSignals(False)

    def _set_combo_to_data(self, combo: QComboBox, value: object | None) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _set_line_edit_text(self, line_edit: QLineEdit, text: str) -> None:
        if line_edit.text() == text:
            return
        line_edit.blockSignals(True)
        line_edit.setText(text)
        line_edit.blockSignals(False)

    def _format_session_label(self, session_id: str) -> str:
        return f"{session_id[:8]}…"

    def _refresh_composer(self) -> None:
        snapshot = self.composer.snapshot
        self._syncing_composer = True
        try:
            self._set_combo_to_data(self.composer_mode, snapshot.input_mode)
            self._set_combo_to_data(self.composer_line_ending, snapshot.line_ending)
            self._set_text_edit_text(self.composer_input, snapshot.draft_text)
        finally:
            self._syncing_composer = False

        self.load_selected_payload_button.setEnabled(self.inspector.selected_entry() is not None)
        self.composer_summary.setText(
            f"{len(snapshot.payload)} 字节 · "
            f"{raw_input_mode_text(snapshot.input_mode)} · "
            f"{line_ending_text(snapshot.line_ending)}"
        )
        self.composer_error.setText(f"输入错误：{snapshot.last_error}" if snapshot.last_error else "")
        self.composer_error.setVisible(bool(snapshot.last_error))
        self.composer_preview.setPlainText(
            "\n".join(
                (
                    "十六进制:",
                    snapshot.payload_hex or "（空）",
                    "",
                    "ASCII:",
                    snapshot.payload_ascii or "（空）",
                    "",
                    "UTF-8:",
                    snapshot.payload_utf8 or "（空）",
                )
            )
        )

    def _set_text_edit_text(self, text_edit: QTextEdit, text: str) -> None:
        if text_edit.toPlainText() == text:
            return
        text_edit.blockSignals(True)
        text_edit.setPlainText(text)
        text_edit.blockSignals(False)

    def _on_replay_snapshot(self, snapshot: PacketReplayExecutionSnapshot) -> None:
        if snapshot.running:
            self.replay_status_label.setText(
                f"重放运行中：{snapshot.plan_name or '-'}    "
                f"步骤 {snapshot.dispatched_steps}/{snapshot.total_steps}    "
                f"跳过：{snapshot.skipped_steps}"
            )
            self._set_replay_controls_enabled(False)
            return

        self._set_replay_controls_enabled(True)
        if snapshot.last_error:
            self.replay_status_label.setText(f"重放错误：{snapshot.last_error}")
            return
        if snapshot.plan_name and snapshot.total_steps > 0 and snapshot.dispatched_steps >= snapshot.total_steps:
            self.replay_status_label.setText(
                f"重放完成：{snapshot.plan_name}    "
                f"派发：{snapshot.dispatched_steps}/{snapshot.total_steps}"
            )
            return
        self.replay_status_label.setText("重放空闲。")

    def _set_replay_controls_enabled(self, enabled: bool) -> None:
        self.replay_file_input.setEnabled(enabled)
        self.replay_target_combo.setEnabled(enabled)
        self.replay_run_button.setEnabled(enabled)
        self.replay_plan_name_input.setEnabled(enabled and self.workspace is not None)
        self.replay_direction_combo.setEnabled(enabled and self.workspace is not None)
        self.replay_build_button.setEnabled(enabled and self.workspace is not None)

    def _set_filters_visible(self, visible: bool) -> None:
        self.filter_panel.setVisible(visible)
        self.filter_toggle_button.setText("隐藏筛选" if visible else "筛选")

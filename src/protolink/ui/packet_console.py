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
    QTextEdit,
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame = QFrame()
        frame.setObjectName("Panel")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(18, 18, 18, 18)
        frame_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Packet Inspector")
        title.setObjectName("SectionTitle")

        self.view_mode = QComboBox()
        self.view_mode.addItem("Hex", PayloadViewMode.HEX)
        self.view_mode.addItem("ASCII", PayloadViewMode.ASCII)
        self.view_mode.addItem("UTF-8", PayloadViewMode.UTF8)
        self.view_mode.currentIndexChanged.connect(self._on_view_mode_changed)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel("Payload View"))
        header_layout.addWidget(self.view_mode)

        filters_layout = QGridLayout()
        filters_layout.setHorizontalSpacing(10)
        filters_layout.setVerticalSpacing(8)

        self.level_filter = QComboBox()
        self.level_filter.addItem("All Levels", None)
        self.level_filter.addItem("Debug", LogLevel.DEBUG)
        self.level_filter.addItem("Info", LogLevel.INFO)
        self.level_filter.addItem("Warning", LogLevel.WARNING)
        self.level_filter.addItem("Error", LogLevel.ERROR)
        self.level_filter.currentIndexChanged.connect(self._on_filters_changed)

        self.session_filter = QComboBox()
        self.session_filter.addItem("All Sessions", None)
        self.session_filter.currentIndexChanged.connect(self._on_filters_changed)

        self.category_filter = QLineEdit()
        self.category_filter.setPlaceholderText("Category contains…")
        self.category_filter.textChanged.connect(self._on_filters_changed)

        self.text_filter = QLineEdit()
        self.text_filter.setPlaceholderText("Search message or payload…")
        self.text_filter.textChanged.connect(self._on_filters_changed)

        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.clicked.connect(self._on_clear_filters)

        filters_layout.addWidget(QLabel("Level"), 0, 0)
        filters_layout.addWidget(self.level_filter, 0, 1)
        filters_layout.addWidget(QLabel("Session"), 0, 2)
        filters_layout.addWidget(self.session_filter, 0, 3)
        filters_layout.addWidget(self.clear_filters_button, 0, 4)
        filters_layout.addWidget(QLabel("Category"), 1, 0)
        filters_layout.addWidget(self.category_filter, 1, 1, 1, 2)
        filters_layout.addWidget(QLabel("Search"), 1, 3)
        filters_layout.addWidget(self.text_filter, 1, 4)
        filters_layout.setColumnStretch(1, 1)
        filters_layout.setColumnStretch(3, 1)
        filters_layout.setColumnStretch(4, 1)

        body = QGridLayout()
        body.setHorizontalSpacing(12)
        body.setVerticalSpacing(8)

        self.entry_list = QListWidget()
        self.entry_list.currentItemChanged.connect(self._on_selection_changed)

        self.entry_summary = QLabel()
        self.entry_summary.setObjectName("MetaLabel")

        self.payload_text = QTextEdit()
        self.payload_text.setReadOnly(True)
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.modbus_text = QTextEdit()
        self.modbus_text.setReadOnly(True)

        body.addWidget(QLabel("Entries"), 0, 0)
        body.addWidget(QLabel("Payload"), 0, 1)
        body.addWidget(QLabel("Metadata"), 2, 1)
        body.addWidget(QLabel("Protocol Decode"), 4, 1)
        body.addWidget(self.entry_list, 1, 0, 4, 1)
        body.addWidget(self.payload_text, 1, 1)
        body.addWidget(self.metadata_text, 3, 1)
        body.addWidget(self.modbus_text, 5, 1)
        body.setColumnStretch(0, 1)
        body.setColumnStretch(1, 1)

        composer_title = QLabel("Raw Packet Composer")
        composer_title.setObjectName("SectionTitle")

        composer_header = QHBoxLayout()
        composer_header.setSpacing(8)

        self.composer_mode = QComboBox()
        self.composer_mode.addItem("HEX", RawPacketInputMode.HEX)
        self.composer_mode.addItem("ASCII", RawPacketInputMode.ASCII)
        self.composer_mode.addItem("UTF-8", RawPacketInputMode.UTF8)
        self.composer_mode.currentIndexChanged.connect(self._on_composer_mode_changed)

        self.composer_line_ending = QComboBox()
        self.composer_line_ending.addItem("None", RawPacketLineEnding.NONE)
        self.composer_line_ending.addItem("CR", RawPacketLineEnding.CR)
        self.composer_line_ending.addItem("LF", RawPacketLineEnding.LF)
        self.composer_line_ending.addItem("CRLF", RawPacketLineEnding.CRLF)
        self.composer_line_ending.currentIndexChanged.connect(self._on_composer_line_ending_changed)

        self.load_selected_payload_button = QPushButton("Load Selected Payload")
        self.load_selected_payload_button.clicked.connect(self._on_load_selected_payload)

        self.composer_clear_button = QPushButton("Clear Draft")
        self.composer_clear_button.clicked.connect(self._on_composer_clear)

        composer_header.addWidget(QLabel("Mode"))
        composer_header.addWidget(self.composer_mode)
        composer_header.addWidget(QLabel("Line Ending"))
        composer_header.addWidget(self.composer_line_ending)
        composer_header.addStretch(1)
        composer_header.addWidget(self.load_selected_payload_button)
        composer_header.addWidget(self.composer_clear_button)

        self.composer_summary = QLabel()
        self.composer_summary.setObjectName("MetaLabel")
        self.composer_error = QLabel()
        self.composer_error.setObjectName("MetaLabel")
        self.composer_error.setWordWrap(True)

        composer_body = QGridLayout()
        composer_body.setHorizontalSpacing(12)
        composer_body.setVerticalSpacing(8)

        self.composer_input = QTextEdit()
        self.composer_input.setPlaceholderText("Enter payload bytes as HEX, ASCII, or UTF-8 text…")
        self.composer_input.textChanged.connect(self._on_composer_text_changed)
        self.composer_preview = QTextEdit()
        self.composer_preview.setReadOnly(True)

        composer_body.addWidget(QLabel("Draft"), 0, 0)
        composer_body.addWidget(QLabel("Bytes Preview"), 0, 1)
        composer_body.addWidget(self.composer_input, 1, 0)
        composer_body.addWidget(self.composer_preview, 1, 1)
        composer_body.setColumnStretch(0, 1)
        composer_body.setColumnStretch(1, 1)

        frame_layout.addLayout(header_layout)
        frame_layout.addWidget(self.entry_summary)
        frame_layout.addLayout(filters_layout)
        frame_layout.addLayout(body)
        frame_layout.addWidget(composer_title)
        frame_layout.addLayout(composer_header)
        frame_layout.addWidget(self.composer_summary)
        frame_layout.addWidget(self.composer_error)
        frame_layout.addLayout(composer_body)
        frame_layout.addWidget(self._build_replay_section())
        layout.addWidget(frame)

    def _build_replay_section(self) -> QWidget:
        section = QFrame()
        section.setObjectName("Panel")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(12, 12, 12, 12)
        section_layout.setSpacing(8)

        title = QLabel("Packet Replay")
        title.setObjectName("SectionTitle")

        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)

        self.replay_file_input = QLineEdit()
        self.replay_file_input.setPlaceholderText("Replay plan path (.json)")
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
            self.replay_target_combo.addItem(kind.value, kind)

        self.replay_run_button = QPushButton("Run Replay")
        self.replay_run_button.clicked.connect(self._on_run_replay)

        self.replay_plan_name_input = QLineEdit()
        self.replay_plan_name_input.setPlaceholderText("replay-plan")
        self.replay_direction_combo = QComboBox()
        self.replay_direction_combo.addItem("Outbound Only", "outbound_only")
        self.replay_direction_combo.addItem("Outbound + Inbound", "outbound_inbound")
        self.replay_direction_combo.addItem("All Directions", "all")
        self.replay_build_button = QPushButton("Build From Visible")
        self.replay_build_button.clicked.connect(self._on_build_replay_plan)

        self.replay_status_label = QLabel("Replay idle.")
        self.replay_status_label.setObjectName("MetaLabel")
        self.replay_status_label.setWordWrap(True)

        controls.addWidget(QLabel("Plan"), 0, 0)
        controls.addWidget(self.replay_file_input, 0, 1, 1, 3)
        controls.addWidget(QLabel("Target"), 1, 0)
        controls.addWidget(self.replay_target_combo, 1, 1)
        controls.addWidget(self.replay_run_button, 1, 3)
        controls.addWidget(QLabel("Build Name"), 2, 0)
        controls.addWidget(self.replay_plan_name_input, 2, 1)
        controls.addWidget(self.replay_direction_combo, 2, 2)
        controls.addWidget(self.replay_build_button, 2, 3)

        section_layout.addWidget(title)
        section_layout.addLayout(controls)
        section_layout.addWidget(self.replay_status_label)
        return section

    def refresh(self) -> None:
        rows = self.inspector.rows()
        counts = self.inspector.counts_by_level()
        sessions = self.inspector.available_session_ids()

        self._sync_view_mode_control()
        self._sync_filter_controls(sessions)

        self.entry_summary.setText(
            "Entries: "
            f"{len(self.inspector)}    "
            f"Visible: {len(rows)}    "
            f"Sessions: {len(sessions)}    "
            f"Info: {counts.get(LogLevel.INFO, 0)}    "
            f"Warning: {counts.get(LogLevel.WARNING, 0)}    "
            f"Error: {counts.get(LogLevel.ERROR, 0)}"
        )

        self.entry_list.blockSignals(True)
        self.entry_list.clear()
        selected_id = self.inspector.selected_entry_id

        selected_row = None
        for row in rows:
            session_label = row.session_id[:8] if row.session_id else "-"
            text = (
                f"{row.timestamp.strftime('%H:%M:%S')}  "
                f"{row.level.value.upper()}  "
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
            self.replay_status_label.setText("Replay service is unavailable.")
            return

        replay_path = self.replay_file_input.text().strip()
        if not replay_path:
            self.replay_status_label.setText("Replay plan path is required.")
            return

        target_kind = self.replay_target_combo.currentData()
        if target_kind is None:
            self.replay_status_label.setText("Replay target is required.")
            return
        if not isinstance(target_kind, TransportKind):
            target_kind = TransportKind(str(target_kind))

        self.replay_status_label.setText(
            f"Replay requested: {Path(replay_path).name} -> {target_kind.value}"
        )
        try:
            service.execute_saved_plan(Path(replay_path), target_kind)
        except Exception as exc:
            self.replay_status_label.setText(f"Replay load failed: {exc}")
            return

    def _on_build_replay_plan(self) -> None:
        if self.workspace is None:
            self.replay_status_label.setText("Workspace is required to build replay plans.")
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
            self.replay_status_label.setText("No visible entries to build replay plan.")
            return

        plan = build_packet_replay_plan(
            visible_entries,
            name=name,
            include_directions=include_directions,
        )
        if not plan.steps:
            self.replay_status_label.setText("No matching transport message rows for replay build.")
            return

        plan_path = default_packet_replay_path(
            self.workspace.captures,
            plan.name,
            created_at=plan.created_at,
        )
        save_packet_replay_plan(plan_path, plan)
        self.replay_file_input.setText(str(plan_path))
        self.replay_status_label.setText(
            f"Replay plan built: {plan_path.name}    Steps: {len(plan.steps)}"
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
        self.session_filter.addItem("All Sessions", None)
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
            f"Bytes: {len(snapshot.payload)}    "
            f"Mode: {snapshot.input_mode.value.upper()}    "
            f"Line Ending: {snapshot.line_ending.value.upper()}"
        )
        self.composer_error.setText(f"Error: {snapshot.last_error}" if snapshot.last_error else "Error: None")
        self.composer_preview.setPlainText(
            "\n".join(
                (
                    "HEX:",
                    snapshot.payload_hex or "(empty)",
                    "",
                    "ASCII:",
                    snapshot.payload_ascii or "(empty)",
                    "",
                    "UTF-8:",
                    snapshot.payload_utf8 or "(empty)",
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
                f"Replay running: {snapshot.plan_name or '-'}    "
                f"Step {snapshot.dispatched_steps}/{snapshot.total_steps}    "
                f"Skipped: {snapshot.skipped_steps}"
            )
            self._set_replay_controls_enabled(False)
            return

        self._set_replay_controls_enabled(True)
        if snapshot.last_error:
            self.replay_status_label.setText(f"Replay error: {snapshot.last_error}")
            return
        if snapshot.plan_name and snapshot.total_steps > 0 and snapshot.dispatched_steps >= snapshot.total_steps:
            self.replay_status_label.setText(
                f"Replay completed: {snapshot.plan_name}    "
                f"Dispatched: {snapshot.dispatched_steps}/{snapshot.total_steps}"
            )
            return
        self.replay_status_label.setText("Replay idle.")

    def _set_replay_controls_enabled(self, enabled: bool) -> None:
        self.replay_file_input.setEnabled(enabled)
        self.replay_target_combo.setEnabled(enabled)
        self.replay_run_button.setEnabled(enabled)
        self.replay_plan_name_input.setEnabled(enabled and self.workspace is not None)
        self.replay_direction_combo.setEnabled(enabled and self.workspace is not None)
        self.replay_build_button.setEnabled(enabled and self.workspace is not None)

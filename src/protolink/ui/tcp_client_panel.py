from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.tcp_client_service import (
    TcpClientLineEnding,
    TcpClientSendEncoding,
    TcpClientSessionService,
    TcpClientSessionSnapshot,
)
from protolink.core.transport import ConnectionState
from protolink.ui.text import CURRENT_DRAFT_TEXT, READY_TEXT, connection_state_text


class TcpClientPanel(QWidget):
    _LABEL_COLUMN_MIN_WIDTH = 88
    _EDITOR_MIN_HEIGHT = 170

    def __init__(self, service: TcpClientSessionService) -> None:
        super().__init__()
        self.service = service
        self._syncing_controls = False
        self._build_ui()
        self.service.subscribe(self.refresh)
        self.refresh(self.service.snapshot)

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
        title = QLabel("TCP 客户端")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.status_label.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        frame_layout.addLayout(header_layout)
        frame_layout.addWidget(self.status_label)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("127.0.0.1")
        self.host_input.textChanged.connect(self._on_host_changed)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.valueChanged.connect(self._on_port_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("十六进制（HEX）", TcpClientSendEncoding.HEX.value)
        self.mode_combo.addItem("ASCII 文本", TcpClientSendEncoding.ASCII.value)
        self.mode_combo.addItem("UTF-8 文本", TcpClientSendEncoding.UTF8.value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.addItem("无", TcpClientLineEnding.NONE.value)
        self.line_ending_combo.addItem("CR", TcpClientLineEnding.CR.value)
        self.line_ending_combo.addItem("LF", TcpClientLineEnding.LF.value)
        self.line_ending_combo.addItem("CRLF", TcpClientLineEnding.CRLF.value)
        self.line_ending_combo.currentIndexChanged.connect(self._on_line_ending_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem(CURRENT_DRAFT_TEXT, None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("预设名称")

        self.open_button = QPushButton("连接")
        self.open_button.clicked.connect(self.service.open_session)
        self.close_button = QPushButton("断开")
        self.close_button.clicked.connect(self.service.close_session)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.service.send_current_payload)
        self.save_preset_button = QPushButton("保存预设")
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button = QPushButton("删除预设")
        self.delete_preset_button.clicked.connect(self._on_delete_preset)

        self.send_text = QTextEdit()
        self.send_text.setMinimumHeight(self._EDITOR_MIN_HEIGHT)
        self.send_text.setPlaceholderText("十六进制：01 03 00 01\nASCII：PING\nUTF-8：hello 世界")
        self.send_text.textChanged.connect(self._on_send_text_changed)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("TcpClientTabs")
        self.content_tabs.addTab(self._build_connection_tab(), "连接配置")
        self.content_tabs.addTab(self._build_payload_tab(), "发送与预设")

        frame_layout.addWidget(self.content_tabs, 1)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def _build_connection_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        connection_frame, connection_layout = self._create_section(
            "连接参数",
            "目标主机和端口独立展示，让窄窗下的状态文案和表单字段不再互相争抢宽度。",
        )
        connection_grid = self._create_form_grid()
        connection_grid.addWidget(QLabel("主机"), 0, 0)
        connection_grid.addWidget(self.host_input, 0, 1)
        connection_grid.addWidget(QLabel("端口"), 0, 2)
        connection_grid.addWidget(self.port_input, 0, 3)
        connection_layout.addLayout(connection_grid)

        session_frame, session_layout = self._create_section(
            "会话控制",
            "连接建立后再切到发送页，避免主工作区同时堆叠连接和报文编辑控件。",
        )
        session_buttons = QHBoxLayout()
        session_buttons.setSpacing(8)
        session_buttons.addWidget(self.open_button)
        session_buttons.addWidget(self.close_button)
        session_buttons.addStretch(1)
        session_layout.addLayout(session_buttons)

        tab_layout.addWidget(connection_frame)
        tab_layout.addWidget(session_frame)
        tab_layout.addStretch(1)
        return tab

    def _build_payload_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        format_frame, format_layout = self._create_section(
            "发送格式",
            "编码、行结束符和预设拆到同一工作流页签，保留文本编辑区的可读高度。",
        )
        format_grid = self._create_form_grid()
        format_grid.addWidget(QLabel("发送模式"), 0, 0)
        format_grid.addWidget(self.mode_combo, 0, 1)
        format_grid.addWidget(QLabel("行结束符"), 0, 2)
        format_grid.addWidget(self.line_ending_combo, 0, 3)
        format_grid.addWidget(QLabel("预设"), 1, 0)
        format_grid.addWidget(self.preset_combo, 1, 1)
        format_grid.addWidget(QLabel("名称"), 1, 2)
        format_grid.addWidget(self.preset_name_input, 1, 3)
        format_layout.addLayout(format_grid)
        preset_actions = QHBoxLayout()
        preset_actions.setSpacing(8)
        preset_actions.addWidget(self.save_preset_button)
        preset_actions.addWidget(self.delete_preset_button)
        preset_actions.addStretch(1)
        format_layout.addLayout(preset_actions)

        payload_frame, payload_layout = self._create_section(
            "发送负载",
            "发送动作与负载编辑固定在同一页签，避免窗口缩小时文本区被挤成细条。",
        )
        payload_layout.addWidget(self.send_text, 1)
        payload_actions = QHBoxLayout()
        payload_actions.setSpacing(8)
        payload_actions.addWidget(self.send_button)
        payload_actions.addStretch(1)
        payload_layout.addLayout(payload_actions)

        tab_layout.addWidget(format_frame)
        tab_layout.addWidget(payload_frame, 1)
        return tab

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

    def refresh(self, snapshot: TcpClientSessionSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._set_text(self.host_input, snapshot.host)
            self._set_spin_value(self.port_input, snapshot.port)
            self._set_combo_to_data(self.mode_combo, snapshot.send_mode.value)
            self._set_combo_to_data(self.line_ending_combo, snapshot.line_ending.value)
            self._rebuild_presets(snapshot)
            self._set_plain_text(self.send_text, snapshot.send_text)
            self._set_text(self.preset_name_input, snapshot.selected_preset_name or "")
        finally:
            self._syncing_controls = False

        state_label = connection_state_text(snapshot.connection_state)
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        preset_label = snapshot.selected_preset_name or CURRENT_DRAFT_TEXT
        self.status_label.setText(
            f"状态：{state_label}    会话：{session_label}\n"
            f"目标：{snapshot.host}:{snapshot.port}    预设：{preset_label}"
        )
        self.error_label.setText(snapshot.last_error or READY_TEXT)

        is_connected = snapshot.connection_state == ConnectionState.CONNECTED
        is_busy = snapshot.connection_state == ConnectionState.CONNECTING
        self.open_button.setEnabled(bool(snapshot.host) and not is_connected and not is_busy)
        self.close_button.setEnabled(
            snapshot.connection_state
            in {ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.ERROR}
        )
        self.send_button.setEnabled(is_connected)
        self.delete_preset_button.setEnabled(bool(snapshot.selected_preset_name))

    def _on_host_changed(self, text: str) -> None:
        if self._syncing_controls:
            return
        self.service.set_host(text)

    def _on_port_changed(self, value: int) -> None:
        if self._syncing_controls:
            return
        self.service.set_port(value)

    def _on_mode_changed(self) -> None:
        if self._syncing_controls:
            return
        mode = self.mode_combo.currentData()
        if mode is not None:
            self.service.set_send_mode(TcpClientSendEncoding(str(mode)))

    def _on_line_ending_changed(self) -> None:
        if self._syncing_controls:
            return
        line_ending = self.line_ending_combo.currentData()
        if line_ending is not None:
            self.service.set_line_ending(TcpClientLineEnding(str(line_ending)))

    def _on_send_text_changed(self) -> None:
        if self._syncing_controls:
            return
        self.service.set_send_text(self.send_text.toPlainText())

    def _on_preset_selected(self) -> None:
        if self._syncing_controls:
            return
        self.service.load_preset(self.preset_combo.currentData())

    def _on_save_preset(self) -> None:
        self.service.save_preset(self.preset_name_input.text())

    def _on_delete_preset(self) -> None:
        self.service.delete_preset(self.preset_combo.currentData())

    def _set_text(self, widget: QLineEdit, text: str) -> None:
        if widget.text() == text:
            return
        widget.blockSignals(True)
        widget.setText(text)
        widget.blockSignals(False)

    def _set_spin_value(self, widget: QSpinBox, value: int) -> None:
        if widget.value() == value:
            return
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)

    def _set_combo_to_data(self, widget: QComboBox, value: str | None) -> None:
        index = widget.findData(value)
        if index >= 0 and widget.currentIndex() != index:
            widget.blockSignals(True)
            widget.setCurrentIndex(index)
            widget.blockSignals(False)

    def _set_plain_text(self, widget: QTextEdit, text: str) -> None:
        if widget.toPlainText() == text:
            return
        widget.blockSignals(True)
        widget.setPlainText(text)
        widget.blockSignals(False)

    def _rebuild_presets(self, snapshot: TcpClientSessionSnapshot) -> None:
        current_data = [self.preset_combo.itemData(index) for index in range(self.preset_combo.count())]
        desired_data = [None, *snapshot.preset_names]
        if current_data != desired_data:
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            self.preset_combo.addItem(CURRENT_DRAFT_TEXT, None)
            for preset_name in snapshot.preset_names:
                self.preset_combo.addItem(preset_name, preset_name)
            self.preset_combo.blockSignals(False)
        self._set_combo_to_data(self.preset_combo, snapshot.selected_preset_name)

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

from protolink.application.tcp_server_service import (
    TcpServerLineEnding,
    TcpServerSendEncoding,
    TcpServerSessionService,
    TcpServerSessionSnapshot,
)
from protolink.core.transport import ConnectionState
from protolink.ui.text import CURRENT_DRAFT_TEXT, READY_TEXT, connection_state_text


class TcpServerPanel(QWidget):
    _LABEL_COLUMN_MIN_WIDTH = 88
    _EDITOR_MIN_HEIGHT = 170

    def __init__(self, service: TcpServerSessionService) -> None:
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
        title = QLabel("TCP 服务端")
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
        self.port_input.setRange(0, 65535)
        self.port_input.valueChanged.connect(self._on_port_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("十六进制（HEX）", TcpServerSendEncoding.HEX.value)
        self.mode_combo.addItem("ASCII 文本", TcpServerSendEncoding.ASCII.value)
        self.mode_combo.addItem("UTF-8 文本", TcpServerSendEncoding.UTF8.value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.addItem("无", TcpServerLineEnding.NONE.value)
        self.line_ending_combo.addItem("CR", TcpServerLineEnding.CR.value)
        self.line_ending_combo.addItem("LF", TcpServerLineEnding.LF.value)
        self.line_ending_combo.addItem("CRLF", TcpServerLineEnding.CRLF.value)
        self.line_ending_combo.currentIndexChanged.connect(self._on_line_ending_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem(CURRENT_DRAFT_TEXT, None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("预设名称")

        self.client_target_combo = QComboBox()
        self.client_target_combo.addItem("广播", None)
        self.client_target_combo.currentIndexChanged.connect(self._on_client_target_changed)

        self.open_button = QPushButton("开启")
        self.open_button.clicked.connect(self.service.open_session)
        self.close_button = QPushButton("断开")
        self.close_button.clicked.connect(self.service.close_session)
        self.send_button = QPushButton("广播")
        self.send_button.clicked.connect(self.service.send_current_payload)
        self.save_preset_button = QPushButton("保存预设")
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button = QPushButton("删除预设")
        self.delete_preset_button.clicked.connect(self._on_delete_preset)

        self.send_text = QTextEdit()
        self.send_text.setMinimumHeight(self._EDITOR_MIN_HEIGHT)
        self.send_text.setPlaceholderText("十六进制：01 03 00 01\nASCII：READY\nUTF-8：hello 世界")
        self.send_text.textChanged.connect(self._on_send_text_changed)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("TcpServerTabs")
        self.content_tabs.addTab(self._build_listen_tab(), "监听配置")
        self.content_tabs.addTab(self._build_dispatch_tab(), "发送与目标")

        frame_layout.addWidget(self.content_tabs, 1)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def _build_listen_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        listen_frame, listen_layout = self._create_section(
            "监听参数",
            "监听地址与端口拆开显示，减少状态区、目标客户端和预设同时占据一行的情况。",
        )
        listen_grid = self._create_form_grid()
        listen_grid.addWidget(QLabel("主机"), 0, 0)
        listen_grid.addWidget(self.host_input, 0, 1)
        listen_grid.addWidget(QLabel("端口"), 0, 2)
        listen_grid.addWidget(self.port_input, 0, 3)
        listen_layout.addLayout(listen_grid)

        preset_frame, preset_layout = self._create_section(
            "预设管理",
            "监听参数与发送格式一起保存为预设，恢复配置时不需要滚动寻找字段。",
        )
        preset_grid = self._create_form_grid()
        preset_grid.addWidget(QLabel("预设"), 0, 0)
        preset_grid.addWidget(self.preset_combo, 0, 1)
        preset_grid.addWidget(QLabel("名称"), 0, 2)
        preset_grid.addWidget(self.preset_name_input, 0, 3)
        preset_layout.addLayout(preset_grid)
        preset_actions = QHBoxLayout()
        preset_actions.setSpacing(8)
        preset_actions.addWidget(self.save_preset_button)
        preset_actions.addWidget(self.delete_preset_button)
        preset_actions.addStretch(1)
        preset_layout.addLayout(preset_actions)

        session_frame, session_layout = self._create_section(
            "会话控制",
            "监听建立后，再切到发送页选择广播或指定客户端。",
        )
        session_buttons = QHBoxLayout()
        session_buttons.setSpacing(8)
        session_buttons.addWidget(self.open_button)
        session_buttons.addWidget(self.close_button)
        session_buttons.addStretch(1)
        session_layout.addLayout(session_buttons)

        tab_layout.addWidget(listen_frame)
        tab_layout.addWidget(preset_frame)
        tab_layout.addWidget(session_frame)
        tab_layout.addStretch(1)
        return tab

    def _build_dispatch_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        dispatch_frame, dispatch_layout = self._create_section(
            "发送目标",
            "把编码参数、目标客户端和实际负载放到同一工作面，缩小时仍能先看清要发给谁。",
        )
        dispatch_grid = self._create_form_grid()
        dispatch_grid.addWidget(QLabel("发送模式"), 0, 0)
        dispatch_grid.addWidget(self.mode_combo, 0, 1)
        dispatch_grid.addWidget(QLabel("行结束符"), 0, 2)
        dispatch_grid.addWidget(self.line_ending_combo, 0, 3)
        dispatch_grid.addWidget(QLabel("目标客户端"), 1, 0)
        dispatch_grid.addWidget(self.client_target_combo, 1, 1, 1, 2)
        dispatch_grid.addWidget(self.send_button, 1, 3)
        dispatch_layout.addLayout(dispatch_grid)
        dispatch_layout.addWidget(self.send_text, 1)

        tab_layout.addWidget(dispatch_frame, 1)
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

    def refresh(self, snapshot: TcpServerSessionSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._set_text(self.host_input, snapshot.host)
            self._set_spin_value(self.port_input, snapshot.port)
            self._set_combo_to_data(self.mode_combo, snapshot.send_mode.value)
            self._set_combo_to_data(self.line_ending_combo, snapshot.line_ending.value)
            self._rebuild_presets(snapshot)
            self._rebuild_client_targets(snapshot)
            self._set_plain_text(self.send_text, snapshot.send_text)
            self._set_text(self.preset_name_input, snapshot.selected_preset_name or "")
        finally:
            self._syncing_controls = False

        state_label = connection_state_text(snapshot.connection_state)
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        target_label = snapshot.selected_client_peer or "广播"
        preset_label = snapshot.selected_preset_name or CURRENT_DRAFT_TEXT
        self.status_label.setText(
            f"状态：{state_label}    会话：{session_label}\n"
            f"监听：{snapshot.host}:{snapshot.port}    客户端数：{snapshot.client_count}\n"
            f"目标：{target_label}    预设：{preset_label}"
        )
        self.error_label.setText(snapshot.last_error or READY_TEXT)

        is_connected = snapshot.connection_state == ConnectionState.CONNECTED
        is_busy = snapshot.connection_state == ConnectionState.CONNECTING
        self.open_button.setEnabled(bool(snapshot.host) and not is_connected and not is_busy)
        self.close_button.setEnabled(
            snapshot.connection_state
            in {ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.ERROR}
        )
        self.send_button.setEnabled(is_connected and snapshot.client_count > 0)
        self.send_button.setText("发送到客户端" if snapshot.selected_client_peer else "广播")
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
            self.service.set_send_mode(TcpServerSendEncoding(str(mode)))

    def _on_line_ending_changed(self) -> None:
        if self._syncing_controls:
            return
        line_ending = self.line_ending_combo.currentData()
        if line_ending is not None:
            self.service.set_line_ending(TcpServerLineEnding(str(line_ending)))

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

    def _on_client_target_changed(self) -> None:
        if self._syncing_controls:
            return
        self.service.set_selected_client_peer(self.client_target_combo.currentData())

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

    def _set_combo_to_data(self, widget: QComboBox, value: object | None) -> None:
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

    def _rebuild_presets(self, snapshot: TcpServerSessionSnapshot) -> None:
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

    def _rebuild_client_targets(self, snapshot: TcpServerSessionSnapshot) -> None:
        current_data = [self.client_target_combo.itemData(index) for index in range(self.client_target_combo.count())]
        desired_data = [None, *snapshot.connected_clients]
        if current_data != desired_data:
            self.client_target_combo.blockSignals(True)
            self.client_target_combo.clear()
            self.client_target_combo.addItem("广播", None)
            for peer in snapshot.connected_clients:
                self.client_target_combo.addItem(peer, peer)
            self.client_target_combo.blockSignals(False)
        self._set_combo_to_data(self.client_target_combo, snapshot.selected_client_peer)

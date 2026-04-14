from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.serial_service import (
    SerialLineEnding,
    SerialSendEncoding,
    SerialSessionService,
    SerialSessionSnapshot,
)
from protolink.core.transport import ConnectionState
from protolink.ui.text import CURRENT_DRAFT_TEXT, READY_TEXT, connection_state_text


COMMON_BAUDRATES = ("9600", "19200", "38400", "57600", "115200")


class SerialStudioPanel(QWidget):
    def __init__(self, service: SerialSessionService) -> None:
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
        title = QLabel("串口工作台")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.target_combo = QComboBox()
        self.target_combo.setEditable(True)
        self.target_combo.editTextChanged.connect(self._on_target_changed)

        self.baudrate_combo = QComboBox()
        self.baudrate_combo.setEditable(True)
        self.baudrate_combo.addItems(COMMON_BAUDRATES)
        self.baudrate_combo.currentTextChanged.connect(self._on_baudrate_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("十六进制（HEX）", SerialSendEncoding.HEX)
        self.mode_combo.addItem("ASCII 文本", SerialSendEncoding.ASCII)
        self.mode_combo.addItem("UTF-8 文本", SerialSendEncoding.UTF8)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.addItem("无", SerialLineEnding.NONE)
        self.line_ending_combo.addItem("CR", SerialLineEnding.CR)
        self.line_ending_combo.addItem("LF", SerialLineEnding.LF)
        self.line_ending_combo.addItem("CRLF", SerialLineEnding.CRLF)
        self.line_ending_combo.currentIndexChanged.connect(self._on_line_ending_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem(CURRENT_DRAFT_TEXT, None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("预设名称")

        self.refresh_button = QPushButton("刷新端口")
        self.refresh_button.clicked.connect(self.service.refresh_ports)
        self.open_button = QPushButton("打开")
        self.open_button.clicked.connect(self.service.open_session)
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.service.close_session)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.service.send_current_payload)
        self.save_preset_button = QPushButton("保存预设")
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button = QPushButton("删除预设")
        self.delete_preset_button.clicked.connect(self._on_delete_preset)

        self.send_text = QTextEdit()
        self.send_text.setPlaceholderText("十六进制：01 03 00 01\nASCII：HELLO\nUTF-8：你好")
        self.send_text.textChanged.connect(self._on_send_text_changed)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("目标"), 0, 0)
        grid.addWidget(self.target_combo, 0, 1, 1, 2)
        grid.addWidget(QLabel("波特率"), 0, 3)
        grid.addWidget(self.baudrate_combo, 0, 4)
        grid.addWidget(QLabel("发送模式"), 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)
        grid.addWidget(QLabel("行结束符"), 1, 2)
        grid.addWidget(self.line_ending_combo, 1, 3)
        grid.addWidget(self.refresh_button, 1, 4)
        grid.addWidget(QLabel("预设"), 2, 0)
        grid.addWidget(self.preset_combo, 2, 1)
        grid.addWidget(self.preset_name_input, 2, 2)
        grid.addWidget(self.save_preset_button, 2, 3)
        grid.addWidget(self.delete_preset_button, 2, 4)
        grid.addWidget(self.open_button, 3, 3)
        grid.addWidget(self.close_button, 3, 4)

        frame_layout.addLayout(header_layout)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(QLabel("帧负载"))
        frame_layout.addWidget(self.send_text)
        frame_layout.addWidget(self.send_button)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def refresh(self, snapshot: SerialSessionSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._rebuild_targets(snapshot)
            self._rebuild_presets(snapshot)
            self._set_combo_to_text(self.baudrate_combo, str(snapshot.baudrate))
            self._set_mode(snapshot.send_mode)
            self._set_line_ending(snapshot.line_ending)
            self._set_send_text(snapshot.send_text)
            self._set_preset_name(snapshot.selected_preset_name or "")
        finally:
            self._syncing_controls = False

        state_label = connection_state_text(snapshot.connection_state)
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        preset_label = snapshot.selected_preset_name or CURRENT_DRAFT_TEXT
        self.status_label.setText(
            f"状态: {state_label}    会话: {session_label}    预设: {preset_label}"
        )
        self.error_label.setText(snapshot.last_error or READY_TEXT)

        is_connected = snapshot.connection_state == ConnectionState.CONNECTED
        is_busy = snapshot.connection_state == ConnectionState.CONNECTING
        self.open_button.setEnabled(bool(snapshot.target) and not is_connected and not is_busy)
        self.close_button.setEnabled(snapshot.connection_state in {ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.ERROR})
        self.send_button.setEnabled(is_connected)
        self.delete_preset_button.setEnabled(bool(snapshot.selected_preset_name))

    def _on_target_changed(self, text: str) -> None:
        if self._syncing_controls:
            return
        self.service.set_target(text)

    def _on_baudrate_changed(self, text: str) -> None:
        if self._syncing_controls or not text.strip():
            return
        self.service.set_baudrate(text)

    def _on_mode_changed(self) -> None:
        if self._syncing_controls:
            return
        mode = self.mode_combo.currentData()
        if mode is not None:
            self.service.set_send_mode(SerialSendEncoding(str(mode)))

    def _on_line_ending_changed(self) -> None:
        if self._syncing_controls:
            return
        line_ending = self.line_ending_combo.currentData()
        if line_ending is not None:
            self.service.set_line_ending(SerialLineEnding(str(line_ending)))

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

    def _rebuild_targets(self, snapshot: SerialSessionSnapshot) -> None:
        current_items = [self.target_combo.itemText(index) for index in range(self.target_combo.count())]
        target_items = [port.device for port in snapshot.available_ports]
        if snapshot.target and snapshot.target not in target_items:
            target_items.insert(0, snapshot.target)
        if current_items != target_items:
            self.target_combo.blockSignals(True)
            self.target_combo.clear()
            self.target_combo.addItems(target_items)
            self.target_combo.blockSignals(False)
        if self.target_combo.currentText() != snapshot.target:
            self.target_combo.setEditText(snapshot.target)

    def _rebuild_presets(self, snapshot: SerialSessionSnapshot) -> None:
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

    def _set_combo_to_text(self, combo: QComboBox, text: str) -> None:
        if combo.currentText() == text:
            return
        combo.blockSignals(True)
        if combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)
        combo.blockSignals(False)

    def _set_mode(self, mode: SerialSendEncoding) -> None:
        index = self.mode_combo.findData(mode.value)
        if index >= 0 and self.mode_combo.currentIndex() != index:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(index)
            self.mode_combo.blockSignals(False)

    def _set_line_ending(self, line_ending: SerialLineEnding) -> None:
        index = self.line_ending_combo.findData(line_ending.value)
        if index >= 0 and self.line_ending_combo.currentIndex() != index:
            self.line_ending_combo.blockSignals(True)
            self.line_ending_combo.setCurrentIndex(index)
            self.line_ending_combo.blockSignals(False)

    def _set_send_text(self, text: str) -> None:
        if self.send_text.toPlainText() == text:
            return
        self.send_text.blockSignals(True)
        self.send_text.setPlainText(text)
        self.send_text.blockSignals(False)

    def _set_preset_name(self, text: str) -> None:
        if self.preset_name_input.text() == text:
            return
        self.preset_name_input.blockSignals(True)
        self.preset_name_input.setText(text)
        self.preset_name_input.blockSignals(False)

    def _set_combo_to_data(self, combo: QComboBox, value: object | None) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

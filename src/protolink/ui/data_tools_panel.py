from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.data_tools_service import DataToolMode, DataToolsService, DataToolsSnapshot
from protolink.ui.text import READY_TEXT


class DataToolsPanel(QWidget):
    def __init__(self, service: DataToolsService) -> None:
        super().__init__()
        self.service = service
        self._syncing = False
        self._build_ui()
        self.service.subscribe(self.refresh)
        self.refresh(self.service.snapshot)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame = QFrame()
        frame.setObjectName("Panel")
        grid = QGridLayout(frame)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        title = QLabel("数据工具")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.notice_label = QLabel("确定性辅助工具，仅提供格式转换与校验，不依赖实时传输。")
        self.notice_label.setObjectName("MetaLabel")
        self.notice_label.setWordWrap(True)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("UTF-8 → 十六进制", DataToolMode.UTF8_TO_HEX)
        self.mode_combo.addItem("十六进制 → UTF-8", DataToolMode.HEX_TO_UTF8)
        self.mode_combo.addItem("十六进制 → Modbus CRC16", DataToolMode.HEX_MODBUS_CRC16)
        self.mode_combo.addItem("美化 JSON", DataToolMode.PRETTY_JSON)
        self.mode_combo.addItem("UTF-8 → Base64 编码", DataToolMode.UTF8_TO_BASE64)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.input_text = QTextEdit()
        self.input_text.textChanged.connect(self._on_input_changed)
        self.run_button = QPushButton("运行工具")
        self.run_button.clicked.connect(self.service.run)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(title, 0, 0, 1, 2)
        grid.addWidget(self.status_label, 0, 2, 1, 2)
        grid.addWidget(self.notice_label, 1, 0, 1, 4)
        grid.addWidget(QLabel("工具"), 2, 0)
        grid.addWidget(self.mode_combo, 2, 1, 1, 3)
        grid.addWidget(QLabel("输入"), 3, 0)
        grid.addWidget(self.input_text, 3, 1, 1, 3)
        grid.addWidget(self.run_button, 4, 3)
        grid.addWidget(QLabel("输出"), 5, 0)
        grid.addWidget(self.output_text, 5, 1, 1, 3)
        grid.addWidget(QLabel("错误"), 6, 0)
        grid.addWidget(self.error_label, 6, 1, 1, 3)

        layout.addWidget(frame)

    def refresh(self, snapshot: DataToolsSnapshot) -> None:
        self._syncing = True
        try:
            index = self.mode_combo.findData(snapshot.selected_mode)
            if index >= 0:
                self.mode_combo.setCurrentIndex(index)
            if self.input_text.toPlainText() != snapshot.input_text:
                self.input_text.setPlainText(snapshot.input_text)
        finally:
            self._syncing = False

        selected_text = self.mode_combo.currentText() or snapshot.selected_mode.value
        self.status_label.setText(f"模式: {selected_text}    运行次数: {snapshot.execution_count}")
        self.output_text.setPlainText(snapshot.output_text)
        self.error_label.setText(snapshot.last_error or READY_TEXT)
        self.run_button.setEnabled(bool(snapshot.input_text.strip()))

    def _on_mode_changed(self) -> None:
        if self._syncing:
            return
        value = self.mode_combo.currentData()
        if value is not None:
            self.service.set_mode(value)

    def _on_input_changed(self) -> None:
        if self._syncing:
            return
        self.service.set_input_text(self.input_text.toPlainText())

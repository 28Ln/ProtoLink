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
    QVBoxLayout,
    QWidget,
)

from protolink.application.register_monitor_service import RegisterMonitorService, RegisterMonitorSnapshot
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.ui.text import READY_TEXT, register_byte_order_text, register_data_type_text


class RegisterMonitorPanel(QWidget):
    def __init__(self, service: RegisterMonitorService) -> None:
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
        title = QLabel("寄存器监视")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.point_combo = QComboBox()
        self.point_combo.addItem("选择点位", None)
        self.point_combo.currentIndexChanged.connect(self._on_point_selected)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("点位名称")
        self.address_input = QSpinBox()
        self.address_input.setRange(0, 65535)

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

        self.upsert_button = QPushButton("保存点位")
        self.upsert_button.clicked.connect(self._on_upsert_point)
        self.delete_button = QPushButton("删除点位")
        self.delete_button.clicked.connect(self._on_delete_point)

        self.register_words_input = QLineEdit()
        self.register_words_input.setPlaceholderText("寄存器字（例如 0x0000 0x3FC0）")
        self.register_words_input.textChanged.connect(self.service.set_register_words_text)
        self.decode_button = QPushButton("解码")
        self.decode_button.clicked.connect(self.service.decode_current_words)

        self.decoded_value_label = QLabel("解码：-")
        self.decoded_value_label.setObjectName("MetaLabel")
        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("点位"), 0, 0)
        grid.addWidget(self.point_combo, 0, 1, 1, 2)
        grid.addWidget(self.delete_button, 0, 3)
        grid.addWidget(QLabel("名称"), 1, 0)
        grid.addWidget(self.name_input, 1, 1)
        grid.addWidget(QLabel("地址"), 1, 2)
        grid.addWidget(self.address_input, 1, 3)
        grid.addWidget(QLabel("类型"), 2, 0)
        grid.addWidget(self.data_type_combo, 2, 1)
        grid.addWidget(QLabel("字节序"), 2, 2)
        grid.addWidget(self.byte_order_combo, 2, 3)
        grid.addWidget(QLabel("缩放"), 3, 0)
        grid.addWidget(self.scale_input, 3, 1)
        grid.addWidget(QLabel("偏移"), 3, 2)
        grid.addWidget(self.offset_input, 3, 3)
        grid.addWidget(QLabel("单位"), 4, 0)
        grid.addWidget(self.unit_input, 4, 1)
        grid.addWidget(self.upsert_button, 4, 3)
        grid.addWidget(QLabel("寄存器"), 5, 0)
        grid.addWidget(self.register_words_input, 5, 1, 1, 2)
        grid.addWidget(self.decode_button, 5, 3)

        frame_layout.addLayout(header_layout)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(self.decoded_value_label)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def refresh(self, snapshot: RegisterMonitorSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._rebuild_point_combo(snapshot)
            self._set_text(self.register_words_input, snapshot.register_words_text)
            self._set_text(self.name_input, snapshot.selected_point_name or "")
        finally:
            self._syncing_controls = False

        selected = snapshot.selected_point_name or "-"
        live_source = snapshot.last_live_source or "-"
        self.status_label.setText(f"点位：{len(snapshot.point_names)}    选中：{selected}    来源：{live_source}")
        self.decoded_value_label.setText(f"解码：{snapshot.decoded_value or '-'}")
        self.error_label.setText(snapshot.last_error or READY_TEXT)
        self.delete_button.setEnabled(bool(snapshot.selected_point_name))

    def _on_point_selected(self) -> None:
        if self._syncing_controls:
            return
        self.service.select_point(self.point_combo.currentData())

    def _on_upsert_point(self) -> None:
        data_type = self.data_type_combo.currentData()
        byte_order = self.byte_order_combo.currentData()
        if not isinstance(data_type, RegisterDataType):
            data_type = RegisterDataType(str(data_type))
        if not isinstance(byte_order, RegisterByteOrder):
            byte_order = RegisterByteOrder(str(byte_order))
        self.service.upsert_point(
            name=self.name_input.text(),
            address=self.address_input.value(),
            data_type=data_type,
            byte_order=byte_order,
            scale=self.scale_input.text(),
            offset=self.offset_input.text(),
            unit=self.unit_input.text(),
        )

    def _on_delete_point(self) -> None:
        self.service.remove_point(self.point_combo.currentData())

    def _rebuild_point_combo(self, snapshot: RegisterMonitorSnapshot) -> None:
        current_data = [self.point_combo.itemData(index) for index in range(self.point_combo.count())]
        desired_data = [None, *snapshot.point_names]
        if current_data != desired_data:
            self.point_combo.blockSignals(True)
            self.point_combo.clear()
            self.point_combo.addItem("选择点位", None)
            for point_name in snapshot.point_names:
                self.point_combo.addItem(point_name, point_name)
            self.point_combo.blockSignals(False)
        self._set_combo_to_data(self.point_combo, snapshot.selected_point_name)

    def _set_combo_to_data(self, combo: QComboBox, value: object | None) -> None:
        index = combo.findData(value)
        if index >= 0 and combo.currentIndex() != index:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _set_text(self, widget: QLineEdit, text: str) -> None:
        if widget.text() == text:
            return
        widget.blockSignals(True)
        widget.setText(text)
        widget.blockSignals(False)

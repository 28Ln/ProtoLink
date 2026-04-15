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
    QVBoxLayout,
    QWidget,
)

from protolink.application.register_monitor_service import RegisterMonitorService, RegisterMonitorSnapshot
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.ui.text import READY_TEXT, register_byte_order_text, register_data_type_text


class RegisterMonitorPanel(QWidget):
    _LABEL_COLUMN_MIN_WIDTH = 76

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
        self.status_label.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        frame_layout.addLayout(header_layout)
        frame_layout.addWidget(self.status_label)

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

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("RegisterMonitorTabs")
        self.content_tabs.addTab(self._build_point_tab(), "点位配置")
        self.content_tabs.addTab(self._build_decode_tab(), "解码预览")

        frame_layout.addWidget(self.content_tabs)
        layout.addWidget(frame)

    def _build_point_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        selection_frame, selection_layout = self._create_section(
            "当前点位",
            "先选择已有点位，或直接在下方填写新的点位定义。",
        )
        selection_grid = self._create_form_grid()
        selection_grid.addWidget(QLabel("点位"), 0, 0)
        selection_grid.addWidget(self.point_combo, 0, 1, 1, 2)
        selection_grid.addWidget(self.delete_button, 0, 3)
        selection_layout.addLayout(selection_grid)

        definition_frame, definition_layout = self._create_section(
            "点位定义",
            "将寄存器地址、数据类型和换算参数拆开配置，避免中文标签在窄窗下互相挤压。",
        )
        definition_grid = self._create_form_grid()
        definition_grid.addWidget(QLabel("名称"), 0, 0)
        definition_grid.addWidget(self.name_input, 0, 1)
        definition_grid.addWidget(QLabel("地址"), 0, 2)
        definition_grid.addWidget(self.address_input, 0, 3)
        definition_grid.addWidget(QLabel("类型"), 1, 0)
        definition_grid.addWidget(self.data_type_combo, 1, 1)
        definition_grid.addWidget(QLabel("字节序"), 1, 2)
        definition_grid.addWidget(self.byte_order_combo, 1, 3)
        definition_grid.addWidget(QLabel("缩放"), 2, 0)
        definition_grid.addWidget(self.scale_input, 2, 1)
        definition_grid.addWidget(QLabel("偏移"), 2, 2)
        definition_grid.addWidget(self.offset_input, 2, 3)
        definition_grid.addWidget(QLabel("单位"), 3, 0)
        definition_grid.addWidget(self.unit_input, 3, 1, 1, 2)
        definition_grid.addWidget(self.upsert_button, 3, 3)
        definition_layout.addLayout(definition_grid)

        tab_layout.addWidget(selection_frame)
        tab_layout.addWidget(definition_frame)
        tab_layout.addStretch(1)
        return tab

    def _build_decode_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        input_frame, input_layout = self._create_section(
            "寄存器输入",
            "将原始寄存器字按空格输入后再解码，适合快速比对现场返回值。",
        )
        input_grid = self._create_form_grid()
        input_grid.addWidget(QLabel("寄存器"), 0, 0)
        input_grid.addWidget(self.register_words_input, 0, 1, 1, 2)
        input_grid.addWidget(self.decode_button, 0, 3)
        input_layout.addLayout(input_grid)

        result_frame, result_layout = self._create_section("解码结果")
        result_layout.addWidget(self.decoded_value_label)
        result_layout.addWidget(self.error_label)

        tab_layout.addWidget(input_frame)
        tab_layout.addWidget(result_frame)
        tab_layout.addStretch(1)
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

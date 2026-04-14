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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.mqtt_client_service import (
    MqttClientSendEncoding,
    MqttClientSessionService,
    MqttClientSessionSnapshot,
)
from protolink.core.transport import ConnectionState
from protolink.ui.text import CURRENT_DRAFT_TEXT, READY_TEXT, connection_state_text


class MqttClientPanel(QWidget):
    def __init__(self, service: MqttClientSessionService) -> None:
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
        title = QLabel("MQTT 客户端")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("127.0.0.1")
        self.host_input.textChanged.connect(self._on_host_changed)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.valueChanged.connect(self._on_port_changed)

        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("可选客户端 ID")
        self.client_id_input.textChanged.connect(self._on_client_id_changed)

        self.publish_topic_input = QLineEdit()
        self.publish_topic_input.setPlaceholderText("主题/分区")
        self.publish_topic_input.textChanged.connect(self._on_publish_topic_changed)

        self.subscribe_topic_input = QLineEdit()
        self.subscribe_topic_input.setPlaceholderText("主题/分区")
        self.subscribe_topic_input.textChanged.connect(self._on_subscribe_topic_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("十六进制（HEX）", MqttClientSendEncoding.HEX.value)
        self.mode_combo.addItem("ASCII 文本", MqttClientSendEncoding.ASCII.value)
        self.mode_combo.addItem("UTF-8 文本", MqttClientSendEncoding.UTF8.value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem(CURRENT_DRAFT_TEXT, None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("预设名称")

        self.open_button = QPushButton("连接")
        self.open_button.clicked.connect(self.service.open_session)
        self.close_button = QPushButton("断开")
        self.close_button.clicked.connect(self.service.close_session)
        self.subscribe_button = QPushButton("订阅")
        self.subscribe_button.clicked.connect(self.service.subscribe_current_topic)
        self.send_button = QPushButton("发布")
        self.send_button.clicked.connect(self.service.send_current_payload)
        self.save_preset_button = QPushButton("保存预设")
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button = QPushButton("删除预设")
        self.delete_preset_button.clicked.connect(self._on_delete_preset)

        self.subscribed_topics_label = QLabel()
        self.subscribed_topics_label.setObjectName("MetaLabel")
        self.subscribed_topics_label.setWordWrap(True)

        self.send_text = QTextEdit()
        self.send_text.setPlaceholderText("十六进制：01 03 00 01\nASCII：READY\nUTF-8：hello 世界")
        self.send_text.textChanged.connect(self._on_send_text_changed)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("主机"), 0, 0)
        grid.addWidget(self.host_input, 0, 1)
        grid.addWidget(QLabel("端口"), 0, 2)
        grid.addWidget(self.port_input, 0, 3)
        grid.addWidget(QLabel("客户端 ID"), 1, 0)
        grid.addWidget(self.client_id_input, 1, 1, 1, 3)
        grid.addWidget(QLabel("发布主题"), 2, 0)
        grid.addWidget(self.publish_topic_input, 2, 1, 1, 3)
        grid.addWidget(QLabel("订阅主题"), 3, 0)
        grid.addWidget(self.subscribe_topic_input, 3, 1, 1, 3)
        grid.addWidget(QLabel("发送模式"), 4, 0)
        grid.addWidget(self.mode_combo, 4, 1)
        grid.addWidget(QLabel("预设"), 4, 2)
        grid.addWidget(self.preset_combo, 4, 3)
        grid.addWidget(self.preset_name_input, 5, 0, 1, 2)
        grid.addWidget(self.save_preset_button, 5, 2)
        grid.addWidget(self.delete_preset_button, 5, 3)
        grid.addWidget(self.open_button, 6, 1)
        grid.addWidget(self.close_button, 6, 2)
        grid.addWidget(self.subscribe_button, 6, 3)
        grid.addWidget(self.send_button, 6, 4)

        frame_layout.addLayout(header_layout)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(QLabel("已订阅主题"))
        frame_layout.addWidget(self.subscribed_topics_label)
        frame_layout.addWidget(QLabel("帧负载"))
        frame_layout.addWidget(self.send_text)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def refresh(self, snapshot: MqttClientSessionSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._set_text(self.host_input, snapshot.host)
            self._set_spin_value(self.port_input, snapshot.port)
            self._set_text(self.client_id_input, snapshot.client_id)
            self._set_text(self.publish_topic_input, snapshot.publish_topic)
            self._set_text(self.subscribe_topic_input, snapshot.subscribe_topic)
            self._set_combo_to_data(self.mode_combo, snapshot.send_mode.value)
            self._rebuild_presets(snapshot)
            self._set_plain_text(self.send_text, snapshot.send_text)
            self._set_text(self.preset_name_input, snapshot.selected_preset_name or "")
        finally:
            self._syncing_controls = False

        state_label = connection_state_text(snapshot.connection_state)
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        preset_label = snapshot.selected_preset_name or CURRENT_DRAFT_TEXT
        self.status_label.setText(
            f"状态: {state_label}    会话: {session_label}    预设: {preset_label}"
        )
        topics_text = "、".join(snapshot.subscribed_topics) if snapshot.subscribed_topics else "（无）"
        self.subscribed_topics_label.setText(topics_text)
        self.error_label.setText(snapshot.last_error or READY_TEXT)

        is_connected = snapshot.connection_state == ConnectionState.CONNECTED
        is_busy = snapshot.connection_state == ConnectionState.CONNECTING
        self.open_button.setEnabled(bool(snapshot.host) and not is_connected and not is_busy)
        self.close_button.setEnabled(snapshot.connection_state in {ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.ERROR})
        self.subscribe_button.setEnabled(is_connected and bool(snapshot.subscribe_topic))
        self.send_button.setEnabled(is_connected and bool(snapshot.publish_topic))
        self.delete_preset_button.setEnabled(bool(snapshot.selected_preset_name))

    def _on_host_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_host(text)

    def _on_port_changed(self, value: int) -> None:
        if not self._syncing_controls:
            self.service.set_port(value)

    def _on_client_id_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_client_id(text)

    def _on_publish_topic_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_publish_topic(text)

    def _on_subscribe_topic_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_subscribe_topic(text)

    def _on_mode_changed(self) -> None:
        if self._syncing_controls:
            return
        mode = self.mode_combo.currentData()
        if mode is not None:
            self.service.set_send_mode(MqttClientSendEncoding(str(mode)))

    def _on_send_text_changed(self) -> None:
        if not self._syncing_controls:
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

    def _set_combo_to_data(self, widget: QComboBox, value: str) -> None:
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

    def _rebuild_presets(self, snapshot: MqttClientSessionSnapshot) -> None:
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

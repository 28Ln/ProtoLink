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

from protolink.application.mqtt_server_service import MqttServerSendEncoding, MqttServerSessionService, MqttServerSessionSnapshot
from protolink.core.transport import ConnectionState


class MqttServerPanel(QWidget):
    def __init__(self, service: MqttServerSessionService) -> None:
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
        title = QLabel("MQTT Server Controls")
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

        self.publish_topic_input = QLineEdit()
        self.publish_topic_input.setPlaceholderText("bench/topic")
        self.publish_topic_input.textChanged.connect(self._on_publish_topic_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("HEX", MqttServerSendEncoding.HEX.value)
        self.mode_combo.addItem("ASCII", MqttServerSendEncoding.ASCII.value)
        self.mode_combo.addItem("UTF-8", MqttServerSendEncoding.UTF8.value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Current Draft", None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("Preset name")

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.service.open_session)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.service.close_session)
        self.send_button = QPushButton("Publish")
        self.send_button.clicked.connect(self.service.send_current_payload)
        self.save_preset_button = QPushButton("Save Preset")
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button = QPushButton("Delete Preset")
        self.delete_preset_button.clicked.connect(self._on_delete_preset)

        self.send_text = QTextEdit()
        self.send_text.setPlaceholderText("HEX: 01 03 00 01\nASCII: READY\nUTF-8: hello 世界")
        self.send_text.textChanged.connect(self._on_send_text_changed)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("Host"), 0, 0)
        grid.addWidget(self.host_input, 0, 1)
        grid.addWidget(QLabel("Port"), 0, 2)
        grid.addWidget(self.port_input, 0, 3)
        grid.addWidget(QLabel("Publish Topic"), 1, 0)
        grid.addWidget(self.publish_topic_input, 1, 1, 1, 3)
        grid.addWidget(QLabel("Send Mode"), 2, 0)
        grid.addWidget(self.mode_combo, 2, 1)
        grid.addWidget(QLabel("Preset"), 2, 2)
        grid.addWidget(self.preset_combo, 2, 3)
        grid.addWidget(self.preset_name_input, 3, 0, 1, 2)
        grid.addWidget(self.save_preset_button, 3, 2)
        grid.addWidget(self.delete_preset_button, 3, 3)
        grid.addWidget(self.open_button, 4, 1)
        grid.addWidget(self.close_button, 4, 2)
        grid.addWidget(self.send_button, 4, 3)

        frame_layout.addLayout(header_layout)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(QLabel("Payload"))
        frame_layout.addWidget(self.send_text)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)

    def refresh(self, snapshot: MqttServerSessionSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._set_text(self.host_input, snapshot.host)
            self._set_spin_value(self.port_input, snapshot.port)
            self._set_text(self.publish_topic_input, snapshot.publish_topic)
            self._set_combo_to_data(self.mode_combo, snapshot.send_mode.value)
            self._rebuild_presets(snapshot)
            self._set_plain_text(self.send_text, snapshot.send_text)
            self._set_text(self.preset_name_input, snapshot.selected_preset_name or "")
        finally:
            self._syncing_controls = False

        state_label = snapshot.connection_state.value.upper()
        session_label = snapshot.active_session_id[:8] if snapshot.active_session_id else "-"
        preset_label = snapshot.selected_preset_name or "draft"
        self.status_label.setText(f"State: {state_label}    Session: {session_label}    Preset: {preset_label}")
        self.error_label.setText(snapshot.last_error or "Ready.")

        is_connected = snapshot.connection_state == ConnectionState.CONNECTED
        is_busy = snapshot.connection_state == ConnectionState.CONNECTING
        self.open_button.setEnabled(bool(snapshot.host) and not is_connected and not is_busy)
        self.close_button.setEnabled(snapshot.connection_state in {ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.ERROR})
        self.send_button.setEnabled(is_connected and bool(snapshot.publish_topic))
        self.delete_preset_button.setEnabled(bool(snapshot.selected_preset_name))

    def _on_host_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_host(text)

    def _on_port_changed(self, value: int) -> None:
        if not self._syncing_controls:
            self.service.set_port(value)

    def _on_publish_topic_changed(self, text: str) -> None:
        if not self._syncing_controls:
            self.service.set_publish_topic(text)

    def _on_mode_changed(self) -> None:
        if self._syncing_controls:
            return
        mode = self.mode_combo.currentData()
        if mode is not None:
            self.service.set_send_mode(MqttServerSendEncoding(str(mode)))

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

    def _rebuild_presets(self, snapshot: MqttServerSessionSnapshot) -> None:
        current_data = [self.preset_combo.itemData(index) for index in range(self.preset_combo.count())]
        desired_data = [None, *snapshot.preset_names]
        if current_data != desired_data:
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            self.preset_combo.addItem("Current Draft", None)
            for preset_name in snapshot.preset_names:
                self.preset_combo.addItem(preset_name, preset_name)
            self.preset_combo.blockSignals(False)
        self._set_combo_to_data(self.preset_combo, snapshot.selected_preset_name)

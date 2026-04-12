from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.network_tools_service import NetworkToolsService, NetworkToolsSnapshot


class NetworkToolsPanel(QWidget):
    def __init__(self, service: NetworkToolsService) -> None:
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

        title = QLabel("Network Tools")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.notice_label = QLabel("Read-only diagnostics only. No network/system write operations are exposed.")
        self.notice_label.setObjectName("MetaLabel")
        self.notice_label.setWordWrap(True)
        self.read_only_notice = self.notice_label
        self.local_info_button = QPushButton("Refresh Local Info")
        self.local_info_button.clicked.connect(self.service.refresh_local_info)
        self.host_input = QLineEdit()
        self.target_host_input = self.host_input
        self.host_input.textChanged.connect(self._on_target_host_changed)
        self.port_spin = QSpinBox()
        self.target_port_spin = self.port_spin
        self.port_spin.setRange(1, 65535)
        self.port_spin.valueChanged.connect(self._on_target_port_changed)
        self.resolve_button = QPushButton("Resolve Host")
        self.resolve_button.clicked.connect(self.service.resolve_target)
        self.probe_button = QPushButton("Probe TCP")
        self.probe_button.clicked.connect(self.service.probe_tcp)
        self.local_text = QTextEdit()
        self.local_text.setReadOnly(True)
        self.resolve_text = QTextEdit()
        self.resolved_ips_text = self.resolve_text
        self.resolve_text.setReadOnly(True)
        self.probe_label = QLabel()
        self.probe_status_label = self.probe_label
        self.probe_label.setObjectName("MetaLabel")
        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(title, 0, 0, 1, 2)
        grid.addWidget(self.status_label, 0, 2, 1, 2)
        grid.addWidget(self.notice_label, 1, 0, 1, 4)
        grid.addWidget(self.local_info_button, 2, 3)
        grid.addWidget(QLabel("Target Host"), 3, 0)
        grid.addWidget(self.host_input, 3, 1, 1, 2)
        grid.addWidget(QLabel("Port"), 3, 3)
        grid.addWidget(self.port_spin, 3, 4)
        grid.addWidget(self.resolve_button, 4, 3)
        grid.addWidget(self.probe_button, 4, 4)
        grid.addWidget(QLabel("Local Info"), 5, 0)
        grid.addWidget(self.local_text, 5, 1, 1, 4)
        grid.addWidget(QLabel("Resolved Addresses"), 6, 0)
        grid.addWidget(self.resolve_text, 6, 1, 1, 4)
        grid.addWidget(QLabel("Probe Result"), 7, 0)
        grid.addWidget(self.probe_label, 7, 1, 1, 4)
        grid.addWidget(QLabel("Error"), 8, 0)
        grid.addWidget(self.error_label, 8, 1, 1, 4)

        layout.addWidget(frame)

    def refresh(self, snapshot: NetworkToolsSnapshot) -> None:
        self._syncing = True
        try:
            if self.host_input.text() != snapshot.target_host:
                self.host_input.setText(snapshot.target_host)
            self.port_spin.setValue(snapshot.target_port)
        finally:
            self._syncing = False

        self.status_label.setText(f"Runs: {snapshot.execution_count}    Host: {snapshot.local_hostname or '-'}")
        self.local_text.setPlainText("\n".join(snapshot.local_ip_addresses))
        self.resolve_text.setPlainText("\n".join(snapshot.resolved_ip_addresses))
        self.probe_label.setText(snapshot.tcp_probe_summary or "-")
        self.error_label.setText(snapshot.last_error or "Ready.")
        self._refresh_action_state(snapshot)

    def _on_target_host_changed(self) -> None:
        if self._syncing:
            return
        self.service.set_target_host(self.host_input.text())

    def _on_target_port_changed(self, value: int) -> None:
        if self._syncing:
            return
        self.service.set_target_port(value)

    def _refresh_action_state(self, snapshot: NetworkToolsSnapshot) -> None:
        has_host = bool(snapshot.target_host.strip())
        self.resolve_button.setEnabled(has_host)
        self.probe_button.setEnabled(has_host)

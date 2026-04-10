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

from protolink.application.rule_engine_service import RuleEngineService, RuleEngineSnapshot
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.rule_engine import AutomationAction, AutomationActionKind, AutomationRule
from protolink.core.transport import TransportKind


class AutomationRulesPanel(QWidget):
    def __init__(self, service: RuleEngineService) -> None:
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

        header = QHBoxLayout()
        title = QLabel("Automation Rules")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.profile_path_label = QLabel()
        self.profile_path_label.setObjectName("MetaLabel")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.rule_combo = QComboBox()
        self.rule_combo.addItem("Select Rule", None)
        self.rule_combo.currentIndexChanged.connect(self._on_rule_selected)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Rule name")

        self.action_combo = QComboBox()
        self.action_combo.addItem("Run Replay Plan", AutomationActionKind.RUN_REPLAY_PLAN)
        self.action_combo.addItem("Enable Auto Response", AutomationActionKind.SET_AUTO_RESPONSE_ENABLED)
        self.action_combo.addItem("Disable Auto Response", AutomationActionKind.SET_AUTO_RESPONSE_ENABLED)
        self.action_combo.addItem("Prepare Device Scan", AutomationActionKind.PREPARE_DEVICE_SCAN)
        self.action_combo.currentIndexChanged.connect(self._refresh_action_specific_controls)

        self.replay_path_input = QLineEdit()
        self.replay_path_input.setPlaceholderText("Replay plan path")
        self.replay_target_combo = QComboBox()
        for kind in (TransportKind.SERIAL, TransportKind.TCP_CLIENT, TransportKind.TCP_SERVER, TransportKind.UDP):
            self.replay_target_combo.addItem(kind.value, kind)

        self.scan_transport_combo = QComboBox()
        for kind in DeviceScanTransportKind:
            self.scan_transport_combo.addItem(kind.value, kind)
        self.scan_target_input = QLineEdit()
        self.scan_target_input.setPlaceholderText("Scan target")
        self.scan_unit_start = QSpinBox()
        self.scan_unit_start.setRange(0, 247)
        self.scan_unit_start.setValue(1)
        self.scan_unit_end = QSpinBox()
        self.scan_unit_end.setRange(0, 247)
        self.scan_unit_end.setValue(16)

        self.save_button = QPushButton("Save Rule")
        self.save_button.clicked.connect(self._on_save_rule)
        self.run_button = QPushButton("Run Rule")
        self.run_button.clicked.connect(self._on_run_rule)
        self.delete_button = QPushButton("Delete Rule")
        self.delete_button.clicked.connect(self._on_delete_rule)
        self.clear_jobs_button = QPushButton("Clear Scan Jobs")
        self.clear_jobs_button.clicked.connect(self.service.clear_prepared_device_scan_jobs)
        self.reload_button = QPushButton("Reload Saved Rules")
        self.reload_button.clicked.connect(self.service.reload_rules)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(QLabel("Rule"), 0, 0)
        grid.addWidget(self.rule_combo, 0, 1, 1, 2)
        grid.addWidget(self.delete_button, 0, 3)
        grid.addWidget(QLabel("Name"), 1, 0)
        grid.addWidget(self.name_input, 1, 1)
        grid.addWidget(QLabel("Action"), 1, 2)
        grid.addWidget(self.action_combo, 1, 3)
        grid.addWidget(QLabel("Replay Path"), 2, 0)
        grid.addWidget(self.replay_path_input, 2, 1, 1, 3)
        grid.addWidget(QLabel("Replay Target"), 3, 0)
        grid.addWidget(self.replay_target_combo, 3, 1)
        grid.addWidget(QLabel("Scan Transport"), 4, 0)
        grid.addWidget(self.scan_transport_combo, 4, 1)
        grid.addWidget(QLabel("Scan Target"), 4, 2)
        grid.addWidget(self.scan_target_input, 4, 3)
        grid.addWidget(QLabel("Unit Start"), 5, 0)
        grid.addWidget(self.scan_unit_start, 5, 1)
        grid.addWidget(QLabel("Unit End"), 5, 2)
        grid.addWidget(self.scan_unit_end, 5, 3)
        grid.addWidget(self.save_button, 6, 1)
        grid.addWidget(self.run_button, 6, 2)
        grid.addWidget(self.clear_jobs_button, 6, 3)
        grid.addWidget(self.reload_button, 7, 3)

        frame_layout.addLayout(header)
        frame_layout.addWidget(self.profile_path_label)
        frame_layout.addLayout(grid)
        frame_layout.addWidget(self.error_label)
        layout.addWidget(frame)
        self._refresh_action_specific_controls()

    def refresh(self, snapshot: RuleEngineSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._rebuild_rules(snapshot)
        finally:
            self._syncing_controls = False
        self.status_label.setText(
            f"Rules: {len(snapshot.rule_names)}    "
            f"Runs: {snapshot.execution_count}    "
            f"Scan Jobs: {snapshot.prepared_device_scan_job_count}"
        )
        profile_path = self.service.profile_path
        self.profile_path_label.setText(f"Profile: {profile_path}" if profile_path is not None else "Profile: in-memory only")
        self.error_label.setText(snapshot.last_error or "Ready.")
        self.delete_button.setEnabled(self.rule_combo.currentData() is not None)

    def _on_rule_selected(self) -> None:
        if self._syncing_controls:
            return
        name = self.rule_combo.currentData()
        rule = self.service.get_rule(name) if name else None
        if rule is None:
            return
        self.name_input.setText(rule.name)
        if not rule.actions:
            return
        action = rule.actions[0]
        self._set_combo_to_data(self.action_combo, action.kind)
        if action.kind == AutomationActionKind.RUN_REPLAY_PLAN:
            self.replay_path_input.setText(action.replay_plan_path or "")
            self._set_combo_to_data(self.replay_target_combo, action.replay_target_kind)
        elif action.kind == AutomationActionKind.PREPARE_DEVICE_SCAN and action.device_scan_config is not None:
            self._set_combo_to_data(self.scan_transport_combo, action.device_scan_config.transport_kind)
            self.scan_target_input.setText(action.device_scan_config.target)
            self.scan_unit_start.setValue(action.device_scan_config.unit_id_start)
            self.scan_unit_end.setValue(action.device_scan_config.unit_id_end)
        self._refresh_action_specific_controls()

    def _on_save_rule(self) -> None:
        name = " ".join(self.name_input.text().strip().split())
        if not name:
            self.error_label.setText("Rule name is required.")
            return
        action_kind = self.action_combo.currentData()
        if not isinstance(action_kind, AutomationActionKind):
            action_kind = AutomationActionKind(str(action_kind))

        if action_kind == AutomationActionKind.RUN_REPLAY_PLAN:
            replay_target = self.replay_target_combo.currentData()
            if not isinstance(replay_target, TransportKind):
                replay_target = TransportKind(str(replay_target))
            rule = AutomationRule(
                name=name,
                actions=(
                    AutomationAction(
                        kind=action_kind,
                        replay_plan_path=self.replay_path_input.text().strip(),
                        replay_target_kind=replay_target,
                    ),
                ),
            )
        elif action_kind == AutomationActionKind.PREPARE_DEVICE_SCAN:
            scan_transport = self.scan_transport_combo.currentData()
            if not isinstance(scan_transport, DeviceScanTransportKind):
                scan_transport = DeviceScanTransportKind(str(scan_transport))
            rule = AutomationRule(
                name=name,
                actions=(
                    AutomationAction(
                        kind=action_kind,
                        device_scan_config=DeviceScanConfig(
                            transport_kind=scan_transport,
                            target=self.scan_target_input.text().strip(),
                            unit_id_start=self.scan_unit_start.value(),
                            unit_id_end=self.scan_unit_end.value(),
                        ),
                    ),
                ),
            )
        else:
            enable = self.action_combo.currentText().startswith("Enable")
            rule = AutomationRule(
                name=name,
                actions=(AutomationAction(kind=action_kind, auto_response_enabled=enable),),
            )
        self.service.upsert_rule(rule)

    def _on_run_rule(self) -> None:
        name = self.rule_combo.currentData() or self.name_input.text().strip()
        if not name:
            self.error_label.setText("Select a rule before running.")
            return
        self.service.run_rule(str(name))

    def _on_delete_rule(self) -> None:
        self.service.remove_rule(self.rule_combo.currentData())

    def _rebuild_rules(self, snapshot: RuleEngineSnapshot) -> None:
        current_data = [self.rule_combo.itemData(index) for index in range(self.rule_combo.count())]
        desired_data = [None, *snapshot.rule_names]
        if current_data != desired_data:
            self.rule_combo.blockSignals(True)
            self.rule_combo.clear()
            self.rule_combo.addItem("Select Rule", None)
            for name in snapshot.rule_names:
                self.rule_combo.addItem(name, name)
            self.rule_combo.blockSignals(False)

    def _refresh_action_specific_controls(self) -> None:
        action_kind = self.action_combo.currentData()
        if not isinstance(action_kind, AutomationActionKind):
            action_kind = AutomationActionKind(str(action_kind))
        is_replay = action_kind == AutomationActionKind.RUN_REPLAY_PLAN
        is_scan = action_kind == AutomationActionKind.PREPARE_DEVICE_SCAN
        self.replay_path_input.setEnabled(is_replay)
        self.replay_target_combo.setEnabled(is_replay)
        self.scan_transport_combo.setEnabled(is_scan)
        self.scan_target_input.setEnabled(is_scan)
        self.scan_unit_start.setEnabled(is_scan)
        self.scan_unit_end.setEnabled(is_scan)

    def _set_combo_to_data(self, combo: QComboBox, value: object | None) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

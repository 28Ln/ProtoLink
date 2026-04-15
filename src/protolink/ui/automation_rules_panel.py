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

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService, AutoResponseRuntimeSnapshot
from protolink.application.channel_bridge_runtime_service import (
    ChannelBridgeRuntimeService,
    ChannelBridgeRuntimeSnapshot,
)
from protolink.application.rule_engine_service import RuleEngineService, RuleEngineSnapshot
from protolink.application.timed_task_service import TimedTaskService, TimedTaskSnapshot
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.rule_engine import AutomationAction, AutomationActionKind, AutomationRule
from protolink.core.transport import TransportKind


class AutomationRulesPanel(QWidget):
    _LABEL_COLUMN_MIN_WIDTH = 88

    def __init__(
        self,
        service: RuleEngineService,
        auto_response_service: AutoResponseRuntimeService | None = None,
        timed_task_service: TimedTaskService | None = None,
        channel_bridge_service: ChannelBridgeRuntimeService | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.auto_response_service = auto_response_service
        self.timed_task_service = timed_task_service
        self.channel_bridge_service = channel_bridge_service
        self._syncing_controls = False
        self._build_ui()
        self.service.subscribe(self.refresh)
        if self.auto_response_service is not None:
            self.auto_response_service.subscribe(self._refresh_auto_response_status)
            self._refresh_auto_response_status(self.auto_response_service.snapshot)
        if self.timed_task_service is not None:
            self.timed_task_service.subscribe(self._refresh_timed_task_status)
            self._refresh_timed_task_status(self.timed_task_service.snapshot)
        if self.channel_bridge_service is not None:
            self.channel_bridge_service.subscribe(self._refresh_channel_bridge_status)
            self._refresh_channel_bridge_status(self.channel_bridge_service.snapshot)
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
        title = QLabel("自动化规则")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.status_label.setWordWrap(True)
        self.profile_path_label = QLabel()
        self.profile_path_label.setObjectName("MetaLabel")
        self.profile_path_label.setWordWrap(True)
        header.addWidget(title)
        header.addStretch(1)
        self.notice_label = QLabel(
            "受控自动化，仅在明确的停止/禁用边界内开放，避免未授权扩展。"
        )
        self.notice_label.setObjectName("MetaLabel")
        self.notice_label.setWordWrap(True)

        self.rule_combo = QComboBox()
        self.rule_combo.addItem("选择规则", None)
        self.rule_combo.currentIndexChanged.connect(self._on_rule_selected)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("规则名称")

        self.action_combo = QComboBox()
        self.action_combo.addItem("执行回放计划", AutomationActionKind.RUN_REPLAY_PLAN)
        self.action_combo.addItem("启用自动响应", AutomationActionKind.SET_AUTO_RESPONSE_ENABLED)
        self.action_combo.addItem("禁用自动响应", AutomationActionKind.SET_AUTO_RESPONSE_ENABLED)
        self.action_combo.addItem("准备设备扫描", AutomationActionKind.PREPARE_DEVICE_SCAN)
        self.action_combo.currentIndexChanged.connect(self._refresh_action_specific_controls)

        self.replay_path_input = QLineEdit()
        self.replay_path_input.setPlaceholderText("回放计划路径")
        self.replay_target_combo = QComboBox()
        for kind in (TransportKind.SERIAL, TransportKind.TCP_CLIENT, TransportKind.TCP_SERVER, TransportKind.UDP):
            self.replay_target_combo.addItem(kind.value, kind)

        self.scan_transport_combo = QComboBox()
        for kind in DeviceScanTransportKind:
            self.scan_transport_combo.addItem(kind.value, kind)
        self.scan_target_input = QLineEdit()
        self.scan_target_input.setPlaceholderText("扫描目标")
        self.scan_unit_start = QSpinBox()
        self.scan_unit_start.setRange(0, 247)
        self.scan_unit_start.setValue(1)
        self.scan_unit_end = QSpinBox()
        self.scan_unit_end.setRange(0, 247)
        self.scan_unit_end.setValue(16)

        self.save_button = QPushButton("保存规则")
        self.save_button.clicked.connect(self._on_save_rule)
        self.run_button = QPushButton("运行规则")
        self.run_button.clicked.connect(self._on_run_rule)
        self.delete_button = QPushButton("删除规则")
        self.delete_button.clicked.connect(self._on_delete_rule)
        self.clear_jobs_button = QPushButton("清除扫描任务")
        self.clear_jobs_button.clicked.connect(self.service.clear_prepared_device_scan_jobs)
        self.reload_button = QPushButton("重新加载规则")
        self.reload_button.clicked.connect(self.service.reload_rules)

        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        frame_layout.addLayout(header)
        frame_layout.addWidget(self.status_label)
        frame_layout.addWidget(self.profile_path_label)
        frame_layout.addWidget(self.notice_label)
        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("AutomationRulesTabs")
        self.content_tabs.addTab(self._build_rule_editor_tab(), "规则编辑")
        if any(
            service is not None
            for service in (
                self.auto_response_service,
                self.timed_task_service,
                self.channel_bridge_service,
            )
        ):
            self.content_tabs.addTab(self._build_runtime_safety_frame(), "运行安全")
        frame_layout.addWidget(self.content_tabs)
        layout.addWidget(frame)
        self._refresh_action_specific_controls()

    def _build_rule_editor_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(12)

        tab_layout.addWidget(self._build_rule_identity_section())
        tab_layout.addWidget(self._build_action_configuration_section())
        tab_layout.addWidget(self._build_execution_section())
        tab_layout.addStretch(1)
        return tab

    def _build_rule_identity_section(self) -> QFrame:
        frame, layout = self._create_section(
            "规则入口",
            "先选规则，再编辑名称和动作类型，避免所有字段同时堆在一张长表单里。",
        )
        grid = self._create_form_grid()
        grid.addWidget(QLabel("规则"), 0, 0)
        grid.addWidget(self.rule_combo, 0, 1, 1, 2)
        grid.addWidget(self.delete_button, 0, 3)
        grid.addWidget(QLabel("名称"), 1, 0)
        grid.addWidget(self.name_input, 1, 1)
        grid.addWidget(QLabel("操作"), 1, 2)
        grid.addWidget(self.action_combo, 1, 3)
        layout.addLayout(grid)
        return frame

    def _build_action_configuration_section(self) -> QFrame:
        frame, layout = self._create_section(
            "动作配置",
            "将回放、扫描和自动响应拆成独立页签，降低中文标签挤压与纵向堆叠。",
        )
        self.action_tabs = QTabWidget()
        self.action_tabs.setObjectName("AutomationActionTabs")
        self.replay_action_tab = self._build_replay_action_tab()
        self.scan_action_tab = self._build_scan_action_tab()
        self.auto_response_action_tab = self._build_auto_response_action_tab()
        self.action_tabs.addTab(self.replay_action_tab, "回放计划")
        self.action_tabs.addTab(self.scan_action_tab, "设备扫描")
        self.action_tabs.addTab(self.auto_response_action_tab, "自动响应")
        layout.addWidget(self.action_tabs)
        return frame

    def _build_replay_action_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        grid = self._create_form_grid()
        grid.addWidget(QLabel("回放计划"), 0, 0)
        grid.addWidget(self.replay_path_input, 0, 1, 1, 3)
        grid.addWidget(QLabel("回放目标"), 1, 0)
        grid.addWidget(self.replay_target_combo, 1, 1, 1, 3)
        layout.addLayout(grid)
        layout.addStretch(1)
        return tab

    def _build_scan_action_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        grid = self._create_form_grid()
        grid.addWidget(QLabel("扫描通道"), 0, 0)
        grid.addWidget(self.scan_transport_combo, 0, 1)
        grid.addWidget(QLabel("扫描目标"), 0, 2)
        grid.addWidget(self.scan_target_input, 0, 3)
        grid.addWidget(QLabel("起始寄存器"), 1, 0)
        grid.addWidget(self.scan_unit_start, 1, 1)
        grid.addWidget(QLabel("结束寄存器"), 1, 2)
        grid.addWidget(self.scan_unit_end, 1, 3)
        layout.addLayout(grid)
        layout.addStretch(1)
        return tab

    def _build_auto_response_action_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.auto_response_action_label = QLabel()
        self.auto_response_action_label.setObjectName("MetaLabel")
        self.auto_response_action_label.setWordWrap(True)
        layout.addWidget(self.auto_response_action_label)
        layout.addStretch(1)
        return tab

    def _build_execution_section(self) -> QFrame:
        frame, layout = self._create_section("执行控制")
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.save_button)
        controls.addWidget(self.run_button)
        controls.addWidget(self.clear_jobs_button)
        controls.addStretch(1)
        controls.addWidget(self.reload_button)
        layout.addLayout(controls)
        layout.addWidget(self.error_label)
        return frame

    def _build_runtime_safety_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QGridLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        row = 0
        title = QLabel("自动化运行安全")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, row, 0, 1, 4)
        row += 1

        self.auto_response_status_label = QLabel("自动响应：不可用")
        self.auto_response_status_label.setWordWrap(True)
        self.enable_auto_response_button = QPushButton("启用自动响应")
        self.disable_auto_response_button = QPushButton("禁用自动响应")
        if self.auto_response_service is not None:
            self.enable_auto_response_button.clicked.connect(lambda: self.auto_response_service.set_enabled(True))
            self.disable_auto_response_button.clicked.connect(lambda: self.auto_response_service.set_enabled(False))
        else:
            self.enable_auto_response_button.setEnabled(False)
            self.disable_auto_response_button.setEnabled(False)
        layout.addWidget(self.auto_response_status_label, row, 0, 1, 2)
        layout.addWidget(self.enable_auto_response_button, row, 2)
        layout.addWidget(self.disable_auto_response_button, row, 3)
        row += 1

        self.timed_task_status_label = QLabel("定时任务：不可用")
        self.timed_task_status_label.setWordWrap(True)
        self.start_timed_tasks_button = QPushButton("启动定时任务")
        self.stop_timed_tasks_button = QPushButton("停止定时任务")
        if self.timed_task_service is not None:
            self.start_timed_tasks_button.clicked.connect(self.timed_task_service.start)
            self.stop_timed_tasks_button.clicked.connect(self.timed_task_service.stop)
        else:
            self.start_timed_tasks_button.setEnabled(False)
            self.stop_timed_tasks_button.setEnabled(False)
        layout.addWidget(self.timed_task_status_label, row, 0, 1, 2)
        layout.addWidget(self.start_timed_tasks_button, row, 2)
        layout.addWidget(self.stop_timed_tasks_button, row, 3)
        row += 1

        self.channel_bridge_status_label = QLabel("通道桥：不可用")
        self.channel_bridge_status_label.setWordWrap(True)
        self.clear_bridges_button = QPushButton("清除桥接")
        if self.channel_bridge_service is not None:
            self.clear_bridges_button.clicked.connect(self.channel_bridge_service.clear_bridges)
        else:
            self.clear_bridges_button.setEnabled(False)
        layout.addWidget(self.channel_bridge_status_label, row, 0, 1, 3)
        layout.addWidget(self.clear_bridges_button, row, 3)
        return frame

    def refresh(self, snapshot: RuleEngineSnapshot) -> None:
        self._syncing_controls = True
        try:
            self._rebuild_rules(snapshot)
        finally:
            self._syncing_controls = False
        self.status_label.setText(
            f"规则数: {len(snapshot.rule_names)}    "
            f"运行次数: {snapshot.execution_count}    "
            f"扫描任务: {snapshot.prepared_device_scan_job_count}"
        )
        profile_path = self.service.profile_path
        self.profile_path_label.setText(f"配置文件: {profile_path}" if profile_path is not None else "配置文件: 内存中")
        self.error_label.setText(snapshot.last_error or "准备就绪")
        self._refresh_primary_actions(snapshot)

    def _refresh_auto_response_status(self, snapshot: AutoResponseRuntimeSnapshot) -> None:
        self.auto_response_status_label.setText(
            f"自动响应：启用={snapshot.enabled} 规则={snapshot.rule_count} 匹配={snapshot.matched_count}"
        )
        self.enable_auto_response_button.setEnabled(self.auto_response_service is not None and not snapshot.enabled)
        self.disable_auto_response_button.setEnabled(self.auto_response_service is not None and snapshot.enabled)

    def _refresh_timed_task_status(self, snapshot: TimedTaskSnapshot) -> None:
        self.timed_task_status_label.setText(
            f"定时任务：运行={snapshot.running} 任务={len(snapshot.task_names)} 次数={snapshot.execution_count}"
        )
        self.start_timed_tasks_button.setEnabled(self.timed_task_service is not None and not snapshot.running)
        self.stop_timed_tasks_button.setEnabled(self.timed_task_service is not None and snapshot.running)

    def _refresh_channel_bridge_status(self, snapshot: ChannelBridgeRuntimeSnapshot) -> None:
        self.channel_bridge_status_label.setText(
            f"通道桥：总数={len(snapshot.bridge_names)} 已启用={len(snapshot.enabled_bridge_names)} 桥接={snapshot.bridged_count}"
        )
        self.clear_bridges_button.setEnabled(self.channel_bridge_service is not None and bool(snapshot.bridge_names))

    def _on_rule_selected(self) -> None:
        if self._syncing_controls:
            return
        name = self.rule_combo.currentData()
        self._refresh_primary_actions()
        rule = self.service.get_rule(name) if name else None
        if rule is None:
            return
        self.name_input.setText(rule.name)
        if not rule.actions:
            return
        action = rule.actions[0]
        if action.kind == AutomationActionKind.SET_AUTO_RESPONSE_ENABLED:
            self._set_auto_response_action(action.auto_response_enabled is not False)
        else:
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
        self._refresh_primary_actions()

    def _on_save_rule(self) -> None:
        name = " ".join(self.name_input.text().strip().split())
        if not name:
            self.error_label.setText("请输入规则名称。")
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
            enable = self._current_auto_response_enabled()
            rule = AutomationRule(
                name=name,
                actions=(AutomationAction(kind=action_kind, auto_response_enabled=enable),),
            )
        self.service.upsert_rule(rule)

    def _on_run_rule(self) -> None:
        name = self.rule_combo.currentData() or self.name_input.text().strip()
        if not name:
            self.error_label.setText("请先选择规则。")
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
            self.rule_combo.addItem("选择规则", None)
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
        if action_kind == AutomationActionKind.RUN_REPLAY_PLAN:
            self.action_tabs.setCurrentWidget(self.replay_action_tab)
        elif action_kind == AutomationActionKind.PREPARE_DEVICE_SCAN:
            self.action_tabs.setCurrentWidget(self.scan_action_tab)
        else:
            self.action_tabs.setCurrentWidget(self.auto_response_action_tab)
        self.auto_response_action_label.setText(
            f"当前操作：{'启用' if self._current_auto_response_enabled() else '禁用'}自动响应。"
        )

    def _refresh_primary_actions(self, snapshot: RuleEngineSnapshot | None = None) -> None:
        snapshot = snapshot or self.service.snapshot
        has_selected_rule = self.rule_combo.currentData() is not None
        self.delete_button.setEnabled(has_selected_rule)
        self.run_button.setEnabled(has_selected_rule)
        self.clear_jobs_button.setEnabled(snapshot.prepared_device_scan_job_count > 0)

    def _set_combo_to_data(self, combo: QComboBox, value: object | None) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_auto_response_action(self, enabled: bool) -> None:
        target_text = "启用自动响应" if enabled else "禁用自动响应"
        for index in range(self.action_combo.count()):
            if self.action_combo.itemText(index) == target_text:
                self.action_combo.setCurrentIndex(index)
                return

    def _current_auto_response_enabled(self) -> bool:
        return self.action_combo.currentText().startswith("启用")

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

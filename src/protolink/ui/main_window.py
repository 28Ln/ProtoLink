from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.packet_replay_service import PacketReplayExecutionService
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.application.rule_engine_service import RuleEngineService
from protolink.application.serial_service import SerialSessionService
from protolink.application.mqtt_client_service import MqttClientSessionService
from protolink.application.mqtt_server_service import MqttServerSessionService
from protolink.application.tcp_client_service import TcpClientSessionService
from protolink.application.tcp_server_service import TcpServerSessionService
from protolink.application.udp_service import UdpSessionService
from protolink.catalog import build_module_catalog
from protolink.core.models import FeatureModule
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.workspace import WorkspaceLayout
from protolink.ui.packet_console import PacketConsoleWidget
from protolink.ui.automation_rules_panel import AutomationRulesPanel
from protolink.ui.modbus_tcp_panel import ModbusTcpLabPanel
from protolink.ui.modbus_rtu_panel import ModbusRtuLabPanel
from protolink.ui.register_monitor_panel import RegisterMonitorPanel
from protolink.ui.serial_panel import SerialStudioPanel
from protolink.ui.mqtt_client_panel import MqttClientPanel
from protolink.ui.mqtt_server_panel import MqttServerPanel
from protolink.ui.tcp_client_panel import TcpClientPanel
from protolink.ui.tcp_server_panel import TcpServerPanel
from protolink.ui.udp_panel import UdpPanel


class ProtoLinkMainWindow(QMainWindow):
    def __init__(
        self,
        workspace: WorkspaceLayout,
        inspector: PacketInspectorState,
        serial_service: SerialSessionService,
        mqtt_client_service: MqttClientSessionService,
        mqtt_server_service: MqttServerSessionService,
        tcp_client_service: TcpClientSessionService,
        tcp_server_service: TcpServerSessionService,
        udp_service: UdpSessionService,
        packet_replay_service: PacketReplayExecutionService,
        register_monitor_service: RegisterMonitorService,
        rule_engine_service: RuleEngineService,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.inspector = inspector
        self.serial_service = serial_service
        self.mqtt_client_service = mqtt_client_service
        self.mqtt_server_service = mqtt_server_service
        self.tcp_client_service = tcp_client_service
        self.tcp_server_service = tcp_server_service
        self.udp_service = udp_service
        self.packet_replay_service = packet_replay_service
        self.register_monitor_service = register_monitor_service
        self.rule_engine_service = rule_engine_service
        self.modules = build_module_catalog()
        self._setup_window()
        self._build_ui()
        self._populate_modules()
        self.module_list.setCurrentRow(0)

    def _setup_window(self) -> None:
        self.setWindowTitle("ProtoLink")
        self.resize(1360, 860)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(10)

        sidebar_title = QLabel("ProtoLink")
        sidebar_title.setObjectName("HeroTitle")
        sidebar_subtitle = QLabel("Industrial communication workbench")
        sidebar_subtitle.setObjectName("MetaLabel")

        self.module_list = QListWidget()
        self.module_list.currentRowChanged.connect(self._on_module_changed)

        sidebar_layout.addWidget(sidebar_title)
        sidebar_layout.addWidget(sidebar_subtitle)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(self.module_list, 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("Hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)

        hero_title = QLabel("Windows-first protocol and transport platform")
        hero_title.setObjectName("HeroTitle")
        hero_subtitle = QLabel(
            "Directly rebuilding the product as a maintainable platform, not as a patchwork of the reference codebases."
        )
        hero_subtitle.setWordWrap(True)

        stats = self._build_stats_row()

        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)
        hero_layout.addLayout(stats)

        details = QFrame()
        details.setObjectName("Panel")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(10)

        section_title = QLabel("Module Focus")
        section_title.setObjectName("SectionTitle")

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.meta_label = QLabel()
        self.meta_label.setObjectName("MetaLabel")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.acceptance_text = QTextEdit()
        self.acceptance_text.setReadOnly(True)

        details_layout.addWidget(section_title)
        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.meta_label)
        details_layout.addWidget(QLabel("Summary"))
        details_layout.addWidget(self.summary_text, 1)
        details_layout.addWidget(QLabel("Acceptance"))
        details_layout.addWidget(self.acceptance_text, 1)

        content_layout.addWidget(hero)
        content_layout.addWidget(details, 1)
        self.serial_panel = SerialStudioPanel(self.serial_service)
        self.serial_panel.setVisible(False)
        content_layout.addWidget(self.serial_panel)
        self.mqtt_client_panel = MqttClientPanel(self.mqtt_client_service)
        self.mqtt_client_panel.setVisible(False)
        content_layout.addWidget(self.mqtt_client_panel)
        self.mqtt_server_panel = MqttServerPanel(self.mqtt_server_service)
        self.mqtt_server_panel.setVisible(False)
        content_layout.addWidget(self.mqtt_server_panel)
        self.tcp_client_panel = TcpClientPanel(self.tcp_client_service)
        self.tcp_client_panel.setVisible(False)
        content_layout.addWidget(self.tcp_client_panel)
        self.tcp_server_panel = TcpServerPanel(self.tcp_server_service)
        self.tcp_server_panel.setVisible(False)
        content_layout.addWidget(self.tcp_server_panel)
        self.udp_panel = UdpPanel(self.udp_service)
        self.udp_panel.setVisible(False)
        content_layout.addWidget(self.udp_panel)
        self.register_monitor_panel = RegisterMonitorPanel(self.register_monitor_service)
        self.register_monitor_panel.setVisible(False)
        content_layout.addWidget(self.register_monitor_panel)
        self.modbus_rtu_panel = ModbusRtuLabPanel(
            self.serial_service,
            self.register_monitor_service,
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self.modbus_rtu_panel.setVisible(False)
        content_layout.addWidget(self.modbus_rtu_panel)
        self.modbus_tcp_panel = ModbusTcpLabPanel(
            self.tcp_client_service,
            self.register_monitor_service,
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self.modbus_tcp_panel.setVisible(False)
        content_layout.addWidget(self.modbus_tcp_panel)
        self.automation_rules_panel = AutomationRulesPanel(self.rule_engine_service)
        self.automation_rules_panel.setVisible(False)
        content_layout.addWidget(self.automation_rules_panel)

        layout.addWidget(sidebar, 0)
        layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self._build_packet_console_dock()

    def _build_stats_row(self) -> QHBoxLayout:
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)

        counts = Counter(module.status.value for module in self.modules)
        badges = [
            f"Workspace: {self.workspace.root}",
            f"Bootstrapped: {counts.get('Bootstrapped', 0)}",
            f"Next: {counts.get('Next', 0)}",
            f"Planned: {counts.get('Planned', 0)}",
            "Canonical mainline: docs/MAINLINE_STATUS.md",
        ]

        for text in badges:
            badge = QLabel(text)
            badge.setObjectName("Badge")
            badge.setTextInteractionFlags(Qt.TextSelectableByMouse)
            stats_layout.addWidget(badge)

        stats_layout.addStretch(1)
        return stats_layout

    def _populate_modules(self) -> None:
        for module in self.modules:
            item = QListWidgetItem(module.name)
            self.module_list.addItem(item)

    def _on_module_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.modules):
            return

        module = self.modules[index]
        self._render_module(module)

    def _render_module(self, module: FeatureModule) -> None:
        self.name_label.setText(module.name)
        self.meta_label.setText(
            f"Area: {module.area}    Status: {module.status.value}    Milestone: {module.milestone}"
        )
        self.summary_text.setPlainText(module.summary)
        self.acceptance_text.setPlainText("\n".join(f"- {item}" for item in module.acceptance))
        self.serial_panel.setVisible(module.name == "Serial Studio")
        self.mqtt_client_panel.setVisible(module.name == "MQTT Client")
        self.mqtt_server_panel.setVisible(module.name == "MQTT Server")
        self.tcp_client_panel.setVisible(module.name == "TCP Client")
        self.tcp_server_panel.setVisible(module.name == "TCP Server")
        self.udp_panel.setVisible(module.name == "UDP Lab")
        self.modbus_rtu_panel.setVisible(module.name == "Modbus RTU Lab")
        self.modbus_tcp_panel.setVisible(module.name == "Modbus TCP Lab")
        self.register_monitor_panel.setVisible(module.name == "Register Monitor")
        self.automation_rules_panel.setVisible(module.name == "Automation Rules")

    def _build_packet_console_dock(self) -> None:
        self.packet_console = PacketConsoleWidget(
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self.packet_console_dock = QDockWidget("Packet Inspector", self)
        self.packet_console_dock.setObjectName("PacketInspectorDock")
        self.packet_console_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.packet_console_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.packet_console_dock.setWidget(self.packet_console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.packet_console_dock)

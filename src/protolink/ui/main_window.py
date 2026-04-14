from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.application.channel_bridge_runtime_service import ChannelBridgeRuntimeService
from protolink.application.data_tools_service import DataToolsService
from protolink.application.network_tools_service import NetworkToolsService
from protolink.application.mqtt_client_service import MqttClientSessionService
from protolink.application.mqtt_server_service import MqttServerSessionService
from protolink.application.packet_replay_service import PacketReplayExecutionService
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.application.rule_engine_service import RuleEngineService
from protolink.application.script_console_service import ScriptConsoleService
from protolink.application.serial_service import SerialSessionService
from protolink.application.tcp_client_service import TcpClientSessionService
from protolink.application.tcp_server_service import TcpServerSessionService
from protolink.application.timed_task_service import TimedTaskService
from protolink.application.udp_service import UdpSessionService
from protolink.catalog import build_module_catalog
from protolink.core.models import FeatureModule, ModuleStatus
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import (
    APPLICATION_SUBTITLE,
    APPLICATION_TITLE,
    display_module_area,
    display_module_status,
)
from protolink.ui.automation_rules_panel import AutomationRulesPanel
from protolink.ui.data_tools_panel import DataToolsPanel
from protolink.ui.modbus_rtu_panel import ModbusRtuLabPanel
from protolink.ui.modbus_tcp_panel import ModbusTcpLabPanel
from protolink.ui.mqtt_client_panel import MqttClientPanel
from protolink.ui.mqtt_server_panel import MqttServerPanel
from protolink.ui.network_tools_panel import NetworkToolsPanel
from protolink.ui.packet_console import PacketConsoleWidget
from protolink.ui.register_monitor_panel import RegisterMonitorPanel
from protolink.ui.script_console_panel import ScriptConsolePanel
from protolink.ui.serial_panel import SerialStudioPanel
from protolink.ui.tcp_client_panel import TcpClientPanel
from protolink.ui.tcp_server_panel import TcpServerPanel
from protolink.ui.udp_panel import UdpPanel


WINDOW_EDGE_MARGIN = 6


class WindowTitleBar(QFrame):
    def __init__(self, window: "ProtoLinkMainWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 14, 14)
        layout.setSpacing(12)

        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(2)

        self.title_label = QLabel("ProtoLink")
        self.title_label.setObjectName("TitleBarTitle")
        self.subtitle_label = QLabel(APPLICATION_SUBTITLE)
        self.subtitle_label.setObjectName("TitleBarSubtitle")
        self.context_label = QLabel("稳定交付模式")
        self.context_label.setObjectName("TitleBarContext")

        brand_layout.addWidget(self.title_label)
        brand_layout.addWidget(self.subtitle_label)

        layout.addLayout(brand_layout, 1)
        layout.addWidget(self.context_label)

        self.minimize_button = self._build_button("-", "最小化窗口", self._window.showMinimized)
        self.maximize_button = self._build_button("□", "最大化窗口", self._window.toggle_maximized)
        self.close_button = self._build_button("×", "关闭窗口", self._window.close, close_button=True)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def _build_button(
        self,
        text: str,
        tooltip: str,
        callback,
        *,
        close_button: bool = False,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setObjectName("WindowCloseButton" if close_button else "WindowButton")
        button.setFixedSize(38, 30)
        button.clicked.connect(callback)
        return button

    def set_context_text(self, text: str) -> None:
        self.context_label.setText(text)

    def sync_window_state(self, maximized: bool) -> None:
        self.maximize_button.setText("❐" if maximized else "□")
        self.maximize_button.setToolTip("还原窗口" if maximized else "最大化窗口")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and not self._window.isMaximized():
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)


class ProtoLinkMainWindow(QMainWindow):
    def __init__(
        self,
        workspace: WorkspaceLayout,
        inspector: PacketInspectorState,
        data_tools_service: DataToolsService,
        network_tools_service: NetworkToolsService,
        serial_service: SerialSessionService,
        mqtt_client_service: MqttClientSessionService,
        mqtt_server_service: MqttServerSessionService,
        tcp_client_service: TcpClientSessionService,
        tcp_server_service: TcpServerSessionService,
        udp_service: UdpSessionService,
        packet_replay_service: PacketReplayExecutionService,
        register_monitor_service: RegisterMonitorService,
        rule_engine_service: RuleEngineService,
        auto_response_runtime_service: AutoResponseRuntimeService | None = None,
        script_console_service: ScriptConsoleService | None = None,
        timed_task_service: TimedTaskService | None = None,
        channel_bridge_runtime_service: ChannelBridgeRuntimeService | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.inspector = inspector
        self.data_tools_service = data_tools_service
        self.network_tools_service = network_tools_service
        self.serial_service = serial_service
        self.mqtt_client_service = mqtt_client_service
        self.mqtt_server_service = mqtt_server_service
        self.tcp_client_service = tcp_client_service
        self.tcp_server_service = tcp_server_service
        self.udp_service = udp_service
        self.packet_replay_service = packet_replay_service
        self.register_monitor_service = register_monitor_service
        self.rule_engine_service = rule_engine_service
        self.auto_response_runtime_service = auto_response_runtime_service
        self.script_console_service = script_console_service
        self.timed_task_service = timed_task_service
        self.channel_bridge_runtime_service = channel_bridge_runtime_service
        self.modules = build_module_catalog()
        self._panel_pages: dict[str, QWidget] = {}
        self._setup_window()
        self._build_ui()
        self._populate_modules()
        self.module_list.setCurrentRow(0)

    def _setup_window(self) -> None:
        self.setWindowTitle(APPLICATION_TITLE)
        self.resize(1480, 920)
        self.setMinimumSize(1180, 760)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self.setMouseTracking(True)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(WINDOW_EDGE_MARGIN, WINDOW_EDGE_MARGIN, WINDOW_EDGE_MARGIN, WINDOW_EDGE_MARGIN)
        root_layout.setSpacing(0)

        surface = QFrame()
        surface.setObjectName("WindowSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self.title_bar = WindowTitleBar(self)
        surface_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(16)

        sidebar = self._build_sidebar()
        content = self._build_content_area()

        body_layout.addWidget(sidebar)
        body_layout.addWidget(content, 1)

        surface_layout.addWidget(body, 1)
        root_layout.addWidget(surface, 1)

        self.setCentralWidget(root)
        self._build_packet_console_dock()
        self.title_bar.sync_window_state(self.isMaximized())

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(290)
        sidebar.setMaximumWidth(340)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        title = QLabel("模块导航")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("默认全中文工作台，所有模块统一从这里进入。")
        subtitle.setObjectName("MetaLabel")
        subtitle.setWordWrap(True)

        workspace_title = QLabel("当前工作区")
        workspace_title.setObjectName("SectionTitle")
        self.workspace_label = QLabel(str(self.workspace.root))
        self.workspace_label.setObjectName("PathLabel")
        self.workspace_label.setWordWrap(True)
        self.workspace_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.workspace_meta_label = QLabel(
            f"日志目录：{self.workspace.logs}\n导出目录：{self.workspace.exports}"
        )
        self.workspace_meta_label.setObjectName("MetaLabel")
        self.workspace_meta_label.setWordWrap(True)
        self.workspace_meta_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.module_list = QListWidget()
        self.module_list.setObjectName("ModuleList")
        self.module_list.currentRowChanged.connect(self._on_module_changed)

        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(4)
        sidebar_layout.addWidget(workspace_title)
        sidebar_layout.addWidget(self.workspace_label)
        sidebar_layout.addWidget(self.workspace_meta_label)
        sidebar_layout.addWidget(self.module_list, 1)
        return sidebar

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("Hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)

        hero_title = QLabel(APPLICATION_TITLE)
        hero_title.setObjectName("HeroTitle")
        hero_subtitle = QLabel("围绕留痕、主链路、自动化和交付验证构建，不以临时演示或 MVP 为目标。")
        hero_subtitle.setObjectName("HeroSubtitle")
        hero_subtitle.setWordWrap(True)

        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)
        hero_layout.addLayout(self._build_stats_row())

        details = QFrame()
        details.setObjectName("Panel")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(10)

        section_title = QLabel("当前模块")
        section_title.setObjectName("SectionTitle")
        self.name_label = QLabel()
        self.name_label.setObjectName("ModuleTitle")
        self.meta_label = QLabel()
        self.meta_label.setObjectName("MetaLabel")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.acceptance_text = QTextEdit()
        self.acceptance_text.setReadOnly(True)

        details_layout.addWidget(section_title)
        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.meta_label)
        details_layout.addWidget(QLabel("能力说明"))
        details_layout.addWidget(self.summary_text, 1)
        details_layout.addWidget(QLabel("验收标准"))
        details_layout.addWidget(self.acceptance_text, 1)

        panel_surface = QFrame()
        panel_surface.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel_surface)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)

        panel_title = QLabel("功能工作面")
        panel_title.setObjectName("SectionTitle")
        panel_hint = QLabel("这里展示当前模块的专属操作面板，保留工作流上下文，不再依赖系统原生窗口标题栏。")
        panel_hint.setObjectName("MetaLabel")
        panel_hint.setWordWrap(True)

        self.panel_stack = QStackedWidget()
        self.panel_stack.setObjectName("PanelStack")

        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(panel_hint)
        panel_layout.addWidget(self.panel_stack, 1)

        content_layout.addWidget(hero)
        content_layout.addWidget(details, 1)
        content_layout.addWidget(panel_surface, 2)

        self._build_module_panels()
        return content

    def _build_dashboard_panel(self) -> QWidget:
        dashboard = QFrame()
        dashboard.setObjectName("Panel")
        layout = QVBoxLayout(dashboard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("工作台总览")
        title.setObjectName("SectionTitle")

        overview = QLabel(
            "ProtoLink 当前按稳定工具标准组织：左侧统一导航，右侧保持模块上下文，底部停靠报文分析台。"
        )
        overview.setObjectName("MetaLabel")
        overview.setWordWrap(True)

        directories = QLabel(
            "\n".join(
                (
                    f"工作区根目录：{self.workspace.root}",
                    f"日志证据目录：{self.workspace.logs}",
                    f"抓包目录：{self.workspace.captures}",
                    f"导出目录：{self.workspace.exports}",
                )
            )
        )
        directories.setObjectName("PathLabel")
        directories.setWordWrap(True)
        directories.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        checklist = QTextEdit()
        checklist.setReadOnly(True)
        checklist.setPlainText(
            "\n".join(
                (
                    "1. 先在左侧选择目标模块，保持链路上下文清晰。",
                    "2. 底部报文分析台统一承接原始负载、过滤和回放计划。",
                    "3. 所有专业模块默认使用中文说明和边界提示。",
                    "4. 打包、预检和交付验证链路保持独立，不与日常调试入口混杂。",
                )
            )
        )

        layout.addWidget(title)
        layout.addWidget(overview)
        layout.addWidget(directories)
        layout.addWidget(checklist, 1)
        return dashboard

    def _build_module_panels(self) -> None:
        self.dashboard_panel = self._build_dashboard_panel()
        self._register_panel_page("dashboard", self.dashboard_panel)

        self.serial_panel = SerialStudioPanel(self.serial_service)
        self._register_panel_page("serial_studio", self._wrap_panel(self.serial_panel))

        self.mqtt_client_panel = MqttClientPanel(self.mqtt_client_service)
        self._register_panel_page("mqtt_client", self._wrap_panel(self.mqtt_client_panel))

        self.mqtt_server_panel = MqttServerPanel(self.mqtt_server_service)
        self._register_panel_page("mqtt_server", self._wrap_panel(self.mqtt_server_panel))

        self.tcp_client_panel = TcpClientPanel(self.tcp_client_service)
        self._register_panel_page("tcp_client", self._wrap_panel(self.tcp_client_panel))

        self.tcp_server_panel = TcpServerPanel(self.tcp_server_service)
        self._register_panel_page("tcp_server", self._wrap_panel(self.tcp_server_panel))

        self.udp_panel = UdpPanel(self.udp_service)
        self._register_panel_page("udp_lab", self._wrap_panel(self.udp_panel))

        self.register_monitor_panel = RegisterMonitorPanel(self.register_monitor_service)
        self._register_panel_page("register_monitor", self._wrap_panel(self.register_monitor_panel))

        self.modbus_rtu_panel = ModbusRtuLabPanel(
            self.serial_service,
            self.register_monitor_service,
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self._register_panel_page("modbus_rtu_lab", self._wrap_panel(self.modbus_rtu_panel))

        self.modbus_tcp_panel = ModbusTcpLabPanel(
            self.tcp_client_service,
            self.register_monitor_service,
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self._register_panel_page("modbus_tcp_lab", self._wrap_panel(self.modbus_tcp_panel))

        self.automation_rules_panel = AutomationRulesPanel(
            self.rule_engine_service,
            auto_response_service=self.auto_response_runtime_service,
            timed_task_service=self.timed_task_service,
            channel_bridge_service=self.channel_bridge_runtime_service,
        )
        self._register_panel_page("automation_rules", self._wrap_panel(self.automation_rules_panel))

        self.data_tools_panel = DataToolsPanel(self.data_tools_service)
        self._register_panel_page("data_tools", self._wrap_panel(self.data_tools_panel))

        self.network_tools_panel = NetworkToolsPanel(self.network_tools_service)
        self._register_panel_page("network_tools", self._wrap_panel(self.network_tools_panel))

        self.script_console_panel = ScriptConsolePanel(self.script_console_service) if self.script_console_service else None
        if self.script_console_panel is not None:
            self._register_panel_page("script_console", self._wrap_panel(self.script_console_panel))

    def _register_panel_page(self, module_name: str, widget: QWidget) -> None:
        self.panel_stack.addWidget(widget)
        self._panel_pages[module_name] = widget

    def _wrap_panel(self, panel: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("PanelScrollArea")
        scroll.setWidget(panel)
        return scroll

    def _build_stats_row(self) -> QHBoxLayout:
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)

        counts = Counter(module.status for module in self.modules)
        badges = [
            f"模块总数：{len(self.modules)}",
            f"已落地：{counts.get(ModuleStatus.BOOTSTRAPPED, 0)}",
            f"下一阶段：{counts.get(ModuleStatus.NEXT, 0)}",
            f"规划中：{counts.get(ModuleStatus.PLANNED, 0)}",
            f"主线基准：docs/MAINLINE_STATUS.md",
        ]

        for text in badges:
            badge = QLabel(text)
            badge.setObjectName("Badge")
            badge.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            stats_layout.addWidget(badge)

        stats_layout.addStretch(1)
        return stats_layout

    def _populate_modules(self) -> None:
        for module in self.modules:
            item = QListWidgetItem(module.name)
            item.setData(Qt.ItemDataRole.UserRole, module.key)
            item.setToolTip(module.summary)
            self.module_list.addItem(item)

    def _on_module_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.modules):
            return
        self._render_module(self.modules[index])

    def _render_module(self, module: FeatureModule) -> None:
        module_title = module.name
        self.name_label.setText(module_title)
        self.meta_label.setText(
            f"领域：{display_module_area(module.area)}    状态：{display_module_status(module.status)}    里程碑：{module.milestone}"
        )
        self.summary_text.setPlainText(module.summary)
        self.acceptance_text.setPlainText("\n".join(f"• {item}" for item in module.acceptance))
        self.panel_stack.setCurrentWidget(self._panel_pages.get(module.key, self.dashboard_panel))
        self.title_bar.set_context_text(module_title)

    def _build_packet_console_dock(self) -> None:
        self.packet_console = PacketConsoleWidget(
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self.packet_console_dock = QDockWidget("报文分析台", self)
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

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.title_bar.sync_window_state(self.isMaximized())

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.sync_window_state(self.isMaximized())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._resize_edges_for_pos(event.position().toPoint())
            handle = self.windowHandle()
            if handle is not None and edges != Qt.Edge(0) and not self.isMaximized() and handle.startSystemResize(edges):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self.isMaximized():
            edges = self._resize_edges_for_pos(event.position().toPoint())
            self.setCursor(self._cursor_for_edges(edges))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.unsetCursor()
        super().leaveEvent(event)

    def _resize_edges_for_pos(self, position: QPoint):
        if self.isMaximized():
            return Qt.Edge(0)

        x = position.x()
        y = position.y()
        width = self.width()
        height = self.height()
        edges = Qt.Edge(0)

        if x <= WINDOW_EDGE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif x >= width - WINDOW_EDGE_MARGIN:
            edges |= Qt.Edge.RightEdge

        if y <= WINDOW_EDGE_MARGIN:
            edges |= Qt.Edge.TopEdge
        elif y >= height - WINDOW_EDGE_MARGIN:
            edges |= Qt.Edge.BottomEdge

        return edges

    def _cursor_for_edges(self, edges):
        if edges == Qt.Edge(0):
            return Qt.CursorShape.ArrowCursor
        if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        if edges in (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        ):
            return Qt.CursorShape.SizeFDiagCursor
        return Qt.CursorShape.SizeBDiagCursor

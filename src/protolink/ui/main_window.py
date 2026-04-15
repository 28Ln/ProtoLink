from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
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
from protolink.core.models import FeatureModule
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
CONTENT_SPLITTER_DETAIL_WIDTH = 200
PACKET_DOCK_TARGET_HEIGHT = 100


class WindowTitleBar(QFrame):
    def __init__(self, window: "ProtoLinkMainWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(10)

        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(2)

        self.title_label = QLabel("ProtoLink")
        self.title_label.setObjectName("TitleBarTitle")
        self.subtitle_label = QLabel(APPLICATION_SUBTITLE)
        self.subtitle_label.setObjectName("TitleBarSubtitle")
        self.context_label = QLabel()
        self.context_label.setObjectName("TitleBarContext")
        self.context_label.setVisible(False)

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

    def set_context_text(self, text: str | None) -> None:
        normalized = (text or "").strip()
        if normalized:
            self.context_label.setText(normalized)
            self.context_label.show()
            return
        self.context_label.clear()
        self.context_label.hide()

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
        self._initial_layout_applied = False
        self._module_context_visible = True
        self._module_context_auto_collapsed = False
        self._last_context_splitter_sizes: list[int] | None = None
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
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(14)

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
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(280)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(10)

        title = QLabel("快速导航")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("按业务链路切换模块。")
        subtitle.setObjectName("MetaLabel")
        subtitle.setWordWrap(True)

        workspace_card = QFrame()
        workspace_card.setObjectName("WorkspaceCard")
        workspace_layout = QVBoxLayout(workspace_card)
        workspace_layout.setContentsMargins(12, 12, 12, 12)
        workspace_layout.setSpacing(4)

        workspace_title = QLabel("当前项目")
        workspace_title.setObjectName("WorkspaceEyebrow")
        workspace_name = QLabel(self._format_workspace_name(self.workspace.root))
        workspace_name.setObjectName("WorkspaceTitle")
        self.workspace_label = QLabel(self._format_sidebar_path(self.workspace.root, keep_segments=2))
        self.workspace_label.setObjectName("PathLabel")
        self.workspace_label.setWordWrap(True)
        self.workspace_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.workspace_label.setToolTip(str(self.workspace.root))

        self.workspace_meta_label = QLabel("悬停可查看日志、抓包与导出目录。")
        self.workspace_meta_label.setObjectName("MetaLabel")
        self.workspace_meta_label.setWordWrap(True)
        self.workspace_meta_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.workspace_meta_label.setToolTip(self._workspace_paths_tooltip())

        workspace_layout.addWidget(workspace_title)
        workspace_layout.addWidget(workspace_name)
        workspace_layout.addWidget(self.workspace_label)
        workspace_layout.addWidget(self.workspace_meta_label)

        module_header = QHBoxLayout()
        module_header.setContentsMargins(0, 0, 0, 0)
        module_header.setSpacing(8)
        module_title = QLabel("全部模块")
        module_title.setObjectName("SectionTitle")
        module_count = QLabel(f"{len(self.modules)} 项")
        module_count.setObjectName("SidebarPill")
        module_header.addWidget(module_title)
        module_header.addStretch(1)
        module_header.addWidget(module_count)

        self.module_list = QListWidget()
        self.module_list.setObjectName("ModuleList")
        self.module_list.currentRowChanged.connect(self._on_module_changed)

        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addWidget(workspace_card)
        sidebar_layout.addLayout(module_header)
        sidebar_layout.addWidget(self.module_list, 1)
        return sidebar

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("Hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(12, 10, 12, 10)
        hero_layout.setSpacing(12)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(2)

        hero_title = QLabel("连接、调试与分析")
        hero_title.setObjectName("HeroTitle")
        hero_subtitle = QLabel("在同一桌面工作区内完成连接配置、协议验证、数据记录与自动化处理。")
        hero_subtitle.setObjectName("HeroSubtitle")
        hero_subtitle.setWordWrap(True)

        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_subtitle)

        hero_layout.addLayout(hero_copy, 1)
        hero_layout.addWidget(self._build_stats_panel(), 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        panel_surface = QFrame()
        panel_surface.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel_surface)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(0)

        self.panel_stack = QStackedWidget()
        self.panel_stack.setObjectName("PanelStack")

        panel_layout.addWidget(self.panel_stack, 1)

        context_surface = QFrame()
        context_surface.setObjectName("Panel")
        context_surface.setMinimumWidth(190)
        context_surface.setMaximumWidth(280)
        context_layout = QVBoxLayout(context_surface)
        context_layout.setContentsMargins(14, 14, 14, 14)
        context_layout.setSpacing(8)

        section_header = QHBoxLayout()
        section_header.setContentsMargins(0, 0, 0, 0)
        section_header.setSpacing(8)
        self.name_label = QLabel()
        self.name_label.setObjectName("ModuleTitle")
        self.name_label.setWordWrap(True)
        self.context_toggle_button = QToolButton()
        self.context_toggle_button.setObjectName("SubtleButton")
        self.context_toggle_button.setText("隐藏")
        self.context_toggle_button.setToolTip("隐藏或显示右侧概览")
        self.context_toggle_button.setAutoRaise(False)
        self.context_toggle_button.clicked.connect(self.toggle_module_context)
        section_header.addWidget(self.name_label, 1)
        section_header.addWidget(self.context_toggle_button)
        self.meta_label = QLabel()
        self.meta_label.setObjectName("MetaLabel")
        self.meta_label.setWordWrap(True)

        self.module_context_tabs = QTabWidget()
        self.module_context_tabs.setObjectName("MainContentTabs")
        self.module_context_tabs.setDocumentMode(True)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("这里会显示模块的主要能力、适用场景与使用边界。")

        self.acceptance_text = QTextEdit()
        self.acceptance_text.setReadOnly(True)
        self.acceptance_text.setPlaceholderText("这里会显示建议的操作清单与验证要点。")

        summary_page = QWidget()
        summary_layout = QVBoxLayout(summary_page)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addWidget(self.summary_text, 1)

        acceptance_page = QWidget()
        acceptance_layout = QVBoxLayout(acceptance_page)
        acceptance_layout.setContentsMargins(0, 0, 0, 0)
        acceptance_layout.addWidget(self.acceptance_text, 1)

        self.module_context_tabs.addTab(summary_page, "概览")
        self.module_context_tabs.addTab(acceptance_page, "清单")

        context_layout.addLayout(section_header)
        context_layout.addWidget(self.meta_label)
        context_layout.addWidget(self.module_context_tabs, 1)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setObjectName("MainContentSplitter")
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(panel_surface)
        self.content_splitter.addWidget(context_surface)
        self.content_splitter.setStretchFactor(0, 4)
        self.content_splitter.setStretchFactor(1, 1)
        self.module_context_surface = context_surface

        content_layout.addWidget(hero)
        content_layout.addWidget(self.content_splitter, 1)

        self._build_module_panels()
        return content

    def _build_dashboard_panel(self) -> QWidget:
        dashboard = QFrame()
        dashboard.setObjectName("Panel")
        layout = QVBoxLayout(dashboard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("选择模块开始")
        title.setObjectName("SectionTitle")

        overview = QLabel("从左侧切换模块即可进入连接、调试和分析流程；底部分析台会承接当前会话的原始数据。")
        overview.setObjectName("MetaLabel")
        overview.setWordWrap(True)

        directories = QLabel(
            "\n".join(
                (
                    f"当前项目：{self._format_workspace_name(self.workspace.root)}",
                    f"项目位置：{self._format_sidebar_path(self.workspace.root, keep_segments=3)}",
                    "日志、抓包与导出目录会随操作自动归档；悬停可查看完整路径。",
                )
            )
        )
        directories.setObjectName("PathLabel")
        directories.setWordWrap(True)
        directories.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        directories.setToolTip(self._workspace_paths_tooltip())

        checklist = QTextEdit()
        checklist.setReadOnly(True)
        checklist.setPlainText(
            "\n".join(
                (
                    "1. 先在左侧选择需要的模块，再进入对应的连接或调试流程。",
                    "2. 设备通信产生的数据会自动汇入底部报文台，便于筛选、解析和回放。",
                    "3. 右侧概览区提供当前模块的能力说明与关键步骤，可按需隐藏以释放空间。",
                    "4. 需要更专注的工作区时，可先隐藏右侧概览，再按需展开底部分析台。",
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

    def _build_stats_panel(self) -> QWidget:
        stats_panel = QWidget()
        stats_layout = QGridLayout(stats_panel)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(6)

        area_counts = Counter(display_module_area(module.area) for module in self.modules if module.key != "dashboard")
        badges = [
            f"连接链路 {area_counts.get('传输链路', 0)}",
            f"协议与分析 {area_counts.get('协议调试', 0) + area_counts.get('共享能力', 0)}",
            f"自动化与诊断 {area_counts.get('自动化', 0) + area_counts.get('运维诊断', 0)}",
        ]

        for index, text in enumerate(badges):
            badge = QLabel(text)
            badge.setObjectName("HeroBadge")
            badge.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            stats_layout.addWidget(badge, 0, index)
            stats_layout.setColumnStretch(index, 1)
        return stats_panel

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
        self.meta_label.setText(f"{display_module_area(module.area)} · {display_module_status(module.status)}")
        self.summary_text.setPlainText(module.summary)
        self.acceptance_text.setPlainText("\n".join(f"• {item}" for item in module.acceptance))
        self.panel_stack.setCurrentWidget(self._panel_pages.get(module.key, self.dashboard_panel))
        self.title_bar.set_context_text(None if module.key == "dashboard" else module_title)

    def _build_packet_console_dock(self) -> None:
        self.packet_console = PacketConsoleWidget(
            self.inspector,
            replay_service=self.packet_replay_service,
            workspace=self.workspace,
        )
        self.packet_console_scroll = QScrollArea()
        self.packet_console_scroll.setObjectName("PanelScrollArea")
        self.packet_console_scroll.setWidgetResizable(True)
        self.packet_console_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.packet_console_scroll.setWidget(self.packet_console)

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
        self.packet_console_dock.setMinimumHeight(92)
        self.packet_console_dock.setWidget(self.packet_console_scroll)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.packet_console_dock)

    def _apply_initial_workspace_layout(self) -> None:
        if self._initial_layout_applied:
            return

        self._initial_layout_applied = True
        splitter_width = max(self.content_splitter.width(), 960)
        detail_width = min(CONTENT_SPLITTER_DETAIL_WIDTH, max(200, splitter_width // 7))
        self.content_splitter.setSizes([splitter_width - detail_width, detail_width])
        self.resizeDocks(
            [self.packet_console_dock],
            [max(92, min(PACKET_DOCK_TARGET_HEIGHT, int(self.height() * 0.14)))],
            Qt.Orientation.Vertical,
        )
        if self.width() <= 1366 and self._module_context_visible:
            self._set_module_context_visible(False, manual=False)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._initial_layout_applied:
            QTimer.singleShot(0, self._apply_initial_workspace_layout)

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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._initial_layout_applied:
            return
        if self.width() > 1366 and self._module_context_auto_collapsed and not self._module_context_visible:
            self._set_module_context_visible(True, manual=False)

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

    def toggle_module_context(self) -> None:
        self._set_module_context_visible(not self._module_context_visible, manual=True)

    def _set_module_context_visible(self, visible: bool, *, manual: bool) -> None:
        if visible == self._module_context_visible:
            return

        if not visible:
            self._last_context_splitter_sizes = self.content_splitter.sizes()
            self.module_context_surface.hide()
            self.content_splitter.setSizes([max(1, self.content_splitter.width()), 0])
            self.context_toggle_button.setText("显示")
            self._module_context_visible = False
            self._module_context_auto_collapsed = not manual
            return

        self.module_context_surface.show()
        restore_sizes = self._last_context_splitter_sizes
        if restore_sizes is None or len(restore_sizes) != 2:
            splitter_width = max(self.content_splitter.width(), 960)
            detail_width = min(CONTENT_SPLITTER_DETAIL_WIDTH, max(200, splitter_width // 7))
            restore_sizes = [splitter_width - detail_width, detail_width]
        self.content_splitter.setSizes(restore_sizes)
        self.context_toggle_button.setText("隐藏")
        self._module_context_visible = True
        self._module_context_auto_collapsed = False

    def _format_workspace_name(self, path) -> str:
        return path.name or str(path)

    def _workspace_paths_tooltip(self) -> str:
        return "\n".join(
            (
                f"工作区：{self.workspace.root}",
                f"日志：{self.workspace.logs}",
                f"抓包：{self.workspace.captures}",
                f"导出：{self.workspace.exports}",
            )
        )

    def _format_sidebar_path(self, path, *, keep_segments: int) -> str:
        parts = list(path.parts)
        if len(parts) <= keep_segments:
            return str(path)
        tail = "\\".join(parts[-keep_segments:])
        return f"...\\{tail}"

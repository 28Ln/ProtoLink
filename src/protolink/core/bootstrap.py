from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from protolink import __version__
from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.application.capture_replay_job_service import CaptureReplayJobService
from protolink.application.channel_bridge_runtime_service import ChannelBridgeRuntimeService
from protolink.application.data_tools_service import DataToolsService
from protolink.application.device_scan_execution_service import DeviceScanExecutionService
from protolink.application.network_tools_service import NetworkToolsService
from protolink.application.packet_replay_service import PacketReplayExecutionService
from protolink.application.register_monitor_service import RegisterMonitorService
from protolink.application.rule_engine_service import RuleEngineService
from protolink.application.script_console_service import ScriptConsoleService
from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.application.serial_service import SerialSessionService
from protolink.application.mqtt_client_service import MqttClientSessionService
from protolink.application.mqtt_server_service import MqttServerSessionService
from protolink.application.tcp_client_service import TcpClientSessionService
from protolink.application.tcp_server_service import TcpServerSessionService
from protolink.application.timed_task_service import TimedTaskService
from protolink.application.udp_service import UdpSessionService
from protolink.core.extensions import (
    ExtensionDescriptorRegistry,
    ExtensionLoadingPlanReport,
    ExtensionRegistryConfig,
    WorkspaceExtensionAuditReport,
    audit_workspace_extensions,
    build_extension_descriptor_registry,
    build_extension_loading_plan,
    load_extension_registry_config,
)
from protolink.core.event_bus import EventBus
from protolink.core.logging import (
    InMemoryLogStore,
    RuntimeFailureEvidenceRecorder,
    StructuredLogEntry,
    WorkspaceJsonlLogWriter,
    default_config_failure_evidence_path,
    default_runtime_failure_evidence_path,
    default_workspace_log_path,
)
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.plugin_manifests import PluginManifestAuditReport, audit_workspace_plugin_manifests
from protolink.core.settings import (
    AppSettings,
    SettingsLayout,
    default_settings_root,
    ensure_settings_layout,
    load_app_settings,
    remember_workspace,
    resolve_workspace_root,
    save_app_settings,
)
from protolink.core.automation_rule_profiles import default_automation_rules_profile_path
from protolink.core.transport import (
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportKind,
    TransportRegistry,
)
from protolink.core.workspace import WorkspaceLayout, ensure_workspace_layout
from protolink.core.wiring import wire_packet_inspector, wire_transport_logging
from protolink.presentation import display_transport_name
from protolink.transports.serial import SerialTransportAdapter
from protolink.transports.mqtt_client import MqttClientTransportAdapter
from protolink.transports.mqtt_server import MqttServerTransportAdapter
from protolink.transports.tcp_client import TcpClientTransportAdapter
from protolink.transports.tcp_server import TcpServerTransportAdapter
from protolink.transports.udp import UdpTransportAdapter


@dataclass(frozen=True, slots=True)
class AppContext:
    base_dir: Path
    settings_layout: SettingsLayout
    settings: AppSettings
    workspace: WorkspaceLayout
    transport_registry: TransportRegistry
    event_bus: EventBus
    log_store: InMemoryLogStore
    runtime_failure_evidence_recorder: RuntimeFailureEvidenceRecorder
    workspace_log_writer: WorkspaceJsonlLogWriter
    packet_inspector: PacketInspectorState
    plugin_manifest_audit: PluginManifestAuditReport
    data_tools_service: DataToolsService
    network_tools_service: NetworkToolsService
    serial_session_service: SerialSessionService
    mqtt_client_service: MqttClientSessionService
    mqtt_server_service: MqttServerSessionService
    tcp_client_service: TcpClientSessionService
    tcp_server_service: TcpServerSessionService
    udp_service: UdpSessionService
    packet_replay_service: PacketReplayExecutionService
    register_monitor_service: RegisterMonitorService
    auto_response_runtime_service: AutoResponseRuntimeService
    rule_engine_service: RuleEngineService
    device_scan_execution_service: DeviceScanExecutionService
    script_host_service: ScriptHostService
    script_console_service: ScriptConsoleService
    timed_task_service: TimedTaskService
    channel_bridge_runtime_service: ChannelBridgeRuntimeService
    capture_replay_job_service: CaptureReplayJobService
    extension_registry_config: ExtensionRegistryConfig
    extension_audit_report: WorkspaceExtensionAuditReport
    extension_registry: ExtensionDescriptorRegistry
    extension_loading_plan: ExtensionLoadingPlanReport


class PlaceholderTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor) -> None:
        super().__init__(descriptor)

    async def open(self, config: TransportConfig) -> None:
        self.bind_session(config)
        raise NotImplementedError(f"{self.descriptor.display_name}尚未实现。")

    async def close(self) -> None:
        return None

    async def send(self, payload: bytes, metadata=None) -> None:
        raise NotImplementedError(f"{self.descriptor.display_name}尚未实现。")


def default_transport_descriptors() -> tuple[TransportDescriptor, ...]:
    return (
        TransportDescriptor(
            kind=TransportKind.SERIAL,
            display_name=display_transport_name(TransportKind.SERIAL),
            capabilities=TransportCapabilities(supports_binary_payloads=True, supports_reconnect=True),
        ),
        TransportDescriptor(
            kind=TransportKind.TCP_CLIENT,
            display_name=display_transport_name(TransportKind.TCP_CLIENT),
            capabilities=TransportCapabilities(supports_binary_payloads=True, supports_tls=True),
        ),
        TransportDescriptor(
            kind=TransportKind.TCP_SERVER,
            display_name=display_transport_name(TransportKind.TCP_SERVER),
            capabilities=TransportCapabilities(can_listen=True, can_accept_clients=True, supports_binary_payloads=True),
        ),
        TransportDescriptor(
            kind=TransportKind.UDP,
            display_name=display_transport_name(TransportKind.UDP),
            capabilities=TransportCapabilities(can_listen=True, supports_binary_payloads=True),
        ),
        TransportDescriptor(
            kind=TransportKind.MQTT_CLIENT,
            display_name=display_transport_name(TransportKind.MQTT_CLIENT),
            capabilities=TransportCapabilities(supports_topics=True, supports_binary_payloads=True, supports_tls=True),
        ),
        TransportDescriptor(
            kind=TransportKind.MQTT_SERVER,
            display_name=display_transport_name(TransportKind.MQTT_SERVER),
            capabilities=TransportCapabilities(
                can_listen=True,
                can_accept_clients=True,
                supports_topics=True,
                supports_binary_payloads=True,
                supports_tls=True,
            ),
        ),
    )


def build_transport_registry() -> TransportRegistry:
    registry = TransportRegistry()
    for descriptor in default_transport_descriptors():
        if descriptor.kind == TransportKind.SERIAL:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: SerialTransportAdapter(descriptor),
            )
            continue
        if descriptor.kind == TransportKind.TCP_CLIENT:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: TcpClientTransportAdapter(descriptor),
            )
            continue
        if descriptor.kind == TransportKind.MQTT_CLIENT:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: MqttClientTransportAdapter(descriptor),
            )
            continue
        if descriptor.kind == TransportKind.MQTT_SERVER:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: MqttServerTransportAdapter(descriptor),
            )
            continue
        if descriptor.kind == TransportKind.TCP_SERVER:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: TcpServerTransportAdapter(descriptor),
            )
            continue
        if descriptor.kind == TransportKind.UDP:
            registry.register(
                descriptor.kind,
                lambda descriptor=descriptor: UdpTransportAdapter(descriptor),
            )
            continue
        registry.register(
            descriptor.kind,
            lambda descriptor=descriptor: PlaceholderTransportAdapter(descriptor),
        )
    return registry


def bootstrap_app_context(
    base_dir: Path,
    *,
    workspace_override: Path | None = None,
    persist_settings: bool = False,
    remember_workspace_override: bool = True,
) -> AppContext:
    settings_layout = ensure_settings_layout(default_settings_root(base_dir))
    settings_failure_recorder = RuntimeFailureEvidenceRecorder(default_config_failure_evidence_path(settings_layout.root))
    settings = load_app_settings(
        settings_layout,
        on_error=lambda code, message, details: settings_failure_recorder.append(
            source="settings",
            code=code,
            message=message,
            details=details,
        ),
    )
    workspace_root = resolve_workspace_root(base_dir, settings, workspace_override)
    workspace_failure_recorder = RuntimeFailureEvidenceRecorder(default_config_failure_evidence_path(workspace_root))
    workspace = ensure_workspace_layout(
        workspace_root,
        on_error=lambda code, message, details: workspace_failure_recorder.append(
            source="workspace",
            code=code,
            message=message,
            details=details,
        ),
    )

    if persist_settings or (workspace_override is not None and remember_workspace_override):
        settings = remember_workspace(settings, workspace.root)
        save_app_settings(settings_layout, settings)

    runtime_failure_evidence_recorder = RuntimeFailureEvidenceRecorder(
        default_runtime_failure_evidence_path(workspace.logs)
    )
    event_bus = EventBus(
        failure_recorder=lambda error: runtime_failure_evidence_recorder.append_handler_error(
            event_type=error.event_type.__name__,
            handler_name=getattr(error.handler, "__name__", repr(error.handler)),
            error=error.error,
        )
    )
    log_store = InMemoryLogStore()
    workspace_log_writer = WorkspaceJsonlLogWriter(
        default_workspace_log_path(workspace.logs),
        failure_evidence_recorder=runtime_failure_evidence_recorder,
    )
    packet_inspector = PacketInspectorState()
    plugin_manifest_audit = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    data_tools_service = DataToolsService()
    network_tools_service = NetworkToolsService()
    transport_registry = build_transport_registry()
    wire_transport_logging(event_bus, log_store)
    wire_packet_inspector(event_bus, packet_inspector)
    event_bus.subscribe(StructuredLogEntry, workspace_log_writer.append)
    serial_session_service = SerialSessionService(transport_registry, event_bus, workspace)
    mqtt_client_service = MqttClientSessionService(transport_registry, event_bus, workspace)
    mqtt_server_service = MqttServerSessionService(transport_registry, event_bus, workspace)
    tcp_client_service = TcpClientSessionService(transport_registry, event_bus, workspace)
    tcp_server_service = TcpServerSessionService(transport_registry, event_bus, workspace)
    udp_service = UdpSessionService(transport_registry, event_bus, workspace)
    for service in (
        serial_session_service,
        mqtt_client_service,
        mqtt_server_service,
        tcp_client_service,
        tcp_server_service,
        udp_service,
    ):
        service.set_shutdown_failure_recorder(
            lambda code, message, details, source=service._transport_kind.value: runtime_failure_evidence_recorder.append(
                source=f"{source}_session_service",
                code=code,
                message=message,
                details=details,
            )
        )
    packet_replay_service = PacketReplayExecutionService(
        {
            TransportKind.SERIAL: serial_session_service,
            TransportKind.MQTT_CLIENT: mqtt_client_service,
            TransportKind.MQTT_SERVER: mqtt_server_service,
            TransportKind.TCP_CLIENT: tcp_client_service,
            TransportKind.TCP_SERVER: tcp_server_service,
            TransportKind.UDP: udp_service,
        }
    )
    register_monitor_service = RegisterMonitorService(event_bus)
    auto_response_runtime_service = AutoResponseRuntimeService(
        event_bus,
        {
            TransportKind.SERIAL: serial_session_service,
            TransportKind.MQTT_CLIENT: mqtt_client_service,
            TransportKind.MQTT_SERVER: mqtt_server_service,
            TransportKind.TCP_CLIENT: tcp_client_service,
            TransportKind.TCP_SERVER: tcp_server_service,
            TransportKind.UDP: udp_service,
        },
    )
    rule_engine_service = RuleEngineService(
        packet_replay_service=packet_replay_service,
        auto_response_runtime_service=auto_response_runtime_service,
        profile_path=default_automation_rules_profile_path(workspace.profiles),
        event_bus=event_bus,
    )
    device_scan_execution_service = DeviceScanExecutionService(
        event_bus,
        {
            TransportKind.SERIAL: serial_session_service,
            TransportKind.TCP_CLIENT: tcp_client_service,
            TransportKind.TCP_SERVER: tcp_server_service,
            TransportKind.UDP: udp_service,
            TransportKind.MQTT_CLIENT: mqtt_client_service,
            TransportKind.MQTT_SERVER: mqtt_server_service,
        },
    )
    script_host_service = ScriptHostService()
    script_host_service.register_host(PythonInlineScriptHost())
    script_console_service = ScriptConsoleService(
        script_host_service,
        workspace,
        event_bus=event_bus,
    )
    channel_bridge_runtime_service = ChannelBridgeRuntimeService(
        event_bus,
        script_host_service,
        {
            TransportKind.SERIAL: serial_session_service,
            TransportKind.MQTT_CLIENT: mqtt_client_service,
            TransportKind.MQTT_SERVER: mqtt_server_service,
            TransportKind.TCP_CLIENT: tcp_client_service,
            TransportKind.TCP_SERVER: tcp_server_service,
            TransportKind.UDP: udp_service,
        },
    )
    capture_replay_job_service = CaptureReplayJobService(packet_replay_service)
    timed_task_service = TimedTaskService(rule_engine_service, event_bus=event_bus)
    extension_registry_config = load_extension_registry_config(workspace.plugins)
    extension_audit_report = audit_workspace_extensions(workspace.plugins, app_version=__version__)
    extension_registry = build_extension_descriptor_registry(extension_audit_report)
    extension_loading_plan = build_extension_loading_plan(extension_registry, extension_registry_config)

    return AppContext(
        base_dir=base_dir,
        settings_layout=settings_layout,
        settings=settings,
        workspace=workspace,
        transport_registry=transport_registry,
        event_bus=event_bus,
        log_store=log_store,
        runtime_failure_evidence_recorder=runtime_failure_evidence_recorder,
        workspace_log_writer=workspace_log_writer,
        packet_inspector=packet_inspector,
        plugin_manifest_audit=plugin_manifest_audit,
        data_tools_service=data_tools_service,
        network_tools_service=network_tools_service,
        serial_session_service=serial_session_service,
        mqtt_client_service=mqtt_client_service,
        mqtt_server_service=mqtt_server_service,
        tcp_client_service=tcp_client_service,
        tcp_server_service=tcp_server_service,
        udp_service=udp_service,
        packet_replay_service=packet_replay_service,
        register_monitor_service=register_monitor_service,
        auto_response_runtime_service=auto_response_runtime_service,
        rule_engine_service=rule_engine_service,
        device_scan_execution_service=device_scan_execution_service,
        script_host_service=script_host_service,
        script_console_service=script_console_service,
        timed_task_service=timed_task_service,
        channel_bridge_runtime_service=channel_bridge_runtime_service,
        capture_replay_job_service=capture_replay_job_service,
        extension_registry_config=extension_registry_config,
        extension_audit_report=extension_audit_report,
        extension_registry=extension_registry,
        extension_loading_plan=extension_loading_plan,
    )

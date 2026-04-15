from dataclasses import replace
from pathlib import Path

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.logging import load_runtime_failure_evidence
from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import ConnectionState
from protolink.core.transport import TransportKind
from protolink.transports.mqtt_client import MqttClientTransportAdapter
from protolink.transports.mqtt_server import MqttServerTransportAdapter
from protolink.transports.serial import SerialTransportAdapter
from protolink.transports.tcp_client import TcpClientTransportAdapter
from protolink.transports.tcp_server import TcpServerTransportAdapter
from protolink.transports.udp import UdpTransportAdapter


def test_bootstrap_app_context_builds_workspace_and_transport_registry(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)

    assert context.workspace.root == (tmp_path / "workspace").resolve()
    assert context.workspace_log_writer.path == context.workspace.logs / "transport-events.jsonl"
    assert context.network_tools_service.snapshot.local_hostname
    assert TransportKind.SERIAL in context.transport_registry.registered_kinds()
    assert TransportKind.MQTT_CLIENT in context.transport_registry.registered_kinds()
    assert TransportKind.MQTT_SERVER in context.transport_registry.registered_kinds()
    assert TransportKind.TCP_CLIENT in context.transport_registry.registered_kinds()
    assert TransportKind.TCP_SERVER in context.transport_registry.registered_kinds()
    assert TransportKind.UDP in context.transport_registry.registered_kinds()
    assert TransportKind.MQTT_SERVER in context.transport_registry.registered_kinds()
    assert isinstance(context.transport_registry.create(TransportKind.SERIAL), SerialTransportAdapter)
    assert isinstance(context.transport_registry.create(TransportKind.MQTT_CLIENT), MqttClientTransportAdapter)
    assert isinstance(context.transport_registry.create(TransportKind.MQTT_SERVER), MqttServerTransportAdapter)
    assert isinstance(context.transport_registry.create(TransportKind.TCP_CLIENT), TcpClientTransportAdapter)
    assert isinstance(context.transport_registry.create(TransportKind.TCP_SERVER), TcpServerTransportAdapter)
    assert isinstance(context.transport_registry.create(TransportKind.UDP), UdpTransportAdapter)
    assert context.serial_session_service.snapshot.baudrate == 9600
    assert context.mqtt_client_service.snapshot.port == 1883
    assert context.mqtt_server_service.snapshot.port == 1883
    assert context.tcp_client_service.snapshot.port == 502
    assert context.tcp_server_service.snapshot.port == 502
    assert context.udp_service.snapshot.remote_port == 502
    assert context.packet_replay_service.snapshot.running is False
    assert context.register_monitor_service.snapshot.point_names == ()
    assert context.auto_response_runtime_service.snapshot.rule_count == 0
    assert context.rule_engine_service.snapshot.rule_names == ()
    assert context.device_scan_execution_service.snapshot.running is False
    assert context.script_host_service.snapshot.available_languages
    assert ScriptLanguage.PYTHON in context.script_console_service.snapshot.available_languages
    assert context.timed_task_service.snapshot.running is False
    assert context.channel_bridge_runtime_service.snapshot.bridge_names == ()
    assert context.capture_replay_job_service.snapshot.job_names == ()
    assert context.plugin_manifest_audit.valid_manifest_count == 0
    assert context.extension_registry.descriptor_count == 0


def test_bootstrap_persists_workspace_when_requested(tmp_path: Path) -> None:
    workspace_override = tmp_path / "workspace" / "bench-a"
    context = bootstrap_app_context(
        tmp_path,
        workspace_override=workspace_override,
        persist_settings=True,
    )

    assert context.settings_layout.settings_file.exists()
    assert context.workspace.root == workspace_override.resolve()


def test_bootstrap_session_services_record_shutdown_close_failures(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service

    class _FailingFuture:
        def result(self, timeout: float | None = None) -> None:
            raise RuntimeError("close failed")

    class _FailingRuntime:
        def submit(self, coroutine):
            coroutine.close()
            return _FailingFuture()

        def shutdown(self) -> None:
            return None

    class _AdapterSession:
        session_id = "bench-session"
        target = "COM9"

    class _FailingAdapter:
        session = _AdapterSession()

        async def close(self) -> None:
            return None

    service._runtime = _FailingRuntime()
    service._adapter = _FailingAdapter()
    service._snapshot = replace(
        service.snapshot,
        connection_state=ConnectionState.CONNECTED,
        active_session_id="bench-session",
    )

    service.shutdown()

    evidence_file, evidence_entries, evidence_error = load_runtime_failure_evidence(context.workspace.logs)

    assert evidence_error is None
    assert evidence_file is not None
    assert any(entry["code"] == "service_shutdown_close_failed" for entry in evidence_entries)
    failure_entry = next(entry for entry in evidence_entries if entry["code"] == "service_shutdown_close_failed")
    assert failure_entry["source"] == "serial_session_service"
    assert failure_entry["message"] == "close failed"
    assert failure_entry["details"]["transport_kind"] == "serial"
    assert failure_entry["details"]["session_id"] == "bench-session"
    assert failure_entry["details"]["target"] == "COM9"
    assert failure_entry["details"]["operation"] == "shutdown"


def test_bootstrap_session_services_record_close_failures(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.serial_session_service

    class _FailingFuture:
        def result(self, timeout: float | None = None) -> None:
            raise RuntimeError("close failed")

    class _AdapterSession:
        session_id = "bench-session"
        target = "COM9"

    class _FailingAdapter:
        session = _AdapterSession()

    adapter = _FailingAdapter()
    service._adapter = adapter
    service._snapshot = replace(
        service.snapshot,
        connection_state=ConnectionState.CONNECTED,
        active_session_id="bench-session",
    )

    service._handle_future_result("close", _FailingFuture(), adapter)

    evidence_file, evidence_entries, evidence_error = load_runtime_failure_evidence(context.workspace.logs)

    assert evidence_error is None
    assert evidence_file is not None
    assert any(entry["code"] == "service_close_failed" for entry in evidence_entries)
    failure_entry = next(entry for entry in evidence_entries if entry["code"] == "service_close_failed")
    assert failure_entry["source"] == "serial_session_service"
    assert failure_entry["message"] == "close failed"
    assert failure_entry["details"]["transport_kind"] == "serial"
    assert failure_entry["details"]["session_id"] == "bench-session"
    assert failure_entry["details"]["target"] == "COM9"
    assert failure_entry["details"]["operation"] == "close"
    assert service._adapter is None

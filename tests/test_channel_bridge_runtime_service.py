import pickle
import subprocess
import threading
import time
from collections.abc import Mapping

from protolink.application import script_host_service as script_host_service_module
from protolink.application.channel_bridge_runtime_service import (
    BRIDGE_SCRIPT_TIMEOUT_SECONDS,
    ChannelBridgeRuntimeService,
)
from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, StructuredLogEntry, create_log_entry
from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import TransportKind


class _FakeBridgeTarget:
    def __init__(self, *, connected: bool = True, session_id: str | None = None, peer: str | None = None) -> None:
        self.connected = connected
        self.sent: list[tuple[bytes, dict[str, str]]] = []
        self.snapshot = type(
            "Snapshot",
            (),
            {
                "active_session_id": session_id,
                "selected_client_peer": peer,
            },
        )()

    def is_connected(self) -> bool:
        return self.connected

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        self.sent.append((payload, dict(metadata or {})))


class _FailingBridgeTarget(_FakeBridgeTarget):
    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        raise RuntimeError("bridge sink offline")


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for channel bridge condition.")


def _completed_script_run(
    *,
    success: bool,
    error: str | None = None,
    output: str = "",
    result: object = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        args=[script_host_service_module.sys.executable, "-c", "test"],
        returncode=0,
        stdout=pickle.dumps(
            {
                "success": success,
                "output": output,
                "error": error,
                "result_pickle": pickle.dumps(result) if result is not None else None,
            }
        ),
        stderr=b"",
    )


def test_channel_bridge_runtime_service_bridges_inbound_messages() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: target},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="UDP->TCP",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)

        assert target.sent == [
            (
                b"PING",
                {
                    "source": "channel_bridge",
                    "bridge_name": "UDP->TCP",
                    "source_transport_kind": "udp",
                    "target_transport_kind": "tcp_client",
                },
            )
        ]
        assert service.snapshot.last_bridge_name == "UDP->TCP"
        assert service.snapshot.bridged_count == 1
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_applies_script_transform_and_rejects_invalid_bridge() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {
            TransportKind.TCP_SERVER: target,
            TransportKind.UDP: target,
        },
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="MQTT->TCP",
                source_transport_kind=TransportKind.MQTT_CLIENT,
                target_transport_kind=TransportKind.TCP_SERVER,
                script_language=ScriptLanguage.PYTHON,
                script_code="result = payload[::-1]",
            ),
            ChannelBridgeConfig(
                name="Invalid Loop",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.UDP,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.MQTT_CLIENT.value,
                raw_payload=b"ABCD",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)
        assert target.sent[0][0] == b"DCBA"

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (3 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"XYZ",
            )
        )
        _wait_until(lambda: service.snapshot.last_error is not None)
        assert service.snapshot.last_error == "桥接“Invalid Loop”不能在同一种传输类型之间回环。"
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_keeps_newer_error_when_older_script_task_finishes_late(
    monkeypatch,
) -> None:
    run_started = threading.Event()
    allow_first_run_to_finish = threading.Event()
    run_count = 0

    def fake_run(*args, **kwargs):
        nonlocal run_count
        run_count += 1
        if run_count == 1:
            run_started.set()
            allow_first_run_to_finish.wait(timeout=1.0)
            return _completed_script_run(success=True, result=b"DCBA")
        raise AssertionError("unexpected extra script execution")

    monkeypatch.setattr(script_host_service_module.subprocess, "run", fake_run)

    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {
            TransportKind.TCP_SERVER: target,
            TransportKind.UDP: target,
        },
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="MQTT->TCP",
                source_transport_kind=TransportKind.MQTT_CLIENT,
                target_transport_kind=TransportKind.TCP_SERVER,
                script_language=ScriptLanguage.PYTHON,
                script_code="result = payload[::-1]",
            ),
            ChannelBridgeConfig(
                name="Invalid Loop",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.UDP,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.MQTT_CLIENT.value,
                raw_payload=b"ABCD",
            )
        )
        assert run_started.wait(timeout=1.0)

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (3 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"XYZ",
            )
        )
        _wait_until(lambda: service.snapshot.last_error == "桥接“Invalid Loop”不能在同一种传输类型之间回环。")

        allow_first_run_to_finish.set()
        _wait_until(lambda: len(target.sent) == 1)

        assert target.sent[0][0] == b"DCBA"
        assert service.snapshot.last_error == "桥接“Invalid Loop”不能在同一种传输类型之间回环。"
    finally:
        allow_first_run_to_finish.set()
        service.shutdown()


def test_channel_bridge_runtime_service_logs_script_and_send_failures() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    failing_target = _FailingBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: failing_target},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="Broken Script",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="raise RuntimeError('boom')",
            ),
            ChannelBridgeConfig(
                name="Send Failure",
                source_transport_kind=TransportKind.MQTT_CLIENT,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: service.snapshot.last_error is not None)
        assert service.snapshot.last_error == "桥接“Broken Script”脚本失败：boom"

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.MQTT_CLIENT.value,
                raw_payload=b"PONG",
            )
        )
        _wait_until(lambda: any(entry.message == "桥接“Send Failure”发送失败：bridge sink offline" for entry in captured))

        error_entries = [entry for entry in captured if entry.category == "automation.channel_bridge.error"]
        assert [entry.message for entry in error_entries] == [
            "桥接“Broken Script”脚本失败：boom",
            "桥接“Send Failure”发送失败：bridge sink offline",
        ]
        assert error_entries[0].metadata == {
            "bridge_name": "Broken Script",
            "source_transport_kind": "udp",
            "target_transport_kind": "tcp_client",
        }
        assert error_entries[1].metadata == {
            "bridge_name": "Send Failure",
            "source_transport_kind": "mqtt_client",
            "target_transport_kind": "tcp_client",
        }
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_preserves_script_failures_during_host_startup_jitter(
    monkeypatch,
) -> None:
    observed_timeouts: list[float] = []

    def fake_run(*args, **kwargs):
        observed_timeouts.append(float(kwargs["timeout"]))
        if float(kwargs["timeout"]) <= BRIDGE_SCRIPT_TIMEOUT_SECONDS:
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=float(kwargs["timeout"]))
        return _completed_script_run(success=False, error="boom")

    monkeypatch.setattr(script_host_service_module.subprocess, "run", fake_run)

    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: _FakeBridgeTarget()},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="Broken Script",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="raise RuntimeError('boom')",
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )

        _wait_until(lambda: service.snapshot.last_error is not None)

        assert observed_timeouts and observed_timeouts[0] > BRIDGE_SCRIPT_TIMEOUT_SECONDS
        assert service.snapshot.last_error == "桥接“Broken Script”脚本失败：boom"
        assert any(
            entry.message == "桥接“Broken Script”脚本失败：boom"
            for entry in captured
            if entry.category == "automation.channel_bridge.error"
        )
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_times_out_scripts_without_blocking_publish(
    monkeypatch,
) -> None:
    run_started = threading.Event()
    allow_timeout = threading.Event()

    def fake_run(*args, **kwargs):
        run_started.set()
        allow_timeout.wait(timeout=1.0)
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=float(kwargs["timeout"]))

    monkeypatch.setattr(script_host_service_module.subprocess, "run", fake_run)

    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {TransportKind.TCP_CLIENT: _FakeBridgeTarget()},
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="Timeout Bridge",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
                script_language=ScriptLanguage.PYTHON,
                script_code="result = payload",
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"PING",
            )
        )
        assert run_started.wait(timeout=1.0)
        assert not allow_timeout.is_set()

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="operator heartbeat",
                transport_kind=TransportKind.UDP.value,
                raw_payload=b"",
            )
        )

        allow_timeout.set()
        _wait_until(lambda: any(entry.category == "automation.channel_bridge.error" for entry in captured))

        assert "超时" in (service.snapshot.last_error or "")
        assert any("超时" in entry.message for entry in captured if entry.category == "automation.channel_bridge.error")
    finally:
        service.shutdown()


def test_channel_bridge_runtime_service_filters_source_messages_by_active_session() -> None:
    event_bus = EventBus()
    script_host = ScriptHostService()
    script_host.register_host(PythonInlineScriptHost())
    source_scope = _FakeBridgeTarget(session_id="session-a")
    target = _FakeBridgeTarget()
    service = ChannelBridgeRuntimeService(
        event_bus,
        script_host,
        {
            TransportKind.UDP: source_scope,
            TransportKind.TCP_CLIENT: target,
        },
    )
    service.set_bridges(
        (
            ChannelBridgeConfig(
                name="UDP->TCP",
                source_transport_kind=TransportKind.UDP,
                target_transport_kind=TransportKind.TCP_CLIENT,
            ),
        )
    )

    try:
        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                session_id="session-b",
                raw_payload=b"PING",
            )
        )
        time.sleep(0.05)
        assert target.sent == []

        event_bus.publish(
            create_log_entry(
                level=LogLevel.INFO,
                category="transport.message",
                message="Inbound payload (4 bytes)",
                transport_kind=TransportKind.UDP.value,
                session_id="session-a",
                raw_payload=b"PING",
            )
        )
        _wait_until(lambda: len(target.sent) == 1)
        assert target.sent[0][0] == b"PING"
    finally:
        service.shutdown()

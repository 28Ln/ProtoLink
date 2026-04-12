from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from protolink.application.script_host_service import ScriptHostService
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, StructuredLogEntry, create_log_entry
from protolink.core.script_host import ScriptExecutionRequest
from protolink.core.transport import TransportKind

BRIDGE_SCRIPT_TIMEOUT_SECONDS = 1.5


class ChannelBridgeTarget(Protocol):
    def is_connected(self) -> bool:
        ...

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        ...


@dataclass(frozen=True, slots=True)
class ChannelBridgeRuntimeSnapshot:
    bridge_names: tuple[str, ...] = ()
    enabled_bridge_names: tuple[str, ...] = ()
    bridged_count: int = 0
    last_bridge_name: str | None = None
    last_source_session_id: str | None = None
    last_source_peer: str | None = None
    last_bridge_at: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class _BridgeDispatchTask:
    bridge: ChannelBridgeConfig
    entry: StructuredLogEntry
    target: object


class ChannelBridgeRuntimeService:
    def __init__(
        self,
        event_bus: EventBus,
        script_host_service: ScriptHostService,
        targets: Mapping[TransportKind, object],
    ) -> None:
        self._event_bus = event_bus
        self._script_host_service = script_host_service
        self._targets = dict(targets)
        self._bridges: tuple[ChannelBridgeConfig, ...] = ()
        self._snapshot = ChannelBridgeRuntimeSnapshot()
        self._listeners: list[Callable[[ChannelBridgeRuntimeSnapshot], None]] = []
        self._dispatch_queue: queue.Queue[_BridgeDispatchTask | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run_worker, name="ProtoLinkChannelBridgeRuntime", daemon=True)
        self._worker.start()
        self._event_bus.subscribe(StructuredLogEntry, self._on_log_entry)

    @property
    def snapshot(self) -> ChannelBridgeRuntimeSnapshot:
        return self._snapshot

    @property
    def bridges(self) -> tuple[ChannelBridgeConfig, ...]:
        return self._bridges

    def subscribe(self, listener: Callable[[ChannelBridgeRuntimeSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_bridges(self, bridges: tuple[ChannelBridgeConfig, ...]) -> None:
        self._bridges = tuple(bridges)
        self._set_snapshot(
            bridge_names=tuple(sorted(bridge.name for bridge in self._bridges)),
            enabled_bridge_names=tuple(sorted(bridge.name for bridge in self._bridges if bridge.enabled)),
            last_error=None,
        )

    def clear_bridges(self) -> None:
        self.set_bridges(())

    def shutdown(self) -> None:
        self._dispatch_queue.put(None)
        self._worker.join(timeout=1.0)

    def _on_log_entry(self, entry: StructuredLogEntry) -> None:
        if entry.category != "transport.message" or not entry.raw_payload:
            return
        if not entry.message.lower().startswith("inbound "):
            return
        if not entry.transport_kind:
            return
        if entry.metadata.get("source") == "channel_bridge":
            return

        try:
            source_kind = TransportKind(entry.transport_kind)
        except ValueError:
            return
        source_target = self._targets.get(source_kind)
        if source_target is not None:
            source_session_id = _target_active_session_id(source_target)
            if source_session_id and entry.session_id != source_session_id:
                return
            source_peer = _target_selected_peer(source_target)
            if source_peer and entry.metadata.get("peer") != source_peer:
                return

        for bridge in self._bridges:
            if not bridge.enabled or bridge.source_transport_kind != source_kind:
                continue
            if bridge.source_transport_kind == bridge.target_transport_kind:
                self._report_error(
                    f"Bridge '{bridge.name}' cannot bridge a transport kind to itself.",
                    bridge=bridge,
                )
                continue

            target = self._targets.get(bridge.target_transport_kind)
            if target is None or not hasattr(target, "is_connected") or not target.is_connected():
                continue

            self._dispatch_queue.put(_BridgeDispatchTask(bridge=bridge, entry=entry, target=target))

    def _run_worker(self) -> None:
        while True:
            task = self._dispatch_queue.get()
            if task is None:
                return
            self._process_dispatch(task)

    def _process_dispatch(self, task: _BridgeDispatchTask) -> None:
        try:
            transformed = self._transform_payload(task.bridge, task.entry)
        except Exception as exc:
            self._report_error(
                f"Bridge '{task.bridge.name}' script execution failed: {exc}",
                bridge=task.bridge,
            )
            return
        if transformed is None:
            return

        try:
            task.target.send_replay_payload(
                transformed,
                {
                    "source": "channel_bridge",
                    "bridge_name": task.bridge.name,
                    "source_transport_kind": task.bridge.source_transport_kind.value,
                    "target_transport_kind": task.bridge.target_transport_kind.value,
                },
            )
        except Exception as exc:
            self._report_error(
                f"Bridge '{task.bridge.name}' send failed: {exc}",
                bridge=task.bridge,
            )
            return

        self._set_snapshot(
            bridged_count=self._snapshot.bridged_count + 1,
            last_bridge_name=task.bridge.name,
            last_source_session_id=task.entry.session_id,
            last_source_peer=task.entry.metadata.get("peer"),
            last_bridge_at=datetime.now(UTC),
            last_error=None,
        )

    def _transform_payload(self, bridge: ChannelBridgeConfig, entry: StructuredLogEntry) -> bytes | None:
        if bridge.script_language is None or not bridge.script_code.strip():
            return entry.raw_payload or b""

        result = self._script_host_service.execute(
            ScriptExecutionRequest(
                language=bridge.script_language,
                code=bridge.script_code,
                context={
                    "payload": entry.raw_payload or b"",
                    "metadata": dict(entry.metadata),
                    "message": entry.message,
                    "transport_kind": entry.transport_kind,
                    "session_id": entry.session_id,
                },
                timeout_seconds=BRIDGE_SCRIPT_TIMEOUT_SECONDS,
            )
        )
        if not result.success:
            self._report_error(
                f"Bridge '{bridge.name}' script failed: {result.error}",
                bridge=bridge,
            )
            return None
        if result.result is None:
            return entry.raw_payload or b""
        if isinstance(result.result, (bytes, bytearray)):
            return bytes(result.result)
        if isinstance(result.result, str):
            return result.result.encode("utf-8")
        self._report_error(
            f"Bridge '{bridge.name}' script result must be bytes, str, or None.",
            bridge=bridge,
        )
        return None

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _report_error(self, message: str, *, bridge: ChannelBridgeConfig) -> None:
        self._publish_error_log(message, bridge=bridge)
        self._set_snapshot(last_error=message)

    def _publish_error_log(self, message: str, *, bridge: ChannelBridgeConfig) -> None:
        self._event_bus.publish(
            create_log_entry(
                level=LogLevel.ERROR,
                category="automation.channel_bridge.error",
                message=message,
                transport_kind=bridge.target_transport_kind.value,
                metadata={
                    "bridge_name": bridge.name,
                    "source_transport_kind": bridge.source_transport_kind.value,
                    "target_transport_kind": bridge.target_transport_kind.value,
                },
            )
        )

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)


def _target_active_session_id(target: object) -> str | None:
    snapshot = getattr(target, "snapshot", None)
    session_id = getattr(snapshot, "active_session_id", None)
    return session_id if isinstance(session_id, str) and session_id else None


def _target_selected_peer(target: object) -> str | None:
    snapshot = getattr(target, "snapshot", None)
    peer = getattr(snapshot, "selected_client_peer", None)
    return peer if isinstance(peer, str) and peer else None

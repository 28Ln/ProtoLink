from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from protolink.application.script_host_service import ScriptHostService
from protolink.core.channel_bridge import ChannelBridgeConfig
from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.script_host import ScriptExecutionRequest
from protolink.core.transport import TransportKind


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
    last_bridge_at: datetime | None = None
    last_error: str | None = None


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

        for bridge in self._bridges:
            if not bridge.enabled or bridge.source_transport_kind != source_kind:
                continue
            if bridge.source_transport_kind == bridge.target_transport_kind:
                self._set_snapshot(last_error=f"Bridge '{bridge.name}' cannot bridge a transport kind to itself.")
                continue

            target = self._targets.get(bridge.target_transport_kind)
            if target is None or not hasattr(target, "is_connected") or not target.is_connected():
                continue

            transformed = self._transform_payload(bridge, entry)
            if transformed is None:
                continue

            try:
                target.send_replay_payload(
                    transformed,
                    {
                        "source": "channel_bridge",
                        "bridge_name": bridge.name,
                        "source_transport_kind": bridge.source_transport_kind.value,
                        "target_transport_kind": bridge.target_transport_kind.value,
                    },
                )
            except Exception as exc:
                self._set_snapshot(last_error=f"Bridge '{bridge.name}' send failed: {exc}")
                continue

            self._set_snapshot(
                bridged_count=self._snapshot.bridged_count + 1,
                last_bridge_name=bridge.name,
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
            )
        )
        if not result.success:
            self._set_snapshot(last_error=f"Bridge '{bridge.name}' script failed: {result.error}")
            return None
        if result.result is None:
            return entry.raw_payload or b""
        if isinstance(result.result, (bytes, bytearray)):
            return bytes(result.result)
        if isinstance(result.result, str):
            return result.result.encode("utf-8")
        self._set_snapshot(last_error=f"Bridge '{bridge.name}' script result must be bytes, str, or None.")
        return None

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)

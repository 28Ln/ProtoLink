from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from protolink.core.auto_response import AutoResponseRule, select_auto_response_action
from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.transport import TransportKind


class AutoResponseTarget(Protocol):
    def is_connected(self) -> bool:
        ...

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        ...


@dataclass(frozen=True, slots=True)
class AutoResponseRuntimeSnapshot:
    enabled: bool = True
    rule_count: int = 0
    matched_count: int = 0
    last_rule_name: str | None = None
    last_action_at: datetime | None = None
    last_error: str | None = None


class AutoResponseRuntimeService:
    def __init__(self, event_bus: EventBus, targets: Mapping[TransportKind, object]) -> None:
        self._event_bus = event_bus
        self._targets = dict(targets)
        self._rules: tuple[AutoResponseRule, ...] = ()
        self._snapshot = AutoResponseRuntimeSnapshot()
        self._listeners: list[Callable[[AutoResponseRuntimeSnapshot], None]] = []
        self._event_bus.subscribe(StructuredLogEntry, self._on_log_entry)

    @property
    def snapshot(self) -> AutoResponseRuntimeSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[AutoResponseRuntimeSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_enabled(self, enabled: bool) -> None:
        self._set_snapshot(enabled=enabled, last_error=None)

    def set_rules(self, rules: tuple[AutoResponseRule, ...]) -> None:
        self._rules = tuple(rules)
        self._set_snapshot(rule_count=len(self._rules), last_error=None)

    def clear_rules(self) -> None:
        self.set_rules(())

    def _on_log_entry(self, entry: StructuredLogEntry) -> None:
        if not self._snapshot.enabled:
            return
        if entry.category != "transport.message" or not entry.raw_payload:
            return
        if not entry.message.lower().startswith("inbound "):
            return
        if not entry.transport_kind:
            return

        try:
            transport_kind = TransportKind(entry.transport_kind)
        except ValueError:
            return

        target = self._targets.get(transport_kind)
        if target is None:
            return
        if not hasattr(target, "is_connected") or not target.is_connected():
            return
        if not hasattr(target, "send_replay_payload"):
            return

        action = select_auto_response_action(self._rules, entry.raw_payload)
        if action is None:
            return

        try:
            target.send_replay_payload(
                action.response_payload,
                {
                    "source": "auto_response",
                    "rule_name": action.rule_name,
                    "protocol": action.protocol.value,
                },
            )
        except Exception as exc:
            self._set_snapshot(last_error=f"Auto response send failed: {exc}")
            return

        self._set_snapshot(
            matched_count=self._snapshot.matched_count + 1,
            last_rule_name=action.rule_name,
            last_action_at=datetime.now(UTC),
            last_error=None,
        )

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)

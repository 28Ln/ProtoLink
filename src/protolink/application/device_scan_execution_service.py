from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from protolink.core.device_scan import (
    DeviceScanConfig,
    DeviceScanOutcome,
    DeviceScanSummary,
    DeviceScanTransportKind,
    build_device_scan_requests,
    build_device_scan_summary,
    evaluate_device_scan_response,
)
from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.transport import TransportKind


class DeviceScanTarget(Protocol):
    def is_connected(self) -> bool:
        ...

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        ...


@dataclass(frozen=True, slots=True)
class DeviceScanExecutionSnapshot:
    running: bool = False
    transport_kind: DeviceScanTransportKind | None = None
    target_transport_kind: TransportKind | None = None
    target_session_id: str | None = None
    target_peer: str | None = None
    total_requests: int = 0
    dispatched_requests: int = 0
    pending_unit_ids: tuple[int, ...] = ()
    discovered_unit_ids: tuple[int, ...] = ()
    exception_unit_ids: tuple[int, ...] = ()
    last_error: str | None = None
    last_summary: DeviceScanSummary | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DeviceScanExecutionService:
    def __init__(self, event_bus: EventBus, targets: Mapping[TransportKind, object]) -> None:
        self._event_bus = event_bus
        self._targets = dict(targets)
        self._listeners: list[Callable[[DeviceScanExecutionSnapshot], None]] = []
        self._snapshot = DeviceScanExecutionSnapshot()
        self._active_config: DeviceScanConfig | None = None
        self._active_target_kind: TransportKind | None = None
        self._active_target_session_id: str | None = None
        self._active_target_peer: str | None = None
        self._outcomes_by_unit: dict[int, DeviceScanOutcome] = {}
        self._event_bus.subscribe(StructuredLogEntry, self._on_log_entry)

    @property
    def snapshot(self) -> DeviceScanExecutionSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[DeviceScanExecutionSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def execute_scan(self, config: DeviceScanConfig, target_transport_kind: TransportKind) -> None:
        target = self._targets.get(target_transport_kind)
        if target is None:
            self._set_snapshot(last_error=f"设备扫描目标“{target_transport_kind.value}”未注册。")
            return
        if not hasattr(target, "is_connected") or not target.is_connected():
            self._set_snapshot(last_error=f"设备扫描目标“{target_transport_kind.value}”未连接。")
            return

        requests = build_device_scan_requests(config)
        if not requests:
            self._set_snapshot(last_error="设备扫描请求集为空。")
            return

        self._active_config = config
        self._active_target_kind = target_transport_kind
        self._active_target_session_id = _target_active_session_id(target)
        self._active_target_peer = _target_selected_peer(target)
        self._outcomes_by_unit.clear()
        started_at = datetime.now(UTC)
        self._set_snapshot(
            running=True,
            transport_kind=config.transport_kind,
            target_transport_kind=target_transport_kind,
            target_session_id=self._active_target_session_id,
            target_peer=self._active_target_peer,
            total_requests=len(requests),
            dispatched_requests=0,
            pending_unit_ids=tuple(request.unit_id for request in requests),
            discovered_unit_ids=(),
            exception_unit_ids=(),
            last_error=None,
            last_summary=None,
            started_at=started_at,
            finished_at=None,
        )

        dispatched = 0
        try:
            for request in requests:
                target.send_replay_payload(
                    request.payload,
                    {
                        **request.metadata,
                        "source": "device_scan",
                        "scan_transport_kind": config.transport_kind.value,
                    },
                )
                dispatched += 1
                self._set_snapshot(dispatched_requests=dispatched)
        except Exception as exc:
            self._set_snapshot(running=False, last_error=f"设备扫描下发失败：{exc}")

    def finalize_current_scan(self) -> DeviceScanSummary | None:
        config = self._active_config
        if config is None:
            self._set_snapshot(last_error="当前没有正在执行的设备扫描。")
            return None

        summary = build_device_scan_summary(config, tuple(self._outcomes_by_unit.values()))
        finished_at = datetime.now(UTC)
        self._set_snapshot(
            running=False,
            pending_unit_ids=summary.missing_units,
            discovered_unit_ids=summary.discovered_units,
            exception_unit_ids=summary.exception_units,
            last_summary=summary,
            last_error=None if not summary.errors else summary.errors[-1],
            finished_at=finished_at,
        )
        return summary

    def _on_log_entry(self, entry: StructuredLogEntry) -> None:
        if not self._snapshot.running:
            return
        if entry.category != "transport.message" or not entry.raw_payload:
            return
        if not _is_inbound_entry(entry):
            return
        if self._active_config is None or self._active_target_kind is None:
            return
        if entry.transport_kind != self._active_target_kind.value:
            return
        if self._active_target_session_id and entry.session_id != self._active_target_session_id:
            return
        if self._active_target_peer and entry.metadata.get("peer") != self._active_target_peer:
            return

        outcome = self._match_outcome(entry.raw_payload)
        if outcome is None:
            return
        if outcome.unit_id in self._outcomes_by_unit:
            return

        self._outcomes_by_unit[outcome.unit_id] = outcome
        self._set_snapshot(
            pending_unit_ids=tuple(
                unit_id for unit_id in self._snapshot.pending_unit_ids if unit_id != outcome.unit_id
            ),
            discovered_unit_ids=tuple(sorted(unit.unit_id for unit in self._outcomes_by_unit.values() if unit.reachable)),
            exception_unit_ids=tuple(
                sorted(unit.unit_id for unit in self._outcomes_by_unit.values() if unit.exception_code is not None)
            ),
            last_error=outcome.error if outcome.error else self._snapshot.last_error,
        )

    def _match_outcome(self, payload: bytes) -> DeviceScanOutcome | None:
        if self._active_config is None:
            return None
        for unit_id in self._snapshot.pending_unit_ids:
            outcome = evaluate_device_scan_response(
                self._active_config.transport_kind,
                expected_unit_id=unit_id,
                payload=payload,
            )
            if outcome.reachable or outcome.exception_code is not None:
                return outcome
        return None

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

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


def _is_inbound_entry(entry: StructuredLogEntry) -> bool:
    direction = str(entry.metadata.get("direction", "")).lower()
    if direction:
        return direction == "inbound"
    message = entry.message.lower()
    return message.startswith("inbound ") or message.startswith("入站")

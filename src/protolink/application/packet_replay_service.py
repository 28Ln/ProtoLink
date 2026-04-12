from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from protolink.application.runtime import AsyncTaskRunner
from protolink.core.packet_replay import PacketReplayPlan, PacketReplayStep, load_packet_replay_plan
from protolink.core.transport import TransportKind


class ReplayDispatchTarget(Protocol):
    def is_connected(self) -> bool:
        ...

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        ...


@dataclass(frozen=True, slots=True)
class PacketReplayExecutionSnapshot:
    running: bool = False
    plan_name: str | None = None
    target_kind: TransportKind | None = None
    target_session_id: str | None = None
    target_peer: str | None = None
    total_steps: int = 0
    dispatched_steps: int = 0
    skipped_steps: int = 0
    last_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PacketReplayExecutionService:
    def __init__(self, targets: Mapping[TransportKind, ReplayDispatchTarget]) -> None:
        self._targets = dict(targets)
        self._runtime: AsyncTaskRunner | None = None
        self._dispatch_scheduler: Callable[[Callable[[], None]], None] | None = None
        self._listeners: list[Callable[[PacketReplayExecutionSnapshot], None]] = []
        self._snapshot = PacketReplayExecutionSnapshot()
        self._active_future: Future[None] | None = None

    @property
    def snapshot(self) -> PacketReplayExecutionSnapshot:
        return self._snapshot

    def subscribe(
        self,
        listener: Callable[[PacketReplayExecutionSnapshot], None],
    ) -> Callable[[], None]:
        self._listeners.append(listener)
        self._dispatch(lambda: listener(self._snapshot))

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_dispatch_scheduler(self, scheduler: Callable[[Callable[[], None]], None] | None) -> None:
        self._dispatch_scheduler = scheduler

    def execute_plan(self, plan: PacketReplayPlan, target_kind: TransportKind) -> None:
        if self._snapshot.running:
            self._set_snapshot(last_error="A replay job is already running.")
            return

        target = self._targets.get(target_kind)
        if target is None:
            self._set_snapshot(last_error=f"Replay target '{target_kind.value}' is not registered.")
            return
        if not target.is_connected():
            self._set_snapshot(last_error=f"Replay target '{target_kind.value}' is not connected.")
            return

        target_steps = self._select_target_steps(plan, target_kind)
        if not target_steps:
            self._set_snapshot(
                last_error=f"No replay steps matched target '{target_kind.value}' in plan '{plan.name}'.",
            )
            return

        started_at = datetime.now(UTC)
        target_session_id = _target_active_session_id(target)
        target_peer = _target_selected_peer(target)
        self._set_snapshot(
            running=True,
            plan_name=plan.name,
            target_kind=target_kind,
            target_session_id=target_session_id,
            target_peer=target_peer,
            total_steps=len(target_steps),
            dispatched_steps=0,
            skipped_steps=max(len(plan.steps) - len(target_steps), 0),
            last_error=None,
            started_at=started_at,
            finished_at=None,
        )
        future = self._ensure_runtime().submit(self._execute_steps(target, target_kind, plan.name, target_steps))
        self._active_future = future
        future.add_done_callback(self._handle_execute_result)

    def execute_saved_plan(self, path: Path | str, target_kind: TransportKind) -> None:
        plan = load_packet_replay_plan(Path(path))
        self.execute_plan(plan, target_kind)

    def shutdown(self) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        runtime.shutdown()
        self._runtime = None

    def _select_target_steps(
        self,
        plan: PacketReplayPlan,
        target_kind: TransportKind,
    ) -> tuple[PacketReplayStep, ...]:
        return tuple(
            step for step in plan.steps if step.transport_kind is None or step.transport_kind == target_kind.value
        )

    async def _execute_steps(
        self,
        target: ReplayDispatchTarget,
        target_kind: TransportKind,
        plan_name: str,
        steps: tuple[PacketReplayStep, ...],
    ) -> None:
        for index, step in enumerate(steps, start=1):
            if step.delay_ms > 0:
                await asyncio.sleep(step.delay_ms / 1000)
            current_target_session_id = _target_active_session_id(target)
            if current_target_session_id != self._snapshot.target_session_id:
                if current_target_session_id is not None or self._snapshot.target_session_id is not None:
                    raise RuntimeError("Replay target session changed during execution.")
            current_target_peer = _target_selected_peer(target)
            if current_target_peer != self._snapshot.target_peer:
                if current_target_peer is not None or self._snapshot.target_peer is not None:
                    raise RuntimeError("Replay target peer changed during execution.")

            metadata = {
                **dict(step.metadata),
                "source": "packet_replay",
                "replay_plan": plan_name,
                "replay_target": target_kind.value,
                "replay_step": str(index),
                "replay_direction": step.direction.value,
                "replay_delay_ms": str(step.delay_ms),
            }
            if step.session_id:
                metadata.setdefault("source_session_id", step.session_id)
            if step.transport_kind:
                metadata.setdefault("source_transport_kind", step.transport_kind)
            if self._snapshot.target_session_id:
                metadata.setdefault("replay_target_session_id", self._snapshot.target_session_id)
            if self._snapshot.target_peer:
                metadata.setdefault("replay_target_peer", self._snapshot.target_peer)

            target.send_replay_payload(step.payload, metadata)
            self._set_snapshot(dispatched_steps=index)

    def _handle_execute_result(self, future: Future[None]) -> None:
        try:
            future.result()
        except Exception as exc:
            self._set_snapshot(
                running=False,
                last_error=f"Replay execution failed: {exc}",
                finished_at=datetime.now(UTC),
            )
            return
        self._set_snapshot(
            running=False,
            last_error=None,
            finished_at=datetime.now(UTC),
        )

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            self._dispatch(lambda listener=listener, snapshot=snapshot: listener(snapshot))

    def _dispatch(self, callback: Callable[[], None]) -> None:
        if self._dispatch_scheduler is None:
            callback()
            return
        self._dispatch_scheduler(callback)

    def _ensure_runtime(self) -> AsyncTaskRunner:
        if self._runtime is None:
            self._runtime = AsyncTaskRunner()
        return self._runtime


def _target_active_session_id(target: object) -> str | None:
    snapshot = getattr(target, "snapshot", None)
    session_id = getattr(snapshot, "active_session_id", None)
    return session_id if isinstance(session_id, str) and session_id else None


def _target_selected_peer(target: object) -> str | None:
    snapshot = getattr(target, "snapshot", None)
    peer = getattr(snapshot, "selected_client_peer", None)
    return peer if isinstance(peer, str) and peer else None

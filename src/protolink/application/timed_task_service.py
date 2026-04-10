from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from protolink.application.rule_engine_service import RuleEngineService
from protolink.core.timed_tasks import TimedTask


@dataclass(frozen=True, slots=True)
class TimedTaskSnapshot:
    running: bool = False
    task_names: tuple[str, ...] = ()
    execution_count: int = 0
    last_run_task_name: str | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None


class TimedTaskService:
    def __init__(self, rule_engine_service: RuleEngineService, *, poll_interval_seconds: float = 0.05) -> None:
        self._rule_engine_service = rule_engine_service
        self._poll_interval_seconds = poll_interval_seconds
        self._tasks_by_name: dict[str, TimedTask] = {}
        self._next_run_monotonic: dict[str, float] = {}
        self._listeners: list[Callable[[TimedTaskSnapshot], None]] = []
        self._snapshot = TimedTaskSnapshot()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def snapshot(self) -> TimedTaskSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[TimedTaskSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_tasks(self, tasks: tuple[TimedTask, ...]) -> None:
        self._tasks_by_name = {task.name: task for task in tasks}
        now = time.monotonic()
        self._next_run_monotonic = {
            task.name: now + max(task.interval_seconds, self._poll_interval_seconds)
            for task in tasks
            if task.enabled
        }
        self._set_snapshot(task_names=tuple(sorted(self._tasks_by_name)), last_error=None)

    def upsert_task(self, task: TimedTask) -> None:
        self._tasks_by_name[task.name] = task
        if task.enabled:
            self._next_run_monotonic[task.name] = time.monotonic() + max(task.interval_seconds, self._poll_interval_seconds)
        else:
            self._next_run_monotonic.pop(task.name, None)
        self._set_snapshot(task_names=tuple(sorted(self._tasks_by_name)), last_error=None)

    def remove_task(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(last_error="Select a timed task before removing.")
            return
        removed = self._tasks_by_name.pop(name, None)
        self._next_run_monotonic.pop(name, None)
        if removed is None:
            self._set_snapshot(last_error=f"Timed task '{name}' was not found.")
            return
        self._set_snapshot(task_names=tuple(sorted(self._tasks_by_name)), last_error=None)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ProtoLinkTimedTaskService", daemon=True)
        self._thread.start()
        self._set_snapshot(running=True, last_error=None)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._set_snapshot(running=False)

    def shutdown(self) -> None:
        self.stop()

    def tick(self, now_monotonic: float | None = None) -> None:
        now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
        for task_name, task in tuple(self._tasks_by_name.items()):
            if not task.enabled:
                continue
            next_run = self._next_run_monotonic.get(task_name)
            if next_run is None or now_monotonic < next_run:
                continue
            result = self._rule_engine_service.run_rule(task.rule_name)
            if result is None:
                self._set_snapshot(last_error=self._rule_engine_service.snapshot.last_error)
            else:
                self._set_snapshot(
                    execution_count=self._snapshot.execution_count + 1,
                    last_run_task_name=task.name,
                    last_run_at=datetime.now(UTC),
                    last_error=None,
                )
            self._next_run_monotonic[task_name] = now_monotonic + max(task.interval_seconds, self._poll_interval_seconds)

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self._poll_interval_seconds):
            self.tick()

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)

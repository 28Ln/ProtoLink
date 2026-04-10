from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from protolink.application.packet_replay_service import PacketReplayExecutionService, PacketReplayExecutionSnapshot
from protolink.core.capture_replay_jobs import CaptureReplayJob


@dataclass(frozen=True, slots=True)
class CaptureReplayJobSnapshot:
    job_names: tuple[str, ...] = ()
    enabled_job_names: tuple[str, ...] = ()
    running: bool = False
    active_job_name: str | None = None
    completed_runs: int = 0
    last_run_at: datetime | None = None
    last_error: str | None = None


class CaptureReplayJobService:
    def __init__(self, packet_replay_service: PacketReplayExecutionService) -> None:
        self._packet_replay_service = packet_replay_service
        self._jobs_by_name: dict[str, CaptureReplayJob] = {}
        self._listeners: list[Callable[[CaptureReplayJobSnapshot], None]] = []
        self._snapshot = CaptureReplayJobSnapshot()
        self._active_job: CaptureReplayJob | None = None
        self._remaining_runs = 0
        self._packet_replay_service.subscribe(self._on_replay_snapshot)

    @property
    def snapshot(self) -> CaptureReplayJobSnapshot:
        return self._snapshot

    @property
    def jobs(self) -> tuple[CaptureReplayJob, ...]:
        return tuple(self._jobs_by_name[name] for name in sorted(self._jobs_by_name))

    def subscribe(self, listener: Callable[[CaptureReplayJobSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_jobs(self, jobs: tuple[CaptureReplayJob, ...]) -> None:
        self._jobs_by_name = {job.name: job for job in jobs}
        self._set_snapshot(
            job_names=tuple(sorted(self._jobs_by_name)),
            enabled_job_names=tuple(sorted(job.name for job in jobs if job.enabled)),
            last_error=None,
        )

    def upsert_job(self, job: CaptureReplayJob) -> None:
        self._jobs_by_name[job.name] = job
        self._set_snapshot(
            job_names=tuple(sorted(self._jobs_by_name)),
            enabled_job_names=tuple(sorted(name for name, item in self._jobs_by_name.items() if item.enabled)),
            last_error=None,
        )

    def remove_job(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(last_error="Select a replay job before removing.")
            return
        removed = self._jobs_by_name.pop(name, None)
        if removed is None:
            self._set_snapshot(last_error=f"Replay job '{name}' was not found.")
            return
        self._set_snapshot(
            job_names=tuple(sorted(self._jobs_by_name)),
            enabled_job_names=tuple(sorted(job_name for job_name, item in self._jobs_by_name.items() if item.enabled)),
            last_error=None,
        )

    def run_job(self, name: str) -> None:
        job = self._jobs_by_name.get(name)
        if job is None:
            self._set_snapshot(last_error=f"Replay job '{name}' was not found.")
            return
        if not job.enabled:
            self._set_snapshot(last_error=f"Replay job '{name}' is disabled.")
            return
        if self._snapshot.running:
            self._set_snapshot(last_error="A capture/replay job is already running.")
            return
        if not Path(job.replay_plan_path).exists():
            self._set_snapshot(last_error=f"Replay plan '{job.replay_plan_path}' was not found.")
            return

        self._active_job = job
        self._remaining_runs = max(int(job.repeat_count), 1)
        self._set_snapshot(
            running=True,
            active_job_name=job.name,
            last_error=None,
        )
        self._start_next_run()

    def _start_next_run(self) -> None:
        if self._active_job is None:
            return
        self._packet_replay_service.execute_saved_plan(
            self._active_job.replay_plan_path,
            self._active_job.target_transport_kind,
        )

    def _on_replay_snapshot(self, snapshot: PacketReplayExecutionSnapshot) -> None:
        if self._active_job is None:
            return
        if snapshot.running:
            return
        if snapshot.last_error:
            self._set_snapshot(
                running=False,
                active_job_name=None,
                last_error=snapshot.last_error,
            )
            self._active_job = None
            self._remaining_runs = 0
            return

        self._remaining_runs -= 1
        self._set_snapshot(
            completed_runs=self._snapshot.completed_runs + 1,
            last_run_at=datetime.now(UTC),
        )
        if self._remaining_runs > 0:
            self._start_next_run()
            return

        self._set_snapshot(
            running=False,
            active_job_name=None,
            last_error=None,
        )
        self._active_job = None

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)

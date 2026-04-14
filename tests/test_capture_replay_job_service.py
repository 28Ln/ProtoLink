from dataclasses import dataclass
from pathlib import Path

from protolink.application.capture_replay_job_service import CaptureReplayJobService
from protolink.core.capture_replay_jobs import CaptureReplayJob
from protolink.core.transport import TransportKind


@dataclass
class _ReplaySnapshot:
    running: bool = False
    last_error: str | None = None


class _ReplayServiceStub:
    def __init__(self) -> None:
        self.snapshot = _ReplaySnapshot()
        self.calls: list[tuple[str, TransportKind]] = []
        self._listeners = []

    def subscribe(self, listener):
        self._listeners.append(listener)
        listener(self.snapshot)
        return lambda: None

    def execute_saved_plan(self, path: Path | str, target_kind: TransportKind) -> None:
        self.calls.append((str(path), target_kind))
        self.snapshot = _ReplaySnapshot(running=True)
        for listener in list(self._listeners):
            listener(self.snapshot)
        self.snapshot = _ReplaySnapshot(running=False, last_error=None)
        for listener in list(self._listeners):
            listener(self.snapshot)


class _FailingReplayServiceStub(_ReplayServiceStub):
    def execute_saved_plan(self, path: Path | str, target_kind: TransportKind) -> None:
        self.calls.append((str(path), target_kind))
        self.snapshot = _ReplaySnapshot(running=False, last_error="回放执行失败：boom")
        for listener in list(self._listeners):
            listener(self.snapshot)


def test_capture_replay_job_service_runs_and_repeats_jobs(tmp_path: Path) -> None:
    replay_service = _ReplayServiceStub()
    service = CaptureReplayJobService(replay_service)  # type: ignore[arg-type]
    replay_path = tmp_path / "demo.json"
    replay_path.write_text("{}", encoding="utf-8")
    service.upsert_job(
        CaptureReplayJob(
            name="Bench Replay",
            replay_plan_path=str(replay_path),
            target_transport_kind=TransportKind.TCP_CLIENT,
            repeat_count=2,
        )
    )

    service.run_job("Bench Replay")

    assert replay_service.calls == [
        (str(replay_path), TransportKind.TCP_CLIENT),
        (str(replay_path), TransportKind.TCP_CLIENT),
    ]
    assert service.snapshot.running is False
    assert service.snapshot.completed_runs == 2


def test_capture_replay_job_service_surfaces_missing_and_failed_jobs(tmp_path: Path) -> None:
    replay_service = _FailingReplayServiceStub()
    service = CaptureReplayJobService(replay_service)  # type: ignore[arg-type]

    service.run_job("Missing")
    assert service.snapshot.last_error == "未找到回放任务“Missing”。"

    replay_path = tmp_path / "demo.json"
    replay_path.write_text("{}", encoding="utf-8")
    service.upsert_job(
        CaptureReplayJob(
            name="Broken Replay",
            replay_plan_path=str(replay_path),
            target_transport_kind=TransportKind.UDP,
        )
    )
    service.run_job("Broken Replay")

    assert replay_service.calls == [(str(replay_path), TransportKind.UDP)]
    assert service.snapshot.last_error == "回放执行失败：boom"

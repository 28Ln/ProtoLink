import time

from protolink.application.timed_task_service import TimedTaskService
from protolink.core.rule_engine import AutomationRule
from protolink.core.timed_tasks import TimedTask


class _RuleEngineStub:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.snapshot = type("Snapshot", (), {"last_error": None})()

    def run_rule(self, name: str):
        self.calls.append(name)
        return type("RunResult", (), {"rule_name": name})()


class _FailingRuleEngineStub:
    def __init__(self) -> None:
        self.snapshot = type("Snapshot", (), {"last_error": "boom"})()

    def run_rule(self, name: str):
        return None


def test_timed_task_service_runs_due_rules_and_tracks_state() -> None:
    engine = _RuleEngineStub()
    service = TimedTaskService(engine, poll_interval_seconds=0.02)
    service.set_tasks((TimedTask(name="Heartbeat", rule_name="Ping Rule", interval_seconds=0.02),))

    service.start()
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and not engine.calls:
        time.sleep(0.02)
    service.stop()

    assert engine.calls
    assert engine.calls[0] == "Ping Rule"
    assert service.snapshot.execution_count >= 1
    assert service.snapshot.last_run_task_name == "Heartbeat"
    assert service.snapshot.running is False


def test_timed_task_service_surfaces_rule_failures() -> None:
    engine = _FailingRuleEngineStub()
    service = TimedTaskService(engine, poll_interval_seconds=0.01)
    service.set_tasks((TimedTask(name="Broken", rule_name="Missing", interval_seconds=0.01),))

    service.tick(now_monotonic=time.monotonic() + 1.0)

    assert service.snapshot.last_error == "boom"

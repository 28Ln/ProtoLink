from dataclasses import dataclass
from pathlib import Path

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.application.rule_engine_service import RuleEngineService
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.rule_engine import AutomationAction, AutomationActionKind, AutomationRule
from protolink.core.transport import TransportKind


@dataclass
class _ReplaySnapshot:
    running: bool = False


class _ReplayServiceStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, TransportKind]] = []
        self.snapshot = _ReplaySnapshot()

    def execute_saved_plan(self, path: Path | str, target_kind: TransportKind) -> None:
        self.calls.append((str(path), target_kind))


def test_rule_engine_service_runs_replay_and_auto_response_actions(tmp_path: Path) -> None:
    replay = _ReplayServiceStub()
    auto_response = AutoResponseRuntimeService(EventBus(), {})
    service = RuleEngineService(
        packet_replay_service=replay,  # type: ignore[arg-type]
        auto_response_runtime_service=auto_response,
    )
    plan_path = tmp_path / "bench-replay.json"
    plan_path.write_text("{}", encoding="utf-8")
    rule = AutomationRule(
        name="Replay + AutoResponse",
        actions=(
            AutomationAction(
                kind=AutomationActionKind.SET_AUTO_RESPONSE_ENABLED,
                auto_response_enabled=True,
            ),
            AutomationAction(
                kind=AutomationActionKind.LOAD_AUTO_RESPONSE_RULES,
                auto_response_rules=(
                    AutoResponseRule(
                        name="Raw Ping",
                        protocol=AutoResponseProtocol.RAW_BYTES,
                        raw_match_payload=b"PING",
                        response_payload=b"PONG",
                    ),
                ),
            ),
            AutomationAction(
                kind=AutomationActionKind.RUN_REPLAY_PLAN,
                replay_plan_path=str(plan_path),
                replay_target_kind=TransportKind.TCP_CLIENT,
            ),
        ),
    )
    service.set_rules((rule,))

    result = service.run_rule("Replay + AutoResponse")

    assert result is not None
    assert result.executed_action_count == 3
    assert replay.calls == [(str(plan_path), TransportKind.TCP_CLIENT)]
    assert auto_response.snapshot.enabled is True
    assert auto_response.snapshot.rule_count == 1
    assert service.snapshot.last_run_rule_name == "Replay + AutoResponse"
    assert service.snapshot.execution_count == 1
    assert service.execution_history[-1].succeeded is True


def test_rule_engine_service_prepares_device_scan_jobs() -> None:
    replay = _ReplayServiceStub()
    auto_response = AutoResponseRuntimeService(EventBus(), {})
    service = RuleEngineService(
        packet_replay_service=replay,  # type: ignore[arg-type]
        auto_response_runtime_service=auto_response,
    )
    scan_config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_TCP,
        target="127.0.0.1:502",
        unit_id_start=1,
        unit_id_end=3,
    )
    service.set_rules(
        (
            AutomationRule(
                name="Prepare Scan",
                actions=(
                    AutomationAction(
                        kind=AutomationActionKind.PREPARE_DEVICE_SCAN,
                        device_scan_config=scan_config,
                    ),
                ),
            ),
        )
    )

    result = service.run_rule("Prepare Scan")

    assert result is not None
    assert len(result.prepared_device_scan_jobs) == 1
    assert result.prepared_device_scan_jobs[0].request_count == 3
    assert service.snapshot.prepared_device_scan_job_count == 1


def test_rule_engine_service_reports_missing_or_disabled_rules() -> None:
    replay = _ReplayServiceStub()
    auto_response = AutoResponseRuntimeService(EventBus(), {})
    service = RuleEngineService(
        packet_replay_service=replay,  # type: ignore[arg-type]
        auto_response_runtime_service=auto_response,
    )
    service.set_rules((AutomationRule(name="Disabled", enabled=False),))

    missing = service.run_rule("Missing")
    assert missing is None
    assert service.snapshot.last_error == "未找到规则“Missing”。"

    disabled = service.run_rule("Disabled")
    assert disabled is None
    assert service.snapshot.last_error == "规则“Disabled”已停用。"
    assert service.snapshot.execution_count == 2
    assert service.execution_history[-1].error == "规则“Disabled”已停用。"


def test_rule_engine_service_blocks_replay_conflicts() -> None:
    replay = _ReplayServiceStub()
    replay.snapshot.running = True
    auto_response = AutoResponseRuntimeService(EventBus(), {})
    service = RuleEngineService(
        packet_replay_service=replay,  # type: ignore[arg-type]
        auto_response_runtime_service=auto_response,
    )
    service.set_rules(
        (
            AutomationRule(
                name="Replay Conflict",
                actions=(
                    AutomationAction(
                        kind=AutomationActionKind.RUN_REPLAY_PLAN,
                        replay_plan_path="C:/tmp/demo.json",
                        replay_target_kind=TransportKind.TCP_CLIENT,
                    ),
                ),
            ),
        )
    )

    result = service.run_rule("Replay Conflict")

    assert result is None
    assert replay.calls == []
    assert service.snapshot.last_error == "规则“Replay Conflict”执行失败：回放服务已在运行中。"
    assert service.execution_history[-1].succeeded is False


def test_rule_engine_service_persists_rules_across_bootstrap_contexts(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    context.rule_engine_service.upsert_rule(
        AutomationRule(
            name="Persisted Rule",
            actions=(
                AutomationAction(
                    kind=AutomationActionKind.SET_AUTO_RESPONSE_ENABLED,
                    auto_response_enabled=True,
                ),
            ),
        )
    )

    reloaded = bootstrap_app_context(tmp_path, persist_settings=False)

    assert reloaded.rule_engine_service.snapshot.rule_names == ("Persisted Rule",)


def test_rule_engine_service_logs_missing_and_failed_rules() -> None:
    event_bus = EventBus()
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    replay = _ReplayServiceStub()
    replay.snapshot.running = True
    auto_response = AutoResponseRuntimeService(EventBus(), {})
    service = RuleEngineService(
        packet_replay_service=replay,  # type: ignore[arg-type]
        auto_response_runtime_service=auto_response,
        event_bus=event_bus,
    )
    service.set_rules(
        (
            AutomationRule(
                name="Replay Conflict",
                actions=(
                    AutomationAction(
                        kind=AutomationActionKind.RUN_REPLAY_PLAN,
                        replay_plan_path="C:/tmp/demo.json",
                        replay_target_kind=TransportKind.TCP_CLIENT,
                    ),
                ),
            ),
        )
    )

    assert service.run_rule("Missing") is None
    assert service.run_rule("Replay Conflict") is None

    error_entries = [entry for entry in captured if entry.category == "automation.rule_engine.error"]
    assert [entry.message for entry in error_entries] == [
        "未找到规则“Missing”。",
        "规则“Replay Conflict”执行失败：回放服务已在运行中。",
    ]
    assert error_entries[0].metadata == {"rule_name": "Missing"}
    assert error_entries[1].metadata == {"rule_name": "Replay Conflict"}

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from protolink.application.auto_response_runtime_service import AutoResponseRuntimeService
from protolink.application.packet_replay_service import PacketReplayExecutionService
from protolink.core.automation_rule_profiles import (
    AutomationRulesProfile,
    load_automation_rules_profile,
    save_automation_rules_profile,
)
from protolink.core.device_scan import build_device_scan_requests
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.rule_engine import (
    AutomationAction,
    AutomationActionKind,
    AutomationRule,
    AutomationRunResult,
    PreparedDeviceScanJob,
    RuleExecutionRecord,
)


@dataclass(frozen=True, slots=True)
class RuleEngineSnapshot:
    rule_names: tuple[str, ...] = ()
    enabled_rule_names: tuple[str, ...] = ()
    prepared_device_scan_job_count: int = 0
    execution_count: int = 0
    last_run_rule_name: str | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None


class RuleEngineService:
    def __init__(
        self,
        *,
        packet_replay_service: PacketReplayExecutionService,
        auto_response_runtime_service: AutoResponseRuntimeService,
        profile_path: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._packet_replay_service = packet_replay_service
        self._auto_response_runtime_service = auto_response_runtime_service
        self._profile_path = profile_path
        self._event_bus = event_bus
        self._rules_by_name: dict[str, AutomationRule] = {}
        self._prepared_device_scan_jobs: list[PreparedDeviceScanJob] = []
        self._execution_history: list[RuleExecutionRecord] = []
        self._listeners: list[Callable[[RuleEngineSnapshot], None]] = []
        self._snapshot = RuleEngineSnapshot()
        self._load_rules()

    @property
    def snapshot(self) -> RuleEngineSnapshot:
        return self._snapshot

    @property
    def prepared_device_scan_jobs(self) -> tuple[PreparedDeviceScanJob, ...]:
        return tuple(self._prepared_device_scan_jobs)

    @property
    def execution_history(self) -> tuple[RuleExecutionRecord, ...]:
        return tuple(self._execution_history)

    @property
    def rules(self) -> tuple[AutomationRule, ...]:
        return tuple(self._rules_by_name[name] for name in sorted(self._rules_by_name))

    @property
    def profile_path(self) -> Path | None:
        return self._profile_path

    def get_rule(self, name: str) -> AutomationRule | None:
        return self._rules_by_name.get(name)

    def subscribe(self, listener: Callable[[RuleEngineSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_rules(self, rules: tuple[AutomationRule, ...]) -> None:
        self._rules_by_name = {rule.name: rule for rule in rules}
        self._persist_rules()
        self._set_snapshot(
            rule_names=tuple(sorted(self._rules_by_name)),
            enabled_rule_names=tuple(sorted(rule.name for rule in rules if rule.enabled)),
            last_error=None,
        )

    def upsert_rule(self, rule: AutomationRule) -> None:
        self._rules_by_name[rule.name] = rule
        self._persist_rules()
        self._set_snapshot(
            rule_names=tuple(sorted(self._rules_by_name)),
            enabled_rule_names=tuple(sorted(name for name, item in self._rules_by_name.items() if item.enabled)),
            last_error=None,
        )

    def remove_rule(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(last_error="删除前请先选择规则。")
            return
        removed = self._rules_by_name.pop(name, None)
        if removed is None:
            self._set_snapshot(last_error=f"未找到规则“{name}”。")
            return
        self._persist_rules()
        self._set_snapshot(
            rule_names=tuple(sorted(self._rules_by_name)),
            enabled_rule_names=tuple(sorted(rule_name for rule_name, item in self._rules_by_name.items() if item.enabled)),
            last_error=None,
        )

    def clear_rules(self) -> None:
        self._rules_by_name.clear()
        self._prepared_device_scan_jobs.clear()
        self._execution_history.clear()
        self._persist_rules()
        self._set_snapshot(
            rule_names=(),
            enabled_rule_names=(),
            prepared_device_scan_job_count=0,
            execution_count=0,
            last_error=None,
        )

    def reload_rules(self) -> None:
        self._load_rules()
        self._set_snapshot(
            rule_names=tuple(sorted(self._rules_by_name)),
            enabled_rule_names=tuple(sorted(rule.name for rule in self._rules_by_name.values() if rule.enabled)),
            last_error=None,
        )

    def run_rule(self, name: str) -> AutomationRunResult | None:
        rule = self._rules_by_name.get(name)
        if rule is None:
            error_message = f"未找到规则“{name}”。"
            self._record_execution(
                RuleExecutionRecord(
                    rule_name=name,
                    succeeded=False,
                    executed_action_count=0,
                    error=error_message,
                )
            )
            self._publish_error_log(error_message, rule_name=name)
            self._set_snapshot(
                execution_count=len(self._execution_history),
                last_error=error_message,
            )
            return None
        if not rule.enabled:
            error_message = f"规则“{name}”已停用。"
            self._record_execution(
                RuleExecutionRecord(
                    rule_name=name,
                    succeeded=False,
                    executed_action_count=0,
                    error=error_message,
                )
            )
            self._publish_error_log(error_message, rule_name=name)
            self._set_snapshot(
                execution_count=len(self._execution_history),
                last_error=error_message,
            )
            return None

        prepared_jobs: list[PreparedDeviceScanJob] = []
        executed_actions = 0
        try:
            for action in rule.actions:
                self._execute_action(rule.name, action, prepared_jobs)
                executed_actions += 1
        except Exception as exc:
            self._record_execution(
                RuleExecutionRecord(
                    rule_name=rule.name,
                    succeeded=False,
                    executed_action_count=executed_actions,
                    error=str(exc),
                )
            )
            error_message = f"规则“{name}”执行失败：{exc}"
            self._publish_error_log(error_message, rule_name=rule.name)
            self._set_snapshot(
                execution_count=len(self._execution_history),
                last_error=error_message,
            )
            return None

        now = datetime.now(UTC)
        self._record_execution(
            RuleExecutionRecord(
                rule_name=rule.name,
                succeeded=True,
                executed_action_count=executed_actions,
            )
        )
        self._set_snapshot(
            prepared_device_scan_job_count=len(self._prepared_device_scan_jobs),
            execution_count=len(self._execution_history),
            last_run_rule_name=rule.name,
            last_run_at=now,
            last_error=None,
        )
        return AutomationRunResult(
            rule_name=rule.name,
            executed_action_count=executed_actions,
            prepared_device_scan_jobs=tuple(prepared_jobs),
        )

    def clear_prepared_device_scan_jobs(self) -> None:
        self._prepared_device_scan_jobs.clear()
        self._set_snapshot(prepared_device_scan_job_count=0, last_error=None)

    def _execute_action(
        self,
        rule_name: str,
        action: AutomationAction,
        prepared_jobs: list[PreparedDeviceScanJob],
    ) -> None:
        if action.kind == AutomationActionKind.RUN_REPLAY_PLAN:
            if not action.replay_plan_path or action.replay_target_kind is None:
                raise ValueError("回放动作必须提供 replay_plan_path 和 replay_target_kind。")
            replay_snapshot = getattr(self._packet_replay_service, "snapshot", None)
            if replay_snapshot is not None and getattr(replay_snapshot, "running", False):
                raise ValueError("回放服务已在运行中。")
            self._packet_replay_service.execute_saved_plan(action.replay_plan_path, action.replay_target_kind)
            return

        if action.kind == AutomationActionKind.SET_AUTO_RESPONSE_ENABLED:
            if action.auto_response_enabled is None:
                raise ValueError("自动响应开关动作必须提供 auto_response_enabled。")
            self._auto_response_runtime_service.set_enabled(action.auto_response_enabled)
            return

        if action.kind == AutomationActionKind.LOAD_AUTO_RESPONSE_RULES:
            self._auto_response_runtime_service.set_rules(action.auto_response_rules)
            return

        if action.kind == AutomationActionKind.PREPARE_DEVICE_SCAN:
            if action.device_scan_config is None:
                raise ValueError("设备扫描动作必须提供 device_scan_config。")
            requests = build_device_scan_requests(action.device_scan_config)
            job = PreparedDeviceScanJob(
                rule_name=rule_name,
                config=action.device_scan_config,
                request_count=len(requests),
            )
            self._prepared_device_scan_jobs.append(job)
            prepared_jobs.append(job)
            return

        raise ValueError(f"不支持的自动化动作类型：{action.kind}")

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _record_execution(self, record: RuleExecutionRecord) -> None:
        self._execution_history.append(record)

    def _load_rules(self) -> None:
        if self._profile_path is None:
            return
        profile = load_automation_rules_profile(self._profile_path)
        self._rules_by_name = {rule.name: rule for rule in profile.rules}
        self._snapshot = replace(
            self._snapshot,
            rule_names=tuple(sorted(self._rules_by_name)),
            enabled_rule_names=tuple(sorted(rule.name for rule in profile.rules if rule.enabled)),
        )

    def _persist_rules(self) -> None:
        if self._profile_path is None:
            return
        save_automation_rules_profile(
            self._profile_path,
            AutomationRulesProfile(rules=list(self.rules)),
        )

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)

    def _publish_error_log(self, message: str, *, rule_name: str) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            create_log_entry(
                level=LogLevel.ERROR,
                category="automation.rule_engine.error",
                message=message,
                metadata={"rule_name": rule_name},
            )
        )

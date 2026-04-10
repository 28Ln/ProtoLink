from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from protolink.core.auto_response import AutoResponseRule
from protolink.core.device_scan import DeviceScanConfig
from protolink.core.transport import TransportKind


class AutomationActionKind(StrEnum):
    RUN_REPLAY_PLAN = "run_replay_plan"
    SET_AUTO_RESPONSE_ENABLED = "set_auto_response_enabled"
    LOAD_AUTO_RESPONSE_RULES = "load_auto_response_rules"
    PREPARE_DEVICE_SCAN = "prepare_device_scan"


class AutomationTriggerKind(StrEnum):
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class AutomationAction:
    kind: AutomationActionKind
    replay_plan_path: str | None = None
    replay_target_kind: TransportKind | None = None
    auto_response_enabled: bool | None = None
    auto_response_rules: tuple[AutoResponseRule, ...] = ()
    device_scan_config: DeviceScanConfig | None = None


@dataclass(frozen=True, slots=True)
class AutomationRule:
    name: str
    trigger_kind: AutomationTriggerKind = AutomationTriggerKind.MANUAL
    enabled: bool = True
    actions: tuple[AutomationAction, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedDeviceScanJob:
    rule_name: str
    config: DeviceScanConfig
    request_count: int


@dataclass(frozen=True, slots=True)
class AutomationRunResult:
    rule_name: str
    executed_action_count: int
    prepared_device_scan_jobs: tuple[PreparedDeviceScanJob, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleExecutionRecord:
    rule_name: str
    succeeded: bool
    executed_action_count: int
    error: str | None = None

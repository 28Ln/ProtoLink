from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.rule_engine import AutomationAction, AutomationActionKind, AutomationRule, AutomationTriggerKind
from protolink.core.transport import TransportKind


AUTOMATION_RULES_FORMAT_VERSION = "protolink-automation-rules-v1"


@dataclass(slots=True)
class AutomationRulesProfile:
    format_version: str = AUTOMATION_RULES_FORMAT_VERSION
    rules: list[AutomationRule] = field(default_factory=list)


def default_automation_rules_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "automation_rules.json"


def load_automation_rules_profile(path: Path) -> AutomationRulesProfile:
    if not path.exists():
        return AutomationRulesProfile()
    try:
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError("automation rules profile is empty")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("automation rules profile must contain a JSON object")
        if str(data.get("format_version", "")) != AUTOMATION_RULES_FORMAT_VERSION:
            raise ValueError("automation rules profile format version is unsupported")
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        _backup_invalid_config_file(path)
        return AutomationRulesProfile()

    rules: list[AutomationRule] = []
    for item in data.get("rules", []):
        if not isinstance(item, dict) or "name" not in item:
            continue
        rules.append(_deserialize_rule(item))
    return AutomationRulesProfile(
        format_version=str(data.get("format_version", AUTOMATION_RULES_FORMAT_VERSION)),
        rules=rules,
    )


def save_automation_rules_profile(path: Path, profile: AutomationRulesProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": profile.format_version,
        "rules": [_serialize_rule(rule) for rule in profile.rules],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _serialize_rule(rule: AutomationRule) -> dict[str, object]:
    return {
        "name": rule.name,
        "trigger_kind": rule.trigger_kind.value,
        "enabled": rule.enabled,
        "actions": [_serialize_action(action) for action in rule.actions],
    }


def _serialize_action(action: AutomationAction) -> dict[str, object]:
    return {
        "kind": action.kind.value,
        "replay_plan_path": action.replay_plan_path,
        "replay_target_kind": action.replay_target_kind.value if action.replay_target_kind is not None else None,
        "auto_response_enabled": action.auto_response_enabled,
        "auto_response_rules": [
            {
                "name": rule.name,
                "protocol": rule.protocol.value,
                "response_payload_hex": rule.response_payload.hex(" "),
                "enabled": rule.enabled,
                "raw_match_payload_hex": rule.raw_match_payload.hex(" "),
                "unit_id": rule.unit_id,
                "function_code": rule.function_code,
                "data_prefix_hex": rule.data_prefix.hex(" "),
            }
            for rule in action.auto_response_rules
        ],
        "device_scan_config": _serialize_device_scan_config(action.device_scan_config),
    }


def _serialize_device_scan_config(config: DeviceScanConfig | None) -> dict[str, object] | None:
    if config is None:
        return None
    return {
        "transport_kind": config.transport_kind.value,
        "target": config.target,
        "unit_id_start": config.unit_id_start,
        "unit_id_end": config.unit_id_end,
        "function_code": config.function_code,
        "start_address": config.start_address,
        "quantity": config.quantity,
        "timeout_ms": config.timeout_ms,
    }


def _deserialize_rule(payload: dict[str, object]) -> AutomationRule:
    actions_raw = payload.get("actions", [])
    actions = tuple(
        _deserialize_action(action_payload)
        for action_payload in actions_raw
        if isinstance(action_payload, dict)
    )
    return AutomationRule(
        name=str(payload["name"]),
        trigger_kind=AutomationTriggerKind(str(payload.get("trigger_kind", AutomationTriggerKind.MANUAL.value))),
        enabled=bool(payload.get("enabled", True)),
        actions=actions,
    )


def _deserialize_action(payload: dict[str, object]) -> AutomationAction:
    auto_rules_raw = payload.get("auto_response_rules", [])
    auto_rules = tuple(
        AutoResponseRule(
            name=str(item.get("name", "")),
            protocol=AutoResponseProtocol(str(item.get("protocol", AutoResponseProtocol.RAW_BYTES.value))),
            response_payload=bytes.fromhex(str(item.get("response_payload_hex", ""))),
            enabled=bool(item.get("enabled", True)),
            raw_match_payload=bytes.fromhex(str(item.get("raw_match_payload_hex", ""))),
            unit_id=int(item["unit_id"]) if item.get("unit_id") is not None else None,
            function_code=int(item["function_code"]) if item.get("function_code") is not None else None,
            data_prefix=bytes.fromhex(str(item.get("data_prefix_hex", ""))),
        )
        for item in auto_rules_raw
        if isinstance(item, dict)
    )
    device_scan_raw = payload.get("device_scan_config")
    device_scan = _deserialize_device_scan_config(device_scan_raw) if isinstance(device_scan_raw, dict) else None
    replay_target_raw = payload.get("replay_target_kind")
    replay_target = TransportKind(str(replay_target_raw)) if replay_target_raw else None
    return AutomationAction(
        kind=AutomationActionKind(str(payload.get("kind", AutomationActionKind.SET_AUTO_RESPONSE_ENABLED.value))),
        replay_plan_path=str(payload["replay_plan_path"]) if payload.get("replay_plan_path") is not None else None,
        replay_target_kind=replay_target,
        auto_response_enabled=bool(payload["auto_response_enabled"]) if payload.get("auto_response_enabled") is not None else None,
        auto_response_rules=auto_rules,
        device_scan_config=device_scan,
    )


def _deserialize_device_scan_config(payload: dict[str, object]) -> DeviceScanConfig:
    return DeviceScanConfig(
        transport_kind=DeviceScanTransportKind(str(payload.get("transport_kind", DeviceScanTransportKind.MODBUS_TCP.value))),
        target=str(payload.get("target", "")),
        unit_id_start=int(payload.get("unit_id_start", 1)),
        unit_id_end=int(payload.get("unit_id_end", 16)),
        function_code=int(payload.get("function_code", 0x03)),
        start_address=int(payload.get("start_address", 0)),
        quantity=int(payload.get("quantity", 1)),
        timeout_ms=int(payload.get("timeout_ms", 500)),
    )


def _backup_invalid_config_file(path: Path) -> Path | None:
    if not path.exists():
        return None

    for index in range(100):
        suffix = ".invalid" if index == 0 else f".invalid.{index}"
        backup_path = path.with_name(f"{path.name}{suffix}")
        if backup_path.exists():
            continue
        try:
            path.replace(backup_path)
        except OSError:
            return None
        return backup_path
    return None

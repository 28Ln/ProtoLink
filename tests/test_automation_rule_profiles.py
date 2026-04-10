from pathlib import Path

from protolink.core.auto_response import AutoResponseProtocol, AutoResponseRule
from protolink.core.automation_rule_profiles import (
    AutomationRulesProfile,
    default_automation_rules_profile_path,
    load_automation_rules_profile,
    save_automation_rules_profile,
)
from protolink.core.device_scan import DeviceScanConfig, DeviceScanTransportKind
from protolink.core.rule_engine import AutomationAction, AutomationActionKind, AutomationRule
from protolink.core.transport import TransportKind


def test_automation_rule_profile_roundtrip(tmp_path: Path) -> None:
    path = default_automation_rules_profile_path(tmp_path)
    profile = AutomationRulesProfile(
        rules=[
            AutomationRule(
                name="Replay",
                actions=(
                    AutomationAction(
                        kind=AutomationActionKind.RUN_REPLAY_PLAN,
                        replay_plan_path="C:/tmp/demo.json",
                        replay_target_kind=TransportKind.TCP_CLIENT,
                    ),
                ),
            ),
            AutomationRule(
                name="Scan + Response",
                actions=(
                    AutomationAction(
                        kind=AutomationActionKind.PREPARE_DEVICE_SCAN,
                        device_scan_config=DeviceScanConfig(
                            transport_kind=DeviceScanTransportKind.MODBUS_TCP,
                            target="127.0.0.1:502",
                            unit_id_start=1,
                            unit_id_end=3,
                        ),
                    ),
                    AutomationAction(
                        kind=AutomationActionKind.LOAD_AUTO_RESPONSE_RULES,
                        auto_response_rules=(
                            AutoResponseRule(
                                name="Ping",
                                protocol=AutoResponseProtocol.RAW_BYTES,
                                raw_match_payload=b"PING",
                                response_payload=b"PONG",
                            ),
                        ),
                    ),
                ),
            ),
        ]
    )

    save_automation_rules_profile(path, profile)
    loaded = load_automation_rules_profile(path)

    assert loaded.format_version == "protolink-automation-rules-v1"
    assert len(loaded.rules) == 2
    assert loaded.rules[0].actions[0].replay_target_kind == TransportKind.TCP_CLIENT
    assert loaded.rules[1].actions[0].device_scan_config is not None
    assert loaded.rules[1].actions[1].auto_response_rules[0].response_payload == b"PONG"


def test_automation_rule_profile_backs_up_malformed_file(tmp_path: Path) -> None:
    path = default_automation_rules_profile_path(tmp_path)
    path.write_text("{not-json", encoding="utf-8")

    loaded = load_automation_rules_profile(path)

    assert loaded.rules == []
    assert not path.exists()
    assert (path.parent / "automation_rules.json.invalid").read_text(encoding="utf-8") == "{not-json"


def test_automation_rule_profile_backs_up_unsupported_format_version(tmp_path: Path) -> None:
    path = default_automation_rules_profile_path(tmp_path)
    path.write_text('{"format_version": "future-version", "rules": []}', encoding="utf-8")

    loaded = load_automation_rules_profile(path)

    assert loaded.format_version == "protolink-automation-rules-v1"
    assert loaded.rules == []
    assert not path.exists()
    assert (path.parent / "automation_rules.json.invalid").exists()

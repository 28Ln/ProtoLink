from __future__ import annotations

import argparse
import subprocess
import sys


SUITES: dict[str, tuple[str, ...]] = {
    "pl001_release_truth": (
        "tests/test_app.py",
        "tests/test_event_bus.py",
        "tests/test_logging.py",
        "tests/test_packaging.py",
        "tests/test_bootstrap.py",
    ),
    "pl003_runtime_truth": (
        "tests/test_register_monitor_service.py",
        "tests/test_device_scan_execution_service.py",
        "tests/test_auto_response_runtime_service.py",
        "tests/test_channel_bridge_runtime_service.py",
        "tests/test_packet_replay_service.py",
        "tests/test_mqtt_server_service.py",
        "tests/test_tcp_server_service.py",
    ),
    "pl006_automation_owner_surface": (
        "tests/test_rule_engine_service.py",
        "tests/test_script_host_service.py",
        "tests/test_timed_task_service.py",
        "tests/test_channel_bridge_runtime_service.py",
        "tests/test_ui_automation_rules_panel.py",
    ),
    "pl007_script_console_owner_surface": (
        "tests/test_script_console_service.py",
        "tests/test_ui_script_console_panel.py",
        "tests/test_ui_main_window.py",
    ),
    "pl008_data_tools_owner_surface": (
        "tests/test_data_tools_service.py",
        "tests/test_ui_data_tools_panel.py",
        "tests/test_ui_main_window.py",
    ),
    "pl009_network_tools_owner_surface": (
        "tests/test_network_tools_service.py",
        "tests/test_ui_network_tools_panel.py",
        "tests/test_ui_main_window.py",
    ),
    "pl010_ui_consistency": (
        "tests/test_ui_owner_surface_consistency.py",
        "tests/test_ui_automation_rules_panel.py",
        "tests/test_ui_script_console_panel.py",
        "tests/test_ui_data_tools_panel.py",
        "tests/test_ui_network_tools_panel.py",
        "tests/test_ui_register_monitor_panel.py",
        "tests/test_modbus_rtu_workflow_acceptance.py",
        "tests/test_modbus_tcp_workflow_acceptance.py",
        "tests/test_ui_main_window.py",
    ),
}


def run_suite(name: str) -> None:
    test_paths = SUITES[name]
    print(f"[targeted-regression] suite={name}")
    print(f"[targeted-regression] tests={' '.join(test_paths)}")
    for test_path in test_paths:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_path],
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(
                f"Targeted regression suite '{name}' failed on '{test_path}' with exit code {completed.returncode}."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ProtoLink targeted regression suites.")
    parser.add_argument(
        "--suite",
        default="all",
        choices=("all", *SUITES.keys()),
        help="Run one named suite or all suites.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suite names and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for name, tests in SUITES.items():
            print(f"{name}: {' '.join(tests)}")
        return 0

    if args.suite == "all":
        for suite_name in SUITES:
            run_suite(suite_name)
        return 0

    run_suite(args.suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

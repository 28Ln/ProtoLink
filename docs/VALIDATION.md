# ProtoLink Validation

## 1. 当前可执行验证

### 当前验证基线

- `uv run pytest -q` -> 263 passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-011 --expected-pytest-count 263` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `uv build` -> passed
- `uv run protolink --headless-summary` -> passed
- `uv run protolink --smoke-check` -> passed with clean `smoke-check-ok` output
- `uv run protolink --release-preflight` -> passed
- `<install-dir>\\runtime\\python.exe -m protolink --headless-summary` -> passed for the installed bundled-runtime payload

### 当前 CI 真值

CI currently enforces:

- full pytest
- canonical truth verification
- targeted regression suites
- release-staging verification via `scripts/verify_release_staging.py` (including portable/distribution/installer verify + install/uninstall)
- clean release-staging verification
- `uv build`

### 环境同步

```powershell
uv sync --python 3.11 --extra dev
```

### 运行测试

```powershell
uv run pytest
```

### 运行 canonical truth gate

```powershell
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-011 --expected-pytest-count 263
```

### 运行 targeted regression gate

```powershell
uv run python scripts/run_targeted_regressions.py --suite all
uv run python scripts/run_targeted_regressions.py --suite pl006_automation_owner_surface
uv run python scripts/run_targeted_regressions.py --suite pl007_script_console_owner_surface
uv run python scripts/run_targeted_regressions.py --suite pl008_data_tools_owner_surface
uv run python scripts/run_targeted_regressions.py --suite pl009_network_tools_owner_surface
uv run python scripts/run_targeted_regressions.py --suite pl010_ui_consistency
```

### 运行 clean release-staging 验证

```powershell
uv run python scripts/verify_release_staging.py --name local
```

### 当前 owner-surface 重点回归

- `uv run pytest tests/test_script_console_service.py tests/test_ui_script_console_panel.py tests/test_ui_main_window.py tests/test_script_host_service.py -q`
- `uv run pytest tests/test_data_tools_service.py tests/test_ui_data_tools_panel.py tests/test_ui_main_window.py -q`
- `uv run pytest tests/test_network_tools_service.py tests/test_ui_network_tools_panel.py tests/test_ui_main_window.py -q`

### 当前 reconciliation lane 重点回归

- `uv run pytest tests/test_logging.py tests/test_event_bus.py tests/test_auto_response_runtime_service.py tests/test_device_scan_execution_service.py tests/test_register_monitor_service.py tests/test_script_host_service.py tests/test_packet_replay_service.py tests/test_channel_bridge_runtime_service.py tests/test_rule_engine_service.py tests/test_timed_task_service.py tests/test_bootstrap.py -q`
- `uv run pytest tests/test_script_console_service.py tests/test_data_tools_service.py tests/test_network_tools_service.py tests/test_ui_script_console_panel.py tests/test_ui_data_tools_panel.py tests/test_ui_network_tools_panel.py tests/test_ui_automation_rules_panel.py tests/test_ui_owner_surface_consistency.py tests/test_ui_main_window.py -q`

### 当前 full-suite snapshot

- `263 passed`
- no warning summary

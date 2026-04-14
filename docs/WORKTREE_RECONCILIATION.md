# ProtoLink Worktree Reconciliation

Last rebuilt: 2026-04-14

## Purpose

This file is the execution artifact for `PL-011`.

It exists because the verified `PL-001` through `PL-010` stack accumulated above the original local baseline in one long-lived worktree.

`PL-011` treats that stack as one reconciliation scope that must be made understandable and handoff-safe before new feature work resumes.

## Handoff anchor

- Original visible local baseline commit: `0fbaec6` (`Establish a verified ProtoLink delivery baseline`)
- Current reconciliation worktree size: `50` tracked modified paths, `16` untracked paths
- Current diff footprint: `3273` insertions / `1864` deletions
- Authoritative validation environment: `uv`-managed project environment (`uv run ...`)
- Canonical mainline truth: `PL-011`

## Reconciliation scope

### 1. Canonical truth / handoff layer

- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/PROJECT_STATUS.md`
- `docs/MAINLINE_STATUS.md`
- `docs/TASK_ARCHIVE.md`
- `docs/VALIDATION.md`
- `.github/workflows/ci.yml`

### 2. Delivery / release verification layer

- `scripts/verify_canonical_truth.py`
- `scripts/run_targeted_regressions.py`
- `scripts/verify_release_staging.py`
- `src/protolink/core/packaging.py`
- release/install verification coverage under `tests/test_packaging.py` and `tests/test_app.py`

### 3. Runtime / context hardening layer

- `src/protolink/application/auto_response_runtime_service.py`
- `src/protolink/application/channel_bridge_runtime_service.py`
- `src/protolink/application/device_scan_execution_service.py`
- `src/protolink/application/packet_replay_service.py`
- `src/protolink/application/register_monitor_service.py`
- `src/protolink/application/rule_engine_service.py`
- `src/protolink/application/script_host_service.py`
- `src/protolink/application/timed_task_service.py`
- `src/protolink/core/bootstrap.py`
- `src/protolink/core/logging.py`
- `src/protolink/core/event_bus.py`
- related runtime/service tests

### 4. Owner-surface expansion layer

- `src/protolink/application/script_console_service.py`
- `src/protolink/application/data_tools_service.py`
- `src/protolink/application/network_tools_service.py`
- `src/protolink/core/data_tools.py`
- `src/protolink/ui/script_console_panel.py`
- `src/protolink/ui/data_tools_panel.py`
- `src/protolink/ui/network_tools_panel.py`
- `src/protolink/ui/main_window.py`
- related service and UI tests

### 5. PL-010 consistency-closure layer

- `src/protolink/ui/automation_rules_panel.py`
- `tests/test_ui_automation_rules_panel.py`
- `tests/test_ui_owner_surface_consistency.py`
- focused UI contract assertions around notice/status/error labels, wrapped guidance, and CTA gating

## Lane status

### Docs / CI / handoff truth

- Current status: synchronized to `PL-011`
- Main evidence:
  - canonical truth gate passes under `PL-011`
  - `README.md`, `docs/`, and `.github/workflows/ci.yml` now point to the same active mainline
  - supporting docs now explicitly separate canonical truth from operational/reference artifacts

### Delivery / release verification

- Current status: baseline-worthy as one release path
- Main evidence:
  - release-truth targeted regressions pass
  - `verify_release_staging.py` passes end-to-end
- Preferred split boundary:
  1. runtime release plumbing (`import_export.py`, `packaging.py`, `app.py`, release tests)
  2. release-process automation (`verify_canonical_truth.py`, `run_targeted_regressions.py`, `verify_release_staging.py`)

### Runtime / context hardening

- Current status: verified by the canonical `uv`-managed full suite, but still too broad for a single fine-grained reconciliation commit
- Main evidence:
  - `uv run pytest tests/test_logging.py tests/test_event_bus.py tests/test_auto_response_runtime_service.py tests/test_device_scan_execution_service.py tests/test_register_monitor_service.py tests/test_script_host_service.py tests/test_packet_replay_service.py tests/test_channel_bridge_runtime_service.py tests/test_rule_engine_service.py tests/test_timed_task_service.py tests/test_bootstrap.py -q` -> `49 passed`
- Preferred split boundary:
  1. substrate (`core/event_bus.py`, `core/logging.py`)
  2. synchronous runtime services (`script_host`, `register_monitor`, `auto_response`, `device_scan`)
  3. orchestration services (`packet_replay`, `channel_bridge`, `timed_task`, `rule_engine`)
  4. bootstrap wiring last

### Owner-surface expansion

- Current status: verified by the canonical `uv`-managed full suite and targeted owner-surface regressions
- Main evidence:
  - `uv run pytest tests/test_script_console_service.py tests/test_data_tools_service.py tests/test_network_tools_service.py tests/test_ui_script_console_panel.py tests/test_ui_data_tools_panel.py tests/test_ui_network_tools_panel.py tests/test_ui_automation_rules_panel.py tests/test_ui_owner_surface_consistency.py tests/test_ui_main_window.py -q` -> `15 passed`
- Preferred split boundary:
  1. non-Qt service logic (`script_console_service.py`, `data_tools_service.py`, `network_tools_service.py`, `core/data_tools.py`)
  2. utility panels (`script_console_panel.py`, `data_tools_panel.py`, `network_tools_panel.py`)
  3. cross-cutting orchestration UI (`automation_rules_panel.py`, `main_window.py`, related tests)

## Current operating rule

Until `PL-011` is closed:

- do not restart feature expansion on top of this mixed stack
- do not treat the whole worktree as a fine-grained bisectable history
- keep canonical docs, CI, and validation synchronized with the single active mainline
- do not treat non-`uv` Python or pytest runs as canonical verification evidence
- do not imply separate CI steps for package install/uninstall when the workflow covers them through `scripts/verify_release_staging.py`

## Planned split order

1. **Docs / CI / handoff truth**
   - keep `README.md`, `docs/`, `.github/workflows/ci.yml`, and this artifact synchronized
2. **Delivery / release verification**
   - keep packaging, release verification scripts, and their tests together as one reviewable lane
3. **Runtime / context hardening**
   - split substrate (`event_bus`, `logging`) before higher-coordination runtime services and bootstrap wiring
4. **Owner-surface expansion**
   - split non-Qt service logic before utility panels, then split cross-cutting UI orchestration surfaces last

## Verification baseline for reconciliation

The reconciled stack is currently evidenced by:

- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-011 --expected-pytest-count 274`
- `uv run python scripts/run_targeted_regressions.py --suite all`
- `uv run pytest -q`
- `uv run protolink --headless-summary`
- `uv run protolink --smoke-check`
- `uv run python scripts/verify_release_staging.py --name ci`
- `uv build`
- Visible CI currently stops at `uv build`; package verify/install/uninstall coverage is exercised inside `scripts/verify_release_staging.py`
- Non-`uv` Python or pytest runs are non-authoritative for this mainline and may report environment gaps that do not reflect the project-managed validation truth

## Exit criteria

`PL-011` closes only when:

- the canonical docs, CI gate, and validation commands all point to `PL-011`
- the handoff anchor explicitly records the baseline commit, current worktree scope, validation environment, and split order
- the next iteration can start from one trustworthy baseline narrative instead of a mixed historical stack

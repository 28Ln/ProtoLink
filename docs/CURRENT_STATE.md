# ProtoLink Current State

Last rebuilt: 2026-04-12

## Canonical scope

This file is the current-state truth for ProtoLink.

- It records only conclusions still supported by repository facts.
- It does not preserve legacy task ordering or stale milestone narration.
- Historical stages and retired aliases live in `docs/TASK_ARCHIVE.md`.

## Evidence basis

This rebuild uses only:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/MAINLINE_STATUS.md`
- `docs/TASK_ARCHIVE.md`
- current repository structure and key entry files under `src/protolink/`
- `git status`, `git diff --stat`, and recent project-local commits
- validation commands and results executed on 2026-04-12

## Repository / git truth

- ProtoLink has a project-local Git repository rooted at `C:/Users/Administrator/Desktop/ProtoLink`.
- ProtoLink originally established the project-local delivery baseline at commit `0fbaec6` (`Establish a verified ProtoLink delivery baseline`).
- `PL-011` now exists because a long-lived verified post-baseline stack accumulated above that original baseline and must be reconciled into one trustworthy handoff point.
- `ref/` remains reference-only local material and is excluded from the formal delivery baseline.

## Product shell truth

- The formal product lives under `src/protolink/`.
- The executable entry chain is:
  - `src/protolink/__main__.py`
  - `src/protolink/app.py`
  - `src/protolink/core/bootstrap.py`
  - `src/protolink/ui/main_window.py`
- The stack remains Windows-first, Python 3.11, PySide6, `uv`, and pytest.

## Runtime composition truth

- `bootstrap_app_context()` currently constructs:
  - workspace and settings layouts
  - transport registry
  - event bus
  - in-memory log store
  - workspace log writer
  - packet inspector state
  - session services for Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server
  - runtime services for replay, register monitor, auto response, rule engine, device scan execution, script host, timed tasks, channel bridge, and capture/replay jobs
- runtime consumers that depend on an active session now have explicit session/peer truth hooks in the current dirty-mainline slice:
  - register monitor live scope
  - device scan target session/peer scope
  - auto response target session/peer scope
  - channel bridge source session/peer scope
  - packet replay target session/peer scope
- Registered transport kinds are:
  - `serial`
  - `tcp_client`
  - `tcp_server`
  - `udp`
  - `mqtt_client`
  - `mqtt_server`

## Implemented owner-surface truth

- The main window currently exposes dedicated panels for:
  - Serial Studio
  - Modbus RTU Lab
  - Modbus TCP Lab
  - MQTT Client
  - MQTT Server
  - TCP Client
  - TCP Server
  - UDP Lab
  - Register Monitor
  - Automation Rules
  - Script Console
  - Data Tools
  - Network Tools
- The packet inspector is exposed through a docked `PacketConsoleWidget`.
- `Automation Rules` now also exposes runtime safety controls for:
  - auto-response enable / disable
  - timed-task start / stop
  - channel-bridge clear
- `Network Tools` is now exposed as a read-only-first owner surface in the main window.

## Delivery truth

- ProtoLink already has executable commands for:
  - headless summary
  - smoke check
  - workspace migration
  - release preflight
  - release bundle export
  - release archive packaging
  - portable / distribution / installer package build
  - package verification
  - package install / uninstall
- Portable/distribution/installer payloads now bundle a Python runtime plus application/runtime dependencies.
- Installed payloads can now run `protolink --headless-summary` through the bundled runtime without requiring preinstalled `uv` or Python.
- Current delivery capability is now “bundled-runtime clean-machine runnable delivery”, but not yet a native self-contained Windows installer/executable product line.
- The current engineering-quality gate now includes:
  - canonical truth verification via `scripts/verify_canonical_truth.py`
  - targeted regression suites via `scripts/run_targeted_regressions.py`
  - clean release-staging verification via `scripts/verify_release_staging.py`

## Validation truth (executed 2026-04-12)

- `uv run pytest -q` -> `263 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-011 --expected-pytest-count 263` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `uv run pytest tests/test_script_console_service.py tests/test_ui_script_console_panel.py tests/test_ui_main_window.py tests/test_script_host_service.py -q` -> passed
- `uv run pytest tests/test_data_tools_service.py tests/test_ui_data_tools_panel.py tests/test_ui_main_window.py -q` -> passed
- `uv run pytest tests/test_network_tools_service.py tests/test_ui_network_tools_panel.py tests/test_ui_main_window.py tests/test_bootstrap.py -q` -> passed
- `uv build` -> passed
- `uv run protolink --headless-summary` -> passed
- `uv run protolink --smoke-check` -> `smoke-check-ok`
- `uv run protolink --workspace .\\workspace\\audit-tmp-verification --generate-smoke-artifacts` -> passed
- `uv run protolink --workspace .\\workspace\\audit-tmp-verification --release-preflight` -> passed
- `uv run protolink --workspace .\\workspace\\audit-tmp-verification --build-installer-package audit` -> passed
- `uv run protolink --verify-installer-package <generated-archive>` -> passed
- `uv run protolink --install-installer-package <generated-archive> <staging-dir> <install-dir>` -> passed
- `<install-dir>\\runtime\\python.exe -m protolink --headless-summary` -> passed for the installed bundled-runtime payload
- `uv run protolink --uninstall-portable-package <install-dir>` -> passed

## Baseline-reconciliation truth

- `PL-011` exists because release hardening, runtime hardening, owner-surface expansion, and canonical doc/CI truth accumulated in one long-lived post-baseline stack.
- The active reconciliation line now treats that verified stack as one baseline candidate instead of as unrelated local residue.
- The current handoff goal is one trustworthy post-PL-010 baseline with canonical docs, CI, and validation all pointing at the same mainline truth.
- The current reconciliation anchor is still the original local baseline commit `0fbaec6`, plus a verified worktree that currently spans `50` tracked modified paths, `16` untracked paths, and `3273` insertions / `1864` deletions.
- Authoritative validation for this reconciliation scope is the `uv`-managed environment; ad-hoc system-Python collection failures are not canonical truth.

## Current judgment

- Transport breadth and basic owned workflow coverage are no longer the first-order gap.
- The completed release-gate slice established:
  - one canonical backlog
  - one canonical mainline
  - one clean baseline or explicitly classified dirty baseline
  - one trustworthy release gate tied to real validation evidence
- Owner-surface consistency is no longer the first-order gap; `PL-010` now has explicit regression evidence and closure proof.
- The current first-order gap is baseline reconciliation, canonical handoff truth, and a trustworthy post-PL-010 mainline baseline.

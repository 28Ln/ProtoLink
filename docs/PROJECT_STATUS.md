# ProtoLink Project Status

Last rebuilt: 2026-04-10

## Canonical status pointers

- Current state truth: `docs/CURRENT_STATE.md`
- Canonical backlog: `docs/ENGINEERING_TASKLIST.md`
- Single mainline: `docs/MAINLINE_STATUS.md`
- Historical archive: `docs/TASK_ARCHIVE.md`

## Active

- `BL-002` — Packaging / release / workspace migration.
  - Status: active mainline
  - Why it is active: the owned workflow line is now established for both RTU and TCP, so the next highest-value task is converting verified product surface into explicit release-preparation truth.
  - Current round progress: release-preparation artifacts now exist through `docs/SMOKE_CHECKLIST.md` and `docs/RELEASE_CHECKLIST.md`; `--smoke-check`, `--generate-smoke-artifacts`, `--export-latest-profile`, `--migrate-workspace`, `--release-preflight`, `--export-release-bundle`, `--prepare-release`, `--package-release`, `--build-portable-package`, `--install-portable-package`, `--verify-portable-package`, `--build-distribution-package`, `--install-distribution-package`, `--build-installer-staging`, `--install-installer-staging`, and `--verify-installer-package` now provide executable release-prep primitives; release-preflight now blocks on missing capture artifacts; portable packages now have a manifest-backed checksum truth surface; distribution / installer installs now verify nested archive checksums; install paths now reject zip path-traversal / symlink entries; portable packages now omit `__pycache__` / `.pyc` residue; config/profile schema backups preserve invalid JSON as `.invalid`; EventBus/log writer failures are isolated; packet replay GUI notifications are dispatcher-aware; Python inline scripts use a builtins whitelist; MQTT server uses amqtt's explicit plugin configuration; offscreen smoke output is clean; a project-local CI workflow now mirrors compileall, pytest, smoke summary, and build.

## Next

- `BL-003` — Script Console UI, Data Tools, and Network Tools boundary.
  - Status: next, not a blocker for the active release-preparation mainline.
  - Entry condition: BL-002 exits with clean release evidence and documentation synchronized.
  - Acceptance shape: Script Console must keep the current script-host whitelist and expose stdout/result/error plus a stop/disable boundary; Data Tools must be deterministic and testable without transport state; Network Tools must start read-only and isolate privileged operations behind explicit rollback documentation.
  - Verification seed: `uv run pytest tests/test_script_host_service.py tests/test_rule_engine_service.py tests/test_channel_bridge_runtime_service.py -q`, focused Data Tools tests, focused Network Tools privilege-boundary tests, and `uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q`.

## Blocked

- No additional blocked items beyond the active backlog ordering.

## Validation snapshot

- `uv run protolink --headless-summary` -> passed on 2026-04-09
- `uv run protolink --create-export-scaffold log demo .json` -> passed on 2026-04-09
- `uv run protolink --workspace <temp-workspace> --export-runtime-log bench-runtime` -> passed on 2026-04-09
- `uv run protolink --workspace <temp-workspace> --export-latest-profile bench-profile` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --generate-smoke-artifacts` -> passed on 2026-04-09
- `uv run protolink --smoke-check` -> passed on 2026-04-09
- `uv run protolink --migrate-workspace` -> passed on 2026-04-09
- `uv run protolink --release-preflight` -> passed on 2026-04-09
- `uv run protolink --workspace <temp-workspace> --export-release-bundle bench-release` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --prepare-release bench-release` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --package-release bench-release` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --build-portable-package bench-portable` -> passed on 2026-04-09
- `uv run protolink --install-portable-package <archive> <target-dir>` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --build-distribution-package bench-distribution` -> passed on 2026-04-09
- `uv run protolink --install-distribution-package <archive> <staging-dir> <target-dir>` -> passed on 2026-04-09
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-staging bench-installer` -> passed on 2026-04-09
- `uv run protolink --install-installer-staging <archive> <staging-dir> <target-dir>` -> passed on 2026-04-09
- `uv run protolink --verify-installer-staging <archive>` -> passed on 2026-04-09
- `uv run pytest` -> 229 passed on 2026-04-10
- `uv build` -> passed on 2026-04-10
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-package audit-fix` -> passed on 2026-04-10
- `uv run protolink --verify-installer-package .\\workspace\\lab-a\\exports\\20260410-114315-installer-package-audit-fix.zip` -> passed on 2026-04-10
- Offscreen Qt smoke -> passed on 2026-04-09
- `uv run pytest tests/test_ui_modbus_rtu_panel.py tests/test_ui_main_window.py tests/test_packet_inspector.py tests/test_register_monitor_service.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_logging.py tests/test_wiring.py tests/test_ui_modbus_rtu_panel.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_import_export.py tests/test_app.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_modbus_rtu_workflow_acceptance.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_ui_modbus_tcp_panel.py tests/test_ui_main_window.py tests/test_catalog.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_ui_modbus_tcp_panel.py tests/test_ui_main_window.py tests/test_catalog.py tests/test_tcp_client_service.py tests/test_packet_replay_service.py -q` -> passed on 2026-04-09
- `uv run pytest tests/test_modbus_tcp_workflow_acceptance.py -q` -> passed on 2026-04-09

## Dirty workspace / baseline classification

### Facts

- ProtoLink now has a project-local git baseline under `C:/Users/Administrator/Desktop/ProtoLink`.
- The parent home-directory repository is no longer the source of truth for ProtoLink diffs; project-local `git status` is the canonical baseline check.
- Runtime artifacts currently present in-tree include:
  - `.protolink/app_settings.json`
  - `workspace/lab-a/exports/*`
  - `workspace/lab-a/profiles/serial_studio.json`

### Preparation-round ownership classification

- Mainline-owned documentation changes in this round:
  - `docs/CURRENT_STATE.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/ENGINEERING_TASKLIST.md`
  - `docs/MAINLINE_STATUS.md`
  - `docs/TASK_ARCHIVE.md`
  - `README.md`
  - legacy redirect cleanup in `TASKS.md` and `docs/STATUS.md`
- Historical or runtime residue not treated as active backlog progress:
  - generated workspace artifacts under `workspace/`
  - generated settings under `.protolink/`
  - legacy non-canonical status/task files now retired from primary use

## Preparation phase status

### Completed

- Canonical backlog has been rebuilt from current project truth.
- Task IDs have been reset and normalized under one canonical scheme.
- A single active mainline has been fixed.
- Legacy task/status documents have been retired from canonical use.
- Next-iteration entry, verification gate, and doc sync points are now explicit.
- The mainline now has an explicit GUI owner surface (`Modbus RTU Lab`) instead of only scattered shared panels.
- Workspace-backed transport log materialization now exists through `workspace/logs/transport-events.jsonl`.
- Runtime log export now packages a real workspace log artifact instead of only scaffold payloads.
- The RTU workflow now has a dedicated acceptance test covering workspace logs, captures, export bundle output, and replay execution.
- Code-visible status drift is now partially reduced:
  - implemented transport surfaces are marked `Bootstrapped`
  - the main window no longer hardcodes a stale mainline ID
- Modbus TCP now has an explicit owned GUI surface instead of existing only as shared transport + parser capability.
- Modbus TCP owned surface now includes replay/export depth, not only request/bootstrap controls.
- Modbus TCP now also has a dedicated acceptance path.
- Release preparation now has explicit checklist artifacts instead of only roadmap text.
- Release preparation now also has an executable CLI smoke-check entry point.
- Release preparation now also has a real profile export path for workspace-migration-oriented artifact packaging.
- Release preparation now also has a versioned workspace manifest and executable migration command.
- Release preparation now also has executable release-preflight and multi-artifact release-bundle commands.
- Release preparation now also has an executable one-shot `--prepare-release` orchestration command.
- Release preparation now also has an executable `--package-release` archive packaging command.
- Release preparation now also has an executable `--build-portable-package` portable packaging command.
- Release preparation now also has an executable `--install-portable-package` extraction/install command.
- Release preparation now also has an executable `--build-distribution-package` distribution package command.
- Release preparation now also has an executable `--install-distribution-package` extraction/install command.
- Release preparation now also has an executable `--build-installer-staging` command.
- Release preparation now also has an executable `--install-installer-staging` command.
- Release preparation now also has an executable `--verify-installer-staging` command.
- Release preparation now also has an executable `--verify-portable-package` command.
- Release preparation now also has an executable `--verify-installer-package` command.
- Release preflight now treats missing capture artifacts as a blocking condition.
- Portable package build/install now has a manifest-backed checksum truth surface.
- Distribution / installer install paths now enforce checksum validation on nested archives.
- Portable / distribution / installer install paths now reject zip path-traversal / symlink entries during extraction.
- Portable package output now excludes `__pycache__` / `.pyc` residue.
- Current implementation quality now also includes dispatcher-safe replay UI updates, config backup on invalid JSON, logging fault isolation, script-host builtins scoping, and a project-local CI workflow.

### Open release-prep signal

- The active `workspace/lab-a` is now preflight-green after generating smoke artifacts.
- The active `workspace/lab-a` now also completes a full `--build-portable-package` flow.
- The active `workspace/lab-a` now also completes a full `--build-distribution-package` flow.
- The active `workspace/lab-a` now also completes a full distribution extract/install flow.
- The active `workspace/lab-a` now also completes a full `--build-installer-staging` flow.
- The active `workspace/lab-a` now also completes a full installer-staging extract/install flow.
- The active `workspace/lab-a` now also verifies the top-level installer-package archive.
- The remaining blocker is no longer artifact absence, missing install-time checksum gates, or warning noise; it is proving the installer flow in a clean release-staging environment.
- Script Console, Data Tools, and Network Tools are intentionally not release-prep blockers; they are the next product-expansion boundary after BL-002 exits.

### Still true after preparation

- A clean project-local git baseline now exists for the formal ProtoLink delivery files; `ref/` is intentionally excluded as local external-reference material.
- No additional implemented-surface status drift is currently evidenced in the catalog/main-window path after the latest cleanup rounds.

### Judgment

Preparation is complete enough to start the next implementation iteration, because the backlog, mainline, verification gate, and documentation truth have been re-frozen.

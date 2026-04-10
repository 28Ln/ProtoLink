# ProtoLink Current State

Last rebuilt: 2026-04-10

## Canonical scope

This file is the current-state truth for ProtoLink.

- It replaces the current-state role previously carried by legacy `docs/STATUS.md`.
- It records only conclusions that are still supported by repository facts.
- Historical task history is moved out of the active path and summarized in `docs/TASK_ARCHIVE.md`.

## Evidence basis

This state summary is rebuilt only from:

- `README.md`
- `docs/ARCHITECTURE.md`
- current repository structure and key entry files under `src/protolink/`
- parent-repository git facts visible from this workspace
- validation commands run on 2026-04-10

## Facts

### Repository / git truth

- No `AGENT.md` or `AGENTS.md` file exists in the project root.
- The ProtoLink directory now contains a project-local `.git` directory.
- `git rev-parse --show-toplevel` from the ProtoLink workspace returns `C:/Users/Administrator/Desktop/ProtoLink`.
- The project-local baseline excludes generated/runtime directories via `.gitignore`, including `.omx/`, `.protolink/`, `workspace/`, `dist/`, and `audit_tmp*/`.
- `ref/` remains a local reference-asset directory and is excluded from the project-local delivery baseline because its child projects are embedded Git repositories.

### Product shell truth

- The official product line is the root Python project under `src/protolink/`.
- `ref/llcom` and `ref/Wu.CommTool` are reference-only assets, not the delivery baseline.
- The executable entry chain is:
  - `src/protolink/__main__.py`
  - `src/protolink/app.py`
  - `src/protolink/core/bootstrap.py`
  - `src/protolink/ui/main_window.py`

### Runtime composition truth

- `bootstrap_app_context()` constructs:
  - workspace and settings layouts
  - transport registry
  - event bus
  - in-memory log store
  - packet inspector state
  - session services for Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server
  - runtime services for replay, register monitor, auto response, rule engine, device scan execution, script host, timed tasks, channel bridge, and capture/replay jobs
- The registered transport kinds are:
  - `serial`
  - `tcp_client`
  - `tcp_server`
  - `udp`
  - `mqtt_client`
  - `mqtt_server`

### Implemented GUI truth

- The main window currently renders dedicated panels for:
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
- The packet inspector is exposed as a dock through `PacketConsoleWidget`.
- `Modbus RTU Lab` now has a dedicated workflow panel for read-request composition, serial dispatch, register-monitor seeding, and packet-inspector decode linkage.
- `Modbus TCP Lab` now has a dedicated workflow panel for request composition, TCP client dispatch, register-monitor seeding, and packet-inspector decode linkage.
- `Modbus TCP Lab` now also supports replay-plan export, replay execution, and capture-bundle export from the owned workflow surface.
- `Modbus TCP Lab` now has a dedicated acceptance path through `tests/test_modbus_tcp_workflow_acceptance.py`.
- `Script Console`, `Data Tools`, and `Network Tools` still exist in the module catalog without dedicated main-window workflow panels.

### Data / logging / export truth

- Transport events are normalized into `StructuredLogEntry`.
- Raw payload bytes are retained in memory and fed into `PacketInspectorState`.
- Transport log entries are now also materialized into `workspace/logs/transport-events.jsonl`.
- EventBus handler failures are isolated and retained as handler-error evidence instead of stopping later subscribers.
- Workspace JSONL log writes now record write-failure counters instead of throwing through the transport path.
- Invalid workspace/settings/profile/rules JSON files are now backed up to `.invalid` files before fallback/rebuild behavior runs.
- Replay-plan files can be written under `workspace/captures/`.
- Export scaffold bundles can be written under `workspace/exports/`.
- Runtime log bundles can now be exported from real workspace log files instead of placeholder payloads.
- Latest workspace profile artifacts can now be exported into real profile bundles.
- Multi-artifact release bundles can now be exported from the active workspace.
- Release preflight now treats missing capture artifacts as a blocking condition instead of a ready-state warning gap.
- Portable package archives can now be built on top of packaged release bundles.
- Portable package archives can now be extracted into a target directory.
- Portable package archives now carry a manifest-backed checksum truth surface and an explicit verification path.
- Portable package archives now exclude `__pycache__` / `.pyc` residue from copied source payloads.
- Distribution package archives can now be built on top of portable and release archives.
- Distribution package archives can now be extracted into staging and target directories.
- Distribution / installer install flows now validate manifest-declared nested archive checksums before installation continues.
- Portable / distribution / installer install flows now reject zip path-traversal and symlink entries during extraction.
- Installer-staging package archives can now be built on top of distribution packages.
- Portable/distribution/installer installation flows now emit install receipts into the final install target.
- Installer package archives can now be built on top of installer-staging packages.
- Installer package archives can now be verified through an explicit top-level CLI path.
- Packet replay execution snapshot notifications now flow through the UI dispatcher when one is configured, so replay state changes do not bypass the main-thread scheduler in GUI entry points.
- The Python inline script host now uses a builtins whitelist rather than exposing the full interpreter builtins surface by default.
- MQTT server broker configuration now uses amqtt's explicit `plugins` configuration path, avoiding the deprecated EntryPoint plugin-loading path.
- Offscreen UI smoke now sets a Windows font directory and filters the known offscreen-only `propagateSizeHints` Qt message, so smoke output stays clean while preserving the window show path.
- A project-local CI workflow now exists at `.github/workflows/ci.yml` and mirrors compileall, pytest, headless summary, and build validation.
- Runtime truth is now only partially materialized:
  - logs are continuously written into the workspace
  - replay-plan captures can be written into the workspace
  - log export packaging can now package a real runtime artifact
  - capture/export packaging is still incomplete for the broader runtime artifact set

### Workspace truth

- Verification-time active workspace: `C:\Users\Administrator\Desktop\ProtoLink\workspace\lab-a`
- Persisted settings file: `C:\Users\Administrator\Desktop\ProtoLink\.protolink\app_settings.json`
- Workspace manifest file: `workspace_manifest.json`
- Runtime-generated artifacts currently exist under:
  - `workspace/lab-a/exports/`
  - `workspace/lab-a/profiles/`

### Validation truth (2026-04-10)

- `uv run protolink --headless-summary` -> passed
- `uv run protolink --list-serial-ports` -> passed; no ports reported in this environment
- `uv run protolink --workspace .\\workspace\\lab-a --print-workspace` -> passed
- `uv run protolink --create-export-scaffold log demo .json` -> passed
- `uv run protolink --workspace <temp-workspace> --export-runtime-log bench-runtime` -> passed
- `uv run protolink --workspace <temp-workspace> --export-latest-profile bench-profile` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --generate-smoke-artifacts` -> passed
- `uv run protolink --smoke-check` -> passed
- `uv run protolink --migrate-workspace` -> passed
- `uv run protolink --release-preflight` -> passed
- `uv run protolink --workspace <temp-workspace> --export-release-bundle bench-release` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --prepare-release bench-release` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --package-release bench-release` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-portable-package bench-portable` -> passed
- `uv run protolink --install-portable-package <archive> <target-dir>` -> passed
- `uv run protolink --verify-portable-package <archive>` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-distribution-package bench-distribution` -> passed
- `uv run protolink --install-distribution-package <archive> <staging-dir> <target-dir>` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-staging bench-installer` -> passed
- `uv run protolink --install-installer-staging <archive> <staging-dir> <target-dir>` -> passed
- `uv run protolink --verify-installer-staging <archive>` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-package bench-installer-package` -> passed
- `uv run protolink --verify-installer-package <archive>` -> passed
- `uv run pytest` -> 229 passed
- `uv build` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-package audit-fix` -> passed
- `uv run protolink --verify-installer-package .\\workspace\\lab-a\\exports\\20260410-114315-installer-package-audit-fix.zip` -> passed
- Offscreen Qt smoke -> `smoke-check-ok` with clean output
- Targeted Modbus RTU workflow UI validation passes through `tests/test_ui_modbus_rtu_panel.py`
- Targeted Modbus TCP workflow UI validation passes through `tests/test_ui_modbus_tcp_panel.py`
- Targeted workspace logging validation passes through `tests/test_logging.py` and `tests/test_wiring.py`
- Runtime log export CLI validation passes through `tests/test_app.py` / `tests/test_import_export.py`
- Latest profile export CLI validation passes through `tests/test_app.py`
- Workspace migration baseline validation passes through `tests/test_workspace.py` / `tests/test_app.py`
- Release preflight and release bundle validation now pass through `tests/test_app.py` / `tests/test_import_export.py`
- Smoke-artifact generation validation now passes through `tests/test_app.py`
- Release preparation orchestration validation now passes through `tests/test_app.py`
- Release package archive validation now passes through `tests/test_app.py` / `tests/test_import_export.py`
- Portable package validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Portable package install validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Distribution package validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Distribution package install validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Installer-staging package validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Installer-staging install validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Installer-staging verification validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Installer-package validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Install-receipt validation now passes through `tests/test_packaging.py` / `tests/test_app.py`
- Dedicated RTU workflow acceptance validation passes through `tests/test_modbus_rtu_workflow_acceptance.py`
- Dedicated TCP workflow acceptance validation passes through `tests/test_modbus_tcp_workflow_acceptance.py`
- Drift-regression validation passes through `tests/test_catalog.py` / `tests/test_ui_main_window.py`
- Executable smoke-check validation passes through `--smoke-check`
- Full-suite validation now covers 229 tests and includes the script-host whitelist, config backup, logging isolation, packet replay dispatcher, and packaging schema updates.

## Current judgments (inference from facts)

- Transport foundation is no longer the primary delivery bottleneck.
- The first explicit Modbus RTU product workflow is now closed at the workflow-surface level:
  - explicit owned GUI entry
  - request dispatch
  - packet-inspector linkage
  - decode linkage
  - register-monitor linkage
  - replay-plan export/replay linkage
- The core runtime-truth path for that RTU workflow now exists:
  - workspace-backed logs
  - replay/capture files
  - real log export bundle
  - real capture export bundle from the RTU workflow path
- A dedicated RTU workflow acceptance path now exists.
- A dedicated TCP workflow acceptance path now also exists.
- Code-visible truth drift is reduced but not fully eliminated:
  - implemented transport surfaces are now marked `Bootstrapped`
  - the main-window badge now points at the canonical mainline document instead of a stale hardcoded ID
- The currently active `workspace/lab-a` can now be driven to a preflight-green state through executable release-prep commands.
- The currently active `workspace/lab-a` can now complete a full `--package-release` flow successfully.
- The currently active `workspace/lab-a` can now complete a full `--build-portable-package` flow successfully.
- The currently active `workspace/lab-a` can now complete a full `--build-distribution-package` flow successfully.
- The currently active `workspace/lab-a` can now complete a full installer-staging build/install flow successfully.
- The currently active `workspace/lab-a` can now complete a full installer-package build flow successfully.
- The currently active `workspace/lab-a` can now verify the top-level installer-package archive successfully.
- The packaging line now includes release prep, archive packaging, portable package build/extract/verify, distribution package build/extract, installer-staging package build/extract, installer-package build, install receipts, checksum-validated nested archive installation, safe archive extraction guards, portable manifest-backed checksum truth, and top-level installer-package verification.
- The remaining highest-value product gap is no longer RTU closure, status drift, TCP owned-surface bootstrap, preflight artifact absence, or warning noise; it is proving the installer flow on a clean release-staging machine.

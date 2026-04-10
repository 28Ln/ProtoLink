# ProtoLink Mainline Status

Last rebuilt: 2026-04-10

## Single active mainline

- ID: `BL-002`
- Title: Packaging / release / workspace migration

## Direct product requirement served

This mainline directly serves the product-core requirement that ProtoLink must move from “verified development surface” toward “release-preparable product”.

The current repository already contains:

- validated transport breadth
- packet inspection and raw-byte truth retention
- Modbus RTU/TCP decode baselines
- register-monitor baseline
- replay baseline
- automation/runtime baselines

What is still missing now is explicit release preparation, smoke discipline, and packaging-readiness truth around the workflows that already exist.

Current round update:

- `ML-001` is closed at the workflow-surface level and has been archived
- `NX-001` is closed at the runtime-truth level for the core path and has been archived
- `NX-002` is closed at the acceptance-freeze level and has been archived
- `NX-003` is closed at the implemented-surface drift-cleanup level and has been archived
- `BL-001` is closed at the Modbus TCP workflow-productization level and has been archived
- release-preparation checklist artifacts now exist through `docs/SMOKE_CHECKLIST.md` and `docs/RELEASE_CHECKLIST.md`
- `uv run protolink --smoke-check` now provides an executable smoke-check path
- `uv run protolink --generate-smoke-artifacts` now provides an executable path to materialize runtime artifacts into the active workspace
- `uv run protolink --export-latest-profile` now provides a real profile export path for workspace migration preparation
- `uv run protolink --migrate-workspace` now provides a workspace-migration baseline command
- `uv run protolink --release-preflight` now provides an executable release-preparation report
- `uv run protolink --export-release-bundle` now provides a multi-artifact release bundle path
- `uv run protolink --prepare-release` now provides a one-shot release-preparation orchestration path
- `uv run protolink --package-release` now provides an archive packaging path
- `uv run protolink --build-portable-package` now provides a portable package archive path
- `uv run protolink --install-portable-package` now provides a portable package extraction/install path
- `uv run protolink --verify-portable-package` now provides a portable package verification path
- `uv run protolink --build-distribution-package` now provides a distribution package archive path
- `uv run protolink --install-distribution-package` now provides a distribution package extraction/install path
- `uv run protolink --build-installer-staging` now provides an installer-staging archive path
- `uv run protolink --install-installer-staging` now provides an installer-staging extraction/install path
- `uv run protolink --verify-installer-staging` now provides an installer-staging verification path
- `uv run protolink --verify-installer-package` now provides a top-level installer-package verification path
- release preflight now blocks when capture artifacts are missing instead of reporting a false-positive ready state
- portable package build/install now has a manifest-backed checksum truth surface instead of only loose copied payloads
- distribution / installer install paths now validate nested archive checksums before installation proceeds
- portable / distribution / installer install paths now reject zip path-traversal and symlink entries during extraction
- portable package output now excludes `__pycache__` / `.pyc` residue from copied source payloads
- the current verification baseline is `uv run pytest` -> 209 passed plus targeted RTU/runtime/acceptance/drift/TCP workflow coverage

## Why this is first priority

- It is the next biggest delivery step after the second owned workflow is in place.
- It directly converts verified workflows into explicit release-preparation truth.
- It is required before executable packaging work can be trusted.

## Why not other tasks first

- Not packaging first:
  - release-preparation is now exactly the highest-value task because the second owned workflow exists
- Not wider automation UI first:
  - more automation UI before release-preparation truth would widen surface area faster than delivery readiness

## Current blockers to starting the mainline

- No technical blocker is evidenced in the current codebase.
- The only open blocker is packaging depth: distribution/package archives and install-time checksum gates now exist, but installer-grade packaging/distribution mechanics are still not implemented.

## Tasks blocked by this mainline

- `BL-003` — Script Console UI, Data Tools, and Network Tools boundary

## Next implementation entry

The next iteration must enter through the new release/smoke checklist path, not through unrelated feature expansion.

`Script Console`, `Data Tools`, and `Network Tools` remain explicitly non-blocking for the active release-preparation mainline. They become the next product-expansion boundary only after BL-002 exits with clean release evidence.

BL-003 acceptance must include:

- script execution through the existing whitelisted script host, with stdout/result/error surfaced in the workspace-owned UI
- an obvious stop/disable path before exposing timed tasks, channel bridges, or automation-driven script execution
- deterministic Data Tools unit tests that run without transport or UI state
- Network Tools read-only-first behavior, explicit privileged-command separation, and rollback documentation before any write operation is exposed
- catalog/main-window drift tests when any of the three surfaces move into implemented UI status

Expected entry points:

- `docs/SMOKE_CHECKLIST.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/VALIDATION.md`
- `src/protolink/app.py`
- packaging/release scripts or commands when they are introduced

## Verification gate for mainline exit

At mainline exit, the repository must pass:

- targeted release/smoke verification
- `uv run pytest`
- offscreen Qt smoke
- updated current-state/status/backlog/docs synchronization

BL-003 must additionally preserve these verification paths once it becomes active:

- `uv run pytest tests/test_script_host_service.py tests/test_rule_engine_service.py tests/test_channel_bridge_runtime_service.py -q`
- focused Data Tools tests for conversion/checksum determinism
- focused Network Tools tests proving privileged operations are not invoked by default
- `uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q`

## Documents that must be synchronized when the mainline moves

- `docs/CURRENT_STATE.md`
- `docs/PROJECT_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/VALIDATION.md`
- `README.md`
- `docs/ARCHITECTURE.md` if the owner boundary changes

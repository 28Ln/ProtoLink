# ProtoLink Engineering Tasklist

Last rebuilt: 2026-04-10

## Canonical rules

- This is the only canonical backlog.
- Only one task may remain in `Active`.
- Task IDs are reset in this document. Legacy milestone numbering and legacy local task numbering are retired.
- IDs remain stable when tasks move between sections; they are not renumbered on every promotion/demotion.
- Priority order is fixed as:
  1. product core workflow and real deliverable closure
  2. owner/runtime/config truth unification that blocks that workflow
  3. verification, logging, exception, and configuration closure
  4. documentation truth and handoff stability
  5. UI consistency and performance polish
  6. extensions, experiments, and non-core enhancements
- Archived, Invalid, and Transitional items must not re-enter `Active` without new evidence.

## Active

### BL-002 — Packaging / release / workspace migration

- Why this is first now:
  - RTU and TCP both now have owned workflow surfaces
  - runtime truth exists on the core path
  - dedicated acceptance coverage exists for both RTU and TCP
  - the highest-value remaining gap is turning that verified product surface into a release-preparation path instead of continuing feature sprawl
- Delivery target:
  - release-preparation truth is explicit
  - smoke gates are explicit
  - release blockers are explicit
  - packaging work starts from a verified checklist instead of an implicit narrative
- Current completed slice:
  - `docs/SMOKE_CHECKLIST.md` now exists
  - `docs/RELEASE_CHECKLIST.md` now exists
  - `uv run protolink --smoke-check` now provides an executable smoke-check entry point
  - `uv run protolink --release-preflight` now provides an executable release-preparation report
  - `uv run protolink --export-latest-profile <name>` now provides a real profile-bundle export path for workspace migration/release prep
  - `uv run protolink --migrate-workspace` now provides a workspace-migration baseline
  - `uv run protolink --export-release-bundle <name>` now provides a multi-artifact release bundle path
  - `uv run protolink --generate-smoke-artifacts` now provides an executable path to materialize missing runtime artifacts in the active workspace
  - `uv run protolink --prepare-release <name>` now provides a one-shot release-preparation orchestration path
  - `uv run protolink --package-release <name>` now provides an archive packaging path on top of release preparation
  - `uv run protolink --build-portable-package <name>` now provides a portable package archive path
  - `uv run protolink --install-portable-package <archive> <target-dir>` now provides a portable package extraction/install path
  - `uv run protolink --verify-portable-package <archive>` now provides a portable package verification path
  - `uv run protolink --build-distribution-package <name>` now provides a distribution package archive path
  - `uv run protolink --install-distribution-package <archive> <staging-dir> <target-dir>` now provides a distribution package extraction/install path
  - `uv run protolink --build-installer-staging <name>` now provides an installer-staging archive path
  - `uv run protolink --verify-installer-package <archive>` now provides a top-level installer package verification path
  - release preflight now blocks when capture artifacts are missing instead of reporting a false-positive ready state
  - portable package build output now contains a manifest-backed checksum truth surface and install-time validation
  - distribution / installer-staging / installer-package install paths now validate nested archive checksums before installation
  - portable / distribution / installer install paths now reject zip path-traversal and symlink entries during extraction
  - portable package output now excludes `__pycache__` / `.pyc` residue from copied source payloads
- Immediate next slice:
  - move from source-oriented portable/distribution archives toward runnable installer-grade packaging with stronger provenance and cleaner installed payloads
- Exit evidence:
  - release-preparation checklist and smoke checklist stay synchronized with passing verification
  - full `uv run pytest` still passes
  - current-state/status/backlog docs are synchronized after each packaging-prep slice
- Depends on:
  - `AR-005`
  - `AR-006`
  - `AR-007`
  - `AR-008`
  - `AR-009`
- Blocks:
  - `BL-003`

## Next

### BL-003 — Script Console UI, Data Tools, and Network Tools boundary

- Why here:
  - automation UI should continue to follow the verified owned-workflow line, not outrun release-preparation work
  - Script Console, Data Tools, and Network Tools are product-expansion surfaces, not blockers for the current release-preparation mainline
  - these surfaces must be introduced behind explicit safety and test gates instead of widening the runtime surface opportunistically
- Delivery target:
  - Script Console provides a controlled UI for trusted inline scripts and workflow-bound execution results
  - Data Tools provides independent deterministic conversions, checksums, and format helpers that do not require active transport state
  - Network Tools provides Windows-oriented field helpers with explicit privileged-operation separation and rollback guidance
- Acceptance:
  - Script Console can run a whitelisted Python script through the existing script host, surface stdout/result/error, and attach failures to workspace-visible state
  - Script Console includes a visible stop/disable boundary for long-running or automated execution paths before any timed/channel workflow is exposed through UI
  - Data Tools conversion functions are deterministic and covered by focused unit tests independent of UI and transport sessions
  - Network Tools surfaces do not execute privileged changes without an explicit, auditable command boundary and a documented rollback path
  - all three surfaces have catalog/main-window drift tests when they move from parked/next into implemented UI
- Risk controls:
  - do not expand Python builtins or file/network access from the script host without dedicated security review
  - do not allow automation rules, channel bridges, or timed tasks to run without an obvious stop path and runtime status evidence
  - do not couple Data Tools to transport session state; conversion tests must run headless
  - keep Network Tools read-only first unless a command is deliberately promoted into a privileged workflow with rollback documentation
- Verification:
  - `uv run pytest tests/test_script_host_service.py tests/test_rule_engine_service.py tests/test_channel_bridge_runtime_service.py -q`
  - add focused Data Tools tests before adding the UI surface
  - add Network Tools tests that prove privileged operations are not invoked by default
  - run `uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q` after any catalog or main-window status change
- Depends on:
  - `BL-002`

## Blocked

- No additional blocked items beyond the active backlog ordering.

## Parked

### PK-001 — Data Tools UI surface

- Parked because:
  - useful, but not required to close the first protocol-grade deliverable
  - it should enter through `BL-003` only after deterministic conversion/checksum tests exist

### PK-002 — Network Tools UI surface

- Parked because:
  - field-ops helpers are not the shortest path to product-core closure
  - it should enter through `BL-003` only with read-only-first behavior, explicit privilege boundaries, and rollback guidance

### PK-003 — Deeper transport-specific polish

- Scope examples:
  - richer TCP server per-client tooling
  - deeper MQTT workflow affordances
  - extra transport UX polish
- Parked because:
  - transport breadth already exists; the current gap is workflow closure

### PK-004 — Performance / UI polish

- Parked because:
  - consistency and performance matter, but they do not outrank mainline closure

### PK-005 — 文档 / CLI / UI 中文化统一

- Scope examples:
  - 文档状态面和验证文案统一中文
  - CLI 用户可见错误与帮助文案统一中文
  - GUI 面板与工作流提示去英文残留
- Parked because:
  - 产品最终需要中文统一，但当前仍不应压过 `BL-002` 的交付安全与 installer-grade 主线

## Transitional

### TR-001 — Retire `TASKS.md` from canonical backlog duty

- New status:
  - transitional cleanup completed in this preparation round
- Canonical replacement:
  - `docs/ENGINEERING_TASKLIST.md`

### TR-002 — Retire `docs/STATUS.md` from canonical current-state duty

- New status:
  - transitional cleanup completed in this preparation round
- Canonical replacement:
  - `docs/CURRENT_STATE.md`
  - `docs/PROJECT_STATUS.md`

### TR-003 — Retire stale status labels as active planning inputs

- Affected artifacts:
  - `src/protolink/catalog.py`
  - `src/protolink/ui/main_window.py`
- New status:
  - still present in code, but no longer canonical planning sources
- Cleanup timing:
  - during `ML-001` / `NX-003`, not before

## Rolled back

- No rolled-back ProtoLink tasks are evidenced from repository-local facts.
- Project-local git history now exists under `C:/Users/Administrator/Desktop/ProtoLink`; rollback claims should cite project-local commits and validation evidence.

## Archived

Archived history is summarized in `docs/TASK_ARCHIVE.md`.

### AR-001 — Foundation setup and bootstrap tasks

- Status:
  - archived as completed
- Reason:
  - project skeleton, workspace/settings bootstrapping, CLI shell, event/log plumbing, and packet-inspector shell already exist and are validated

### AR-002 — Transport-core implementation tasks

- Status:
  - archived as completed
- Reason:
  - Serial / TCP / UDP / MQTT adapters, services, panels, profile persistence, and lifecycle validation already exist and are validated

### AR-003 — Shared protocol/workbench baseline tasks

- Status:
  - archived as completed-at-baseline
- Reason:
  - replay, Modbus RTU/TCP decode, register-monitor baseline, auto-response baseline, and device-scan baseline already exist
- Follow-on work:
  - integration/productization now belongs to `ML-001`, not to baseline reimplementation

### AR-004 — Automation infrastructure baseline tasks

- Status:
  - archived as completed-at-baseline
- Reason:
  - rule engine, script host, timed tasks, channel bridge runtime, and capture/replay job service already exist in code and tests

### AR-005 — ML-001 first explicit Modbus RTU workflow closure

- Status:
  - archived as completed
- Reason:
  - the main window now owns a dedicated `Modbus RTU Lab` workflow surface
  - the workflow can compose and dispatch RTU requests, link into packet-inspector decode, seed register monitor points, export replay plans, and replay those plans
  - targeted UI/integration validation exists and the full suite still passes

### AR-006 — NX-001 runtime-truth materialization for logs/captures/export

- Status:
  - archived as completed
- Reason:
  - transport log entries now land in `workspace/logs/transport-events.jsonl`
  - runtime log export packages a real workspace log artifact
  - real replay/capture artifacts can be exported into workspace export bundles from the closed RTU workflow path

### AR-007 — NX-002 RTU workflow acceptance freeze

- Status:
  - archived as completed
- Reason:
  - dedicated acceptance coverage now exists through `tests/test_modbus_rtu_workflow_acceptance.py`
  - validation docs point to that acceptance path explicitly
  - the acceptance contract is now part of the repository truth instead of being implied by scattered tests

### AR-008 — NX-003 implemented-surface drift cleanup

- Status:
  - archived as completed
- Reason:
  - implemented transport surfaces are now marked `Bootstrapped`
  - the main-window badge now points to canonical docs instead of a stale hardcoded mainline ID
  - drift-regression tests now guard the catalog/main-window truth surface

### AR-009 — BL-001 Modbus TCP workflow productization

- Status:
  - archived as completed
- Reason:
  - the main window now owns a dedicated `Modbus TCP Lab` workflow surface
  - the workflow can compose and dispatch TCP requests, link into packet-inspector decode, seed register monitor points, export replay plans, replay them, export capture bundles, and pass a dedicated acceptance test

## Invalid

### IV-001 — “`uv run pytest` = 152 passed”

- Invalid because:
  - verification on 2026-04-10 produced 209 passed

### IV-002 — “capture/replay jobs are still unimplemented”

- Invalid because:
  - `capture_replay_job_service.py`, `capture_replay_jobs.py`, bootstrap wiring, and tests already exist

### IV-003 — “current milestone is M0 -> M1”

- Invalid because:
  - validated code reality is beyond pure transport bootstrap and already includes protocol/workbench and automation baselines

### IV-004 — “transport panels are still the next implementation line”

- Invalid because:
  - the transport panels already exist, are wired, and are covered by passing tests

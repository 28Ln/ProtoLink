# ProtoLink Task Archive

Last rebuilt: 2026-04-09

## Scope

This file holds historical task groups and invalidated historical claims that should no longer drive active planning.

Use this file for context only.

The canonical backlog is `docs/ENGINEERING_TASKLIST.md`.

## Archived completed groups

### AR-001 — Foundation archive

Archived as completed:

- root-level Python project skeleton
- workspace and settings bootstrap
- CLI shell and non-GUI summary path
- event bus and structured logging model
- packet-inspector shell

Why archived:

- these are implemented and validated; they are not current mainline tasks anymore

### AR-002 — Transport-core archive

Archived as completed:

- Serial transport / service / panel
- TCP Client transport / service / panel
- TCP Server transport / service / panel
- UDP transport / service / panel
- MQTT Client transport / service / panel
- MQTT Server transport / service / panel
- shared connection lifecycle base
- transport profile persistence base

Why archived:

- transport breadth already exists and passes current validation

### AR-003 — Shared workbench baseline archive

Archived as completed-at-baseline:

- raw packet composer
- replay plan build/save/load/run baseline
- Modbus RTU decode baseline
- Modbus TCP decode baseline
- register-monitor baseline
- auto-response baseline
- device-scan baseline

Why archived:

- baseline capability exists
- follow-on work is now integration/productization, not baseline re-creation

### AR-004 — Automation infrastructure archive

Archived as completed-at-baseline:

- rule engine
- script host abstraction
- timed task service
- channel bridge runtime service
- capture/replay job service baseline

Why archived:

- code and tests already exist
- current missing work is productization/UI sequencing, not baseline existence

### AR-005 — First explicit Modbus RTU workflow closure

Archived as completed:

- dedicated `Modbus RTU Lab` GUI owner surface
- RTU read-request composition
- serial dispatch through the owned workflow surface
- packet-inspector decode linkage
- register-monitor point seeding
- replay-plan export/replay linkage from the same workflow

Why archived:

- the workflow-surface closure work is done
- the next delivery gap is runtime truth materialization, not RTU workflow ownership

### AR-006 — Runtime truth materialization for the first RTU workflow path

Archived as completed:

- workspace-backed log materialization into `workspace/logs/transport-events.jsonl`
- real runtime log export bundle
- real capture/export bundle path from the closed RTU workflow

Why archived:

- the core runtime artifact path now exists
- the next delivery gap is acceptance freeze, not artifact-path existence

### AR-007 — Acceptance freeze for the first RTU workflow path

Archived as completed:

- dedicated RTU workflow acceptance test
- validation-doc entry for the acceptance path

Why archived:

- the acceptance contract now exists
- the next delivery gap is code-visible truth alignment, not acceptance-path absence

### AR-008 — Implemented-surface drift cleanup

Archived as completed:

- implemented transport surfaces marked `Bootstrapped`
- main-window badge now points to canonical docs instead of a stale hardcoded mainline ID
- drift-regression tests for catalog/main-window truth

Why archived:

- code-visible truth on implemented surfaces is now aligned enough to stop driving the active mainline
- the next delivery gap is owned Modbus TCP productization

### AR-009 — Modbus TCP workflow productization

Archived as completed:

- dedicated `Modbus TCP Lab` GUI surface
- Modbus TCP request composition / dispatch / decode linkage
- register-monitor seeding
- replay-plan export / replay
- capture-bundle export
- dedicated acceptance test

Why archived:

- the second owned workflow now exists at a verified product level
- the next delivery gap is release preparation rather than additional TCP surface bootstrap

## Legacy open items reclassified

### Legacy item: capture-and-replay job baseline

- New classification: `Archived`
- Reason: baseline code, bootstrap wiring, and tests already exist

### Legacy item: automation rule persistence UI affordances beyond the current runtime editor

- New classification: `Blocked`
- Reason: automation UI expansion is not allowed to outrun the first closed Modbus RTU workflow

### Legacy item: script-console workflow surface

- New classification: `Blocked`
- Reason: Script Console UI should follow a frozen automation scope after the first protocol-grade workflow is closed

## Transitional sources retired from canonical use

- `TASKS.md`
- `docs/STATUS.md`
- stale module-status labels in `src/protolink/catalog.py`
- stale milestone badge text in `src/protolink/ui/main_window.py`

## Invalidated historical claims

- “`uv run pytest` = 152 passed”
- “capture/replay jobs are still unimplemented”
- “current milestone is M0 -> M1”
- “transport modules are still the next engineering build line”

## Rolled-back items

- No rolled-back ProtoLink tasks are evidenced from current repository-local facts.
- Project-local git history now exists; future rollback claims should cite project-local commits and validation evidence.

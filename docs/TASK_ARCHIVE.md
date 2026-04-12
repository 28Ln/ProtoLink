# ProtoLink Task Archive

Last rebuilt: 2026-04-12

## Scope

This file stores historical stages, retired aliases, and invalidated claims so they stop polluting the active mainline.

It is not a second backlog.

## Archived completed groups

### Foundation / bootstrap baseline

- Legacy aliases:
  - `AR-001`
- Archived because:
  - root project shell, workspace/settings bootstrap, CLI entry, event bus, structured logging baseline, and packet-inspector shell already exist

### Transport breadth baseline

- Legacy aliases:
  - `AR-002`
- Archived because:
  - Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server breadth already exists

### Shared workbench baseline

- Legacy aliases:
  - `AR-003`
- Archived because:
  - raw packet composer, replay baseline, Modbus RTU/TCP decode baseline, register-monitor baseline, and related shared tooling already exist

### Automation infrastructure baseline

- Legacy aliases:
  - `AR-004`
- Archived because:
  - rule engine, script host abstraction, timed task runtime, channel bridge runtime, and capture/replay job baseline already exist

### RTU owned-workflow closure

- Legacy aliases:
  - `AR-005`
  - `ML-001`
- Archived because:
  - the RTU owner surface and acceptance path already exist

### RTU runtime-truth materialization

- Legacy aliases:
  - `AR-006`
  - `NX-001`
- Archived because:
  - workspace log/capture/export paths already exist for the first RTU workflow line

### RTU acceptance freeze

- Legacy aliases:
  - `AR-007`
  - `NX-002`
- Archived because:
  - the RTU acceptance path already exists

### Implemented-surface drift cleanup

- Legacy aliases:
  - `AR-008`
  - `NX-003`
- Archived because:
  - the first drift-cleanup stage has already been completed

### Modbus TCP owned-workflow productization

- Legacy aliases:
  - `AR-009`
  - `BL-001`
- Archived because:
  - a dedicated Modbus TCP owner surface and acceptance path already exist

### Legacy packaging / release primitive build-out

- Legacy aliases:
  - `BL-002`
- Archived because:
  - packaging, verification, install, and uninstall primitives already exist
  - the active work is no longer primitive creation; it is trusted release truth and baseline freeze

### Owner-surface consistency closure

- Canonical ID:
  - `PL-010`
- Archived because:
  - owner-surface notices, wrapped guidance, CTA gating, and consistency regressions are now explicit and verified

## Retired canonical aliases

These aliases are historical only and must not be used as current planning IDs:

- `ML-*`
- `NX-*`
- `BL-*`
- `PK-*`
- `TR-*`
- `AR-*`
- `IV-*`

## Invalidated historical claims

These statements are no longer current truth:

- “current canonical active mainline is still `BL-002`”
- “current canonical active mainline is still `PL-010`”
- “current validation truth is `152 passed`”
- “current validation truth is `209 passed`”
- “current validation truth is `229 passed`”
- “current validation truth is `239 passed`”
- “current validation truth is `240 passed`”
- “current validation truth is `245 passed`”
- “current validation truth is `246 passed`”
- “current validation truth is `251 passed`”
- “current validation truth is `252 passed`”
- “current validation truth is `255 passed`”
- “current validation truth is `261 passed`”
- “current validation truth is `262 passed`”
- “`TASKS.md` still carries canonical backlog duty”
- “`docs/STATUS.md` still carries canonical current-state duty”

## Rolled-back items

- No rolled-back ProtoLink task is evidenced from the current project-local Git history.

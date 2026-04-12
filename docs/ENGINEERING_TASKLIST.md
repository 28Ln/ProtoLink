# ProtoLink Engineering Tasklist

Last rebuilt: 2026-04-12

## Canonical rules

- This is the only canonical backlog.
- All priorities are derived from product-core needs, not recent edits, local convenience, or task inertia.
- Canonical task IDs use the neutral `PL-###` scheme.
- Legacy IDs such as `ML-*`, `NX-*`, `BL-*`, `PK-*`, `TR-*`, `AR-*`, and `IV-*` are historical aliases only.
- Only one task may remain in `Active`.
- Items in `Archived`, `Invalid`, and `Transitional` cannot re-enter `Active` without new evidence.

## Priority basis

1. Product core mainline, core workflow closure, real delivery capability
2. Architecture boundary / owner closure / runtime truth / context truth / config truth unification
3. Verification closure, tests, logging, exceptions, config/schema standardization
4. Long-term maintainability, handoff, canonical documentation, redundancy cleanup
5. UI consistency and performance polish
6. Expansion surfaces and experimental improvements

## Active

### PL-011 — Carry-over dirty workspace reconciliation

- Classification: `Active`
- Direct product requirement served:
  - restore one trustworthy release-ready baseline and handoff truth after the verified `PL-001` through `PL-010` stack
- Why this is first:
  - `PL-010` exit evidence now exists
  - the repository history is still too thin for the size of the verified delivery/runtime/owner-surface stack
  - further feature or polish work on top of an unreconciled baseline would widen drift and weaken handoff truth
  - product delivery confidence now depends more on baseline reconciliation than on more surface expansion
- Current implementation slice:
  - collapse the validated `PL-001` through `PL-010` stack into one trustworthy baseline handoff point
  - synchronize canonical docs, CI, validation, and mainline truth around that baseline
  - remove ambiguity between active mainline work and historical residue
- Exit evidence:
  - canonical docs, CI, and validation all point to `PL-011`
  - the repository has one verified post-PL-010 baseline handoff point
  - future iterations no longer start from an unreconciled mixed stack

## Next

- No higher-priority follow-on task should activate until `PL-011` establishes the new baseline.

## Parked

- No lower-priority parked task currently outranks the active/next line.

## Rolled back

- No rolled-back ProtoLink task is evidenced from the current project-local Git history.

## Archived

- `PL-001` trusted release gate and preparation freeze -> `Archived` as a completed mainline stage
- `PL-002` clean-machine Windows delivery path -> `Archived` as a completed mainline stage
- `PL-003` runtime/session truth unification -> `Archived` as a completed mainline stage
- `PL-004` verification and engineering standards gate -> `Archived` as a completed mainline stage
- `PL-005` clean release-staging / hardware-in-the-loop sign-off -> `Archived` as a completed mainline stage
- `PL-006` multi-session automation expansion on top of unified runtime truth -> `Archived` as a completed mainline stage
- `PL-007` Script Console owner surface -> `Archived` as a completed mainline stage
- `PL-008` Data Tools owner surface -> `Archived` as a completed mainline stage
- `PL-009` Network Tools owner surface -> `Archived` as a completed mainline stage
- `PL-010` UI consistency / performance / localization polish -> `Archived` as a completed mainline stage
- Legacy foundation / bootstrap line (`AR-001`) -> `Archived`
- Legacy transport breadth line (`AR-002`) -> `Archived`
- Legacy shared workbench baseline line (`AR-003`) -> `Archived`
- Legacy automation infrastructure baseline line (`AR-004`) -> `Archived`
- Legacy RTU workflow closure line (`AR-005`, `ML-001`) -> `Archived`
- Legacy RTU runtime-truth materialization line (`AR-006`, `NX-001`) -> `Archived`
- Legacy RTU acceptance-freeze line (`AR-007`, `NX-002`) -> `Archived`
- Legacy implemented-surface drift cleanup line (`AR-008`, `NX-003`) -> `Archived`
- Legacy Modbus TCP owned-workflow line (`AR-009`, `BL-001`) -> `Archived`
- Legacy packaging / release primitive build-out line (`BL-002`) -> `Archived` as a completed/superseded stage

## Invalid

- Legacy status-coded planning IDs are no longer canonical planning IDs:
  - `ML-*`
  - `NX-*`
  - `BL-*`
  - `PK-*`
  - `TR-*`
  - `AR-*`
  - `IV-*`
- These claims are no longer current truth:
  - “current active mainline is still `BL-002`”
  - “current active mainline is still `PL-010`”
  - “`uv run pytest` current truth is 152 / 209 / 229 / 239 / 240 / 245 / 246 / 251 / 255 / 258 / 261 / 262 passed”
  - “`TASKS.md` still carries canonical backlog duty”
  - “`docs/STATUS.md` still carries canonical current-state duty”

## Transitional

### PL-012 — Legacy alias cleanup in commentary and planning references

- Classification: `Transitional`
- Purpose:
  - remove remaining uses of retired IDs as active planning inputs

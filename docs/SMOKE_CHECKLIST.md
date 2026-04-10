# ProtoLink Smoke Checklist

Last created: 2026-04-09

## Purpose

This checklist is the first release-preparation slice for ProtoLink.

It is intentionally grounded in currently implemented and verified repository facts.

## Environment

- Python 3.11
- `uv`
- UI dependencies installed

## Baseline commands

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run protolink --headless-summary
uv run pytest
```

## Mandatory smoke steps

### 1. Workspace / settings

- Run:

```powershell
uv run protolink --workspace .\workspace\lab-a --print-workspace
```

- Expected:
  - the printed path matches the intended workspace
  - `.protolink/app_settings.json` points at that workspace

### 2. Headless summary

- Run:

```powershell
uv run protolink --headless-summary
```

- Expected:
  - command succeeds
  - transport count is 6
  - module count is 15

### 3. Full regression

- Run:

```powershell
uv run pytest
```

- Expected:
  - full suite passes
  - known warnings are limited to the current aMQTT deprecation warning set

### 4. Offscreen UI smoke

- Preferred executable path:

```powershell
uv run protolink --smoke-check
```

- Or run the explicit offscreen smoke from `docs/VALIDATION.md`

- Expected:
  - `ui-smoke-ok`
  - no crash during bootstrap/show/close

### 5. Runtime truth smoke

- Verify:
  - workspace log file path exists during runtime:
    - `workspace/logs/transport-events.jsonl`
  - if runtime artifacts are missing, generate them:

```powershell
uv run protolink --workspace <workspace-path> --generate-smoke-artifacts
```

  - real runtime log export works:

```powershell
uv run protolink --workspace <workspace-path> --export-runtime-log bench-runtime
```

- Expected:
  - a real bundle is created under `workspace/exports/`
  - payload file is copied from the workspace log file

### 5b. Release preflight smoke

- Run:

```powershell
uv run protolink --release-preflight
```

- Expected:
  - JSON report is printed
  - `manifest_exists` is `true`
  - `smoke_check` is `smoke-check-ok`
  - `ready` is `true` for a release-prep-green workspace

### 6. RTU workflow smoke

- Run:

```powershell
uv run pytest tests/test_modbus_rtu_workflow_acceptance.py -q
```

- Expected:
  - acceptance path passes

### 7. TCP workflow smoke

- Run:

```powershell
uv run pytest tests/test_modbus_tcp_workflow_acceptance.py -q
```

- Expected:
  - acceptance path passes

## Exit condition

The smoke checklist is considered green only if:

- every mandatory step passes
- no new unexpected warning class appears
- current-state/status/backlog documents still match the verified product surface

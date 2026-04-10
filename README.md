# ProtoLink

ProtoLink is a Windows-first local industrial communication and protocol debugging platform.

The current workspace started with two reference projects under `ref/`:

- `llcom`: strong in scripting, flexible transport tooling, rapid field debugging.
- `Wu.CommTool`: strong in modular structure, Modbus workflows, configuration-driven tooling.

This repository now treats those projects as references only. The formal ProtoLink product starts from the root-level Python project and documentation created in this round.

## Product Direction

- Primary platform: Windows desktop
- Primary stack: Python 3.11 + PySide6
- Product goal: unify serial, Modbus, MQTT, TCP/UDP, automation, capture, and configuration workflows in one maintainable desktop platform

## Current State

- `ref/` contains the two analyzed reference projects
- `src/protolink/` contains the formal ProtoLink application shell
- `docs/` contains the canonical current-state, project-status, backlog, mainline, architecture, archive, and validation documents
- `TASKS.md` is now a legacy redirect stub; the canonical backlog lives under `docs/`
- Current validation baseline: `uv run pytest` -> 229 passed
- Project-local CI lives in `.github/workflows/ci.yml` and mirrors compileall, pytest, smoke summary, and build
- Release validation now includes installer-package verification through `uv run protolink --verify-installer-package <archive-path>`

## Quick Start

```powershell
uv sync --python 3.11 --extra dev
uv run protolink --headless-summary
uv run pytest
uv sync --python 3.11 --extra dev --extra ui
uv run protolink
```

## Key Documents

- `docs/CURRENT_STATE.md`
- `docs/PROJECT_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/MAINLINE_STATUS.md`
- `docs/TASK_ARCHIVE.md`
- `docs/SMOKE_CHECKLIST.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/PROJECT_BRIEF.md`
- `docs/REFERENCE_ANALYSIS.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/VALIDATION.md`

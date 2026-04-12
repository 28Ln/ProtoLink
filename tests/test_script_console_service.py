from __future__ import annotations

from pathlib import Path

from protolink.application.script_console_service import ScriptConsoleService
from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.workspace import ensure_workspace_layout


def test_script_console_service_runs_script_and_publishes_workspace_log(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    event_bus = EventBus()
    captured: list[StructuredLogEntry] = []
    event_bus.subscribe(StructuredLogEntry, captured.append)
    host = ScriptHostService()
    host.register_host(PythonInlineScriptHost())
    service = ScriptConsoleService(host, workspace, event_bus=event_bus)

    service.set_code("print(value * 2)\nresult = value + 1")
    service.set_context_text('{"value": 21}')
    result = service.run_script()

    assert result is not None
    assert result.success is True
    assert service.snapshot.last_output.strip() == "42"
    assert service.snapshot.last_result_text == "22"
    assert service.snapshot.last_script_file is not None
    assert Path(service.snapshot.last_script_file).exists()
    assert Path(service.snapshot.last_script_file).parent == workspace.scripts
    run_entries = [entry for entry in captured if entry.category == "automation.script_console.run"]
    assert len(run_entries) == 1


def test_script_console_service_surfaces_context_errors(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    host = ScriptHostService()
    host.register_host(PythonInlineScriptHost())
    service = ScriptConsoleService(host, workspace)

    service.set_code("print('x')")
    service.set_context_text("[1, 2, 3]")
    result = service.run_script()

    assert result is None
    assert service.snapshot.last_error == "Script context must be a JSON object."

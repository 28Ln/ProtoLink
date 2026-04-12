import time

from protolink.application.script_host_service import PythonInlineScriptHost, ScriptHostService
from protolink.core.script_host import ScriptExecutionRequest, ScriptLanguage


def test_script_host_service_executes_python_inline_scripts() -> None:
    service = ScriptHostService()
    service.register_host(PythonInlineScriptHost())

    result = service.execute(
        ScriptExecutionRequest(
            language=ScriptLanguage.PYTHON,
            code="print(value * 2)\nresult = value + 1",
            context={"value": 21},
        )
    )

    assert result.success is True
    assert result.output.strip() == "42"
    assert result.result == 22
    assert service.snapshot.last_language == ScriptLanguage.PYTHON


def test_script_host_service_reports_unregistered_language_and_script_errors() -> None:
    service = ScriptHostService()
    missing = service.execute(
        ScriptExecutionRequest(language=ScriptLanguage.PYTHON, code="print('x')")
    )
    assert missing.success is False
    assert "not registered" in (missing.error or "")

    service.register_host(PythonInlineScriptHost())
    failed = service.execute(
        ScriptExecutionRequest(language=ScriptLanguage.PYTHON, code="raise RuntimeError('boom')")
    )
    assert failed.success is False
    assert failed.error == "boom"


def test_python_inline_host_restricts_dangerous_builtins() -> None:
    service = ScriptHostService()
    service.register_host(PythonInlineScriptHost())

    imported = service.execute(
        ScriptExecutionRequest(language=ScriptLanguage.PYTHON, code="import os\nresult = os.getcwd()")
    )
    assert imported.success is False
    assert "__import__" in (imported.error or "")

    opened = service.execute(
        ScriptExecutionRequest(language=ScriptLanguage.PYTHON, code="result = open('pyproject.toml').read()")
    )
    assert opened.success is False
    assert "open" in (opened.error or "")


def test_python_inline_host_ignores_dunder_context_injection() -> None:
    service = ScriptHostService()
    service.register_host(PythonInlineScriptHost())

    result = service.execute(
        ScriptExecutionRequest(
            language=ScriptLanguage.PYTHON,
            code="result = __builtins__",
            context={"__builtins__": __builtins__},
        )
    )

    assert result.success is True
    assert isinstance(result.result, dict)
    assert "__import__" not in result.result
    assert "open" not in result.result


def test_python_inline_host_times_out_infinite_loops() -> None:
    service = ScriptHostService()
    service.register_host(PythonInlineScriptHost())

    result = service.execute(
        ScriptExecutionRequest(
            language=ScriptLanguage.PYTHON,
            code="while True:\n    pass",
            timeout_seconds=0.1,
        )
    )

    assert result.success is False
    assert result.error == "Script execution timed out after 0.10s."


def test_python_inline_host_times_out_infinite_scripts() -> None:
    service = ScriptHostService()
    service.register_host(PythonInlineScriptHost())

    started = time.monotonic()
    result = service.execute(
        ScriptExecutionRequest(
            language=ScriptLanguage.PYTHON,
            code="while True:\n    pass",
            timeout_seconds=0.2,
        )
    )
    elapsed = time.monotonic() - started

    assert result.success is False
    assert "timed out" in (result.error or "")
    assert elapsed < 1.0

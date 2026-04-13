from __future__ import annotations

import pickle
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from protolink.core.script_host import ScriptExecutionRequest, ScriptExecutionResult, ScriptHost, ScriptLanguage

SAFE_PYTHON_BUILTIN_NAMES: tuple[str, ...] = (
    "abs",
    "all",
    "any",
    "bool",
    "bytes",
    "bytearray",
    "dict",
    "enumerate",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "max",
    "min",
    "print",
    "range",
    "reversed",
    "round",
    "RuntimeError",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "ValueError",
    "zip",
)

DEFAULT_SCRIPT_TIMEOUT_SECONDS = 2.0
MIN_SCRIPT_HOST_STARTUP_GRACE_SECONDS = 0.1
MAX_SCRIPT_HOST_STARTUP_GRACE_SECONDS = 0.35

_PYTHON_INLINE_RUNNER = """
import builtins as _builtins
import contextlib
import io
import pickle
import sys

allowed_names = {allowed_names}
payload = pickle.loads(sys.stdin.buffer.read())
stdout = io.StringIO()
globals_scope = {{"__builtins__": {{name: getattr(_builtins, name) for name in allowed_names}}}}
locals_scope = {{
    str(name): value
    for name, value in payload["context"].items()
    if not str(name).startswith("__")
}}
try:
    with contextlib.redirect_stdout(stdout):
        exec(payload["code"], globals_scope, locals_scope)
except Exception as exc:
    result_payload = {{
        "success": False,
        "output": stdout.getvalue(),
        "error": str(exc),
        "result_pickle": None,
    }}
else:
    result_payload = {{
        "success": True,
        "output": stdout.getvalue(),
        "error": None,
        "result_pickle": None,
    }}
    try:
        result_payload["result_pickle"] = pickle.dumps(locals_scope.get("result"))
    except Exception as exc:
        result_payload["success"] = False
        result_payload["error"] = f"Script result is not serializable: {{exc}}"

sys.stdout.buffer.write(pickle.dumps(result_payload))
""".format(allowed_names=repr(SAFE_PYTHON_BUILTIN_NAMES))


def _normalize_timeout(timeout_seconds: float | None) -> float:
    if timeout_seconds is None or timeout_seconds <= 0:
        return DEFAULT_SCRIPT_TIMEOUT_SECONDS
    return timeout_seconds


def _host_timeout_budget(timeout_seconds: float) -> float:
    startup_grace_seconds = min(
        MAX_SCRIPT_HOST_STARTUP_GRACE_SECONDS,
        max(MIN_SCRIPT_HOST_STARTUP_GRACE_SECONDS, timeout_seconds * 0.5),
    )
    return timeout_seconds + startup_grace_seconds


def _build_serializable_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        str(name): value
        for name, value in context.items()
        if not str(name).startswith("__")
    }


class PythonInlineScriptHost:
    language = ScriptLanguage.PYTHON

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        timeout_seconds = _normalize_timeout(request.timeout_seconds)
        host_timeout_budget = _host_timeout_budget(timeout_seconds)
        try:
            completed = subprocess.run(
                [sys.executable, "-c", _PYTHON_INLINE_RUNNER],
                input=pickle.dumps(
                    {
                        "code": request.code,
                        "context": _build_serializable_context(dict(request.context)),
                    }
                ),
                capture_output=True,
                # Process launch and interpreter cold start are outside the user
                # script body but can consume part of the wall clock budget.
                timeout=host_timeout_budget,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ScriptExecutionResult(
                success=False,
                error=f"Script execution timed out after {timeout_seconds:.2f}s.",
            )
        except Exception as exc:
            return ScriptExecutionResult(
                success=False,
                error=f"Script execution could not start: {exc}",
            )

        if not completed.stdout:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            error_message = stderr or f"Script execution exited without a result (exit code {completed.returncode})."
            return ScriptExecutionResult(
                success=False,
                error=error_message,
            )

        try:
            payload = pickle.loads(completed.stdout)
        except Exception as exc:
            return ScriptExecutionResult(
                success=False,
                error=f"Script result payload could not be decoded: {exc}",
            )

        result_pickle = payload.get("result_pickle")
        try:
            result_value = pickle.loads(result_pickle) if isinstance(result_pickle, bytes) else None
        except Exception as exc:
            return ScriptExecutionResult(
                success=False,
                output=str(payload.get("output", "")),
                error=f"Script result payload could not be decoded: {exc}",
            )

        return ScriptExecutionResult(
            success=bool(payload.get("success")),
            output=str(payload.get("output", "")),
            result=result_value,
            error=str(payload["error"]) if payload.get("error") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ScriptHostSnapshot:
    available_languages: tuple[ScriptLanguage, ...] = ()
    last_language: ScriptLanguage | None = None
    last_error: str | None = None


class ScriptHostService:
    def __init__(self) -> None:
        self._hosts: dict[ScriptLanguage, ScriptHost] = {}
        self._snapshot = ScriptHostSnapshot()

    @property
    def snapshot(self) -> ScriptHostSnapshot:
        return self._snapshot

    def register_host(self, host: ScriptHost) -> None:
        self._hosts[host.language] = host
        self._snapshot = ScriptHostSnapshot(
            available_languages=tuple(sorted(self._hosts, key=lambda item: item.value)),
            last_language=self._snapshot.last_language,
            last_error=self._snapshot.last_error,
        )

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        host = self._hosts.get(request.language)
        if host is None:
            self._snapshot = ScriptHostSnapshot(
                available_languages=self._snapshot.available_languages,
                last_language=request.language,
                last_error=f"Script host '{request.language.value}' is not registered.",
            )
            return ScriptExecutionResult(
                success=False,
                error=f"Script host '{request.language.value}' is not registered.",
            )

        result = host.execute(request)
        self._snapshot = ScriptHostSnapshot(
            available_languages=self._snapshot.available_languages,
            last_language=request.language,
            last_error=result.error,
        )
        return result

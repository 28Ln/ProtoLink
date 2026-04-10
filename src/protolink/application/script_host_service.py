from __future__ import annotations

import contextlib
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from protolink.core.script_host import ScriptExecutionRequest, ScriptExecutionResult, ScriptHost, ScriptLanguage

SAFE_PYTHON_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "bytes": bytes,
    "bytearray": bytearray,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "RuntimeError": RuntimeError,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "ValueError": ValueError,
    "zip": zip,
}


class PythonInlineScriptHost:
    language = ScriptLanguage.PYTHON

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        stdout = io.StringIO()
        globals_scope = {"__builtins__": SAFE_PYTHON_BUILTINS}
        locals_scope: dict[str, Any] = {
            str(name): value
            for name, value in request.context.items()
            if not str(name).startswith("__")
        }
        try:
            with contextlib.redirect_stdout(stdout):
                exec(request.code, globals_scope, locals_scope)
        except Exception as exc:
            return ScriptExecutionResult(
                success=False,
                output=stdout.getvalue(),
                error=str(exc),
            )
        return ScriptExecutionResult(
            success=True,
            output=stdout.getvalue(),
            result=locals_scope.get("result"),
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

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ScriptLanguage(StrEnum):
    PYTHON = "python"


@dataclass(frozen=True, slots=True)
class ScriptExecutionRequest:
    language: ScriptLanguage
    code: str
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScriptExecutionResult:
    success: bool
    output: str = ""
    result: Any = None
    error: str | None = None


class ScriptHost(Protocol):
    language: ScriptLanguage

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        ...

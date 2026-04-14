from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CliExitCode(IntEnum):
    OK = 0
    USER_ERROR = 2
    RUNTIME_ERROR = 3
    GUI_DEPENDENCY_MISSING = 4


@dataclass(frozen=True, slots=True)
class ProtoLinkUserError(Exception):
    message: str
    action: str | None = None
    recovery: str | None = None

    def __str__(self) -> str:
        return self.message


def format_cli_error(error: ProtoLinkUserError, *, fallback_action: str | None = None) -> str:
    action = error.action or fallback_action
    parts: list[str] = []
    if action:
        parts.append(f"{action}失败：")
    parts.append(error.message)
    if error.recovery:
        parts.append(f"恢复建议：{error.recovery}")
    return " ".join(parts)


def format_unexpected_cli_error(action: str, error: Exception) -> str:
    return f"{action}失败：{error}"

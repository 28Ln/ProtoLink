from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    format_version: str
    owner: str | None = None
    truth_boundary: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class JsonObjectLoadResult:
    path: Path
    payload: dict[str, object] | None
    backup_file: Path | None = None
    error_message: str | None = None
    error_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.payload is not None

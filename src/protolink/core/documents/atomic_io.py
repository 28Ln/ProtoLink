from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path

from protolink.core.documents.contracts import JsonObjectLoadResult


def backup_invalid_document_file(path: Path) -> Path | None:
    if not path.exists():
        return None

    for index in range(100):
        suffix = ".invalid" if index == 0 else f".invalid.{index}"
        backup_path = path.with_name(f"{path.name}{suffix}")
        if backup_path.exists():
            continue
        try:
            path.replace(backup_path)
        except OSError:
            return None
        return backup_path
    return None


def load_json_object_file(
    path: Path,
    *,
    empty_error_message: str,
    non_object_error_message: str,
    backup_invalid: bool = True,
) -> JsonObjectLoadResult:
    if not path.exists():
        return JsonObjectLoadResult(path=path, payload=None)

    try:
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError(empty_error_message)
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError(non_object_error_message)
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        backup_file = backup_invalid_document_file(path) if backup_invalid else None
        return JsonObjectLoadResult(
            path=path,
            payload=None,
            backup_file=backup_file,
            error_message=str(exc),
            error_type=type(exc).__name__,
        )

    return JsonObjectLoadResult(path=path, payload=payload)


def write_json_document(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handle, temp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_handle, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False, indent=2))

        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import time
from typing import TypeAlias

ProfileValue: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class PresetProfileDraft:
    values: dict[str, ProfileValue] = field(default_factory=dict)
    selected_preset_name: str | None = None


@dataclass(frozen=True, slots=True)
class PresetProfileEntry:
    name: str
    values: dict[str, ProfileValue] = field(default_factory=dict)


@dataclass(slots=True)
class PresetProfileStore:
    format_version: str
    selected_preset_name: str | None = None
    draft: PresetProfileDraft = field(default_factory=PresetProfileDraft)
    presets: list[PresetProfileEntry] = field(default_factory=list)


def load_preset_profile_store(
    path: Path,
    *,
    format_version: str,
    default_values: dict[str, ProfileValue],
) -> PresetProfileStore:
    if not path.exists():
        return PresetProfileStore(
            format_version=format_version,
            draft=PresetProfileDraft(values=dict(default_values)),
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError("profile store is empty")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("profile store must contain a JSON object")
        if str(data.get("format_version", "")) != format_version:
            raise ValueError("profile store format version is unsupported")
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        _backup_invalid_config_file(path)
        return PresetProfileStore(
            format_version=format_version,
            draft=PresetProfileDraft(values=dict(default_values)),
        )

    draft_data = dict(data.get("draft", {}))
    selected_preset_name = data.get("selected_preset_name")
    draft_selected = draft_data.pop("selected_preset_name", None)

    draft_values = dict(default_values)
    draft_values.update(draft_data)

    presets = [
        PresetProfileEntry(
            name=item["name"],
            values={key: value for key, value in item.items() if key != "name"},
        )
        for item in data.get("presets", [])
        if "name" in item
    ]

    return PresetProfileStore(
        format_version=str(data.get("format_version", format_version)),
        selected_preset_name=selected_preset_name,
        draft=PresetProfileDraft(values=draft_values, selected_preset_name=draft_selected),
        presets=presets,
    )


def save_preset_profile_store(path: Path, profile: PresetProfileStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    draft_payload = dict(profile.draft.values)
    draft_payload["selected_preset_name"] = profile.draft.selected_preset_name
    presets_payload = []
    for preset in profile.presets:
        payload = dict(preset.values)
        payload["name"] = preset.name
        presets_payload.append(payload)

    payload = {
        "format_version": profile.format_version,
        "selected_preset_name": profile.selected_preset_name,
        "draft": draft_payload,
        "presets": presets_payload,
    }
    file_handle, temp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_handle, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))

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


def _backup_invalid_config_file(path: Path) -> Path | None:
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

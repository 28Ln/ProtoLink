from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


MAX_RECENT_WORKSPACES = 8


@dataclass(frozen=True, slots=True)
class SettingsLayout:
    root: Path
    settings_file: Path


@dataclass(slots=True)
class AppSettings:
    active_workspace: str | None = None
    recent_workspaces: list[str] = field(default_factory=list)


def default_settings_root(base_dir: Path) -> Path:
    return base_dir / ".protolink"


def ensure_settings_layout(root: Path) -> SettingsLayout:
    root.mkdir(parents=True, exist_ok=True)
    return SettingsLayout(root=root, settings_file=root / "app_settings.json")


def load_app_settings(layout: SettingsLayout) -> AppSettings:
    if not layout.settings_file.exists():
        return AppSettings()

    try:
        raw_text = layout.settings_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError("settings file is empty")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("settings file must contain a JSON object")
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        _backup_invalid_config_file(layout.settings_file)
        return AppSettings()

    recent_raw = data.get("recent_workspaces", [])
    recent_workspaces = [str(path) for path in recent_raw] if isinstance(recent_raw, list) else []
    active_workspace = data.get("active_workspace")
    return AppSettings(
        active_workspace=str(active_workspace) if active_workspace is not None else None,
        recent_workspaces=recent_workspaces,
    )


def save_app_settings(layout: SettingsLayout, settings: AppSettings) -> None:
    payload = asdict(settings)
    layout.settings_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_workspace_root(base_dir: Path, settings: AppSettings, override: Path | None = None) -> Path:
    if override is not None:
        candidate = override
    elif settings.active_workspace:
        candidate = Path(settings.active_workspace)
    else:
        candidate = base_dir / "workspace"

    return candidate.expanduser().resolve()


def remember_workspace(settings: AppSettings, workspace_root: Path) -> AppSettings:
    normalized = str(workspace_root.resolve())
    recents = [normalized]
    recents.extend(path for path in settings.recent_workspaces if path != normalized)

    return AppSettings(
        active_workspace=normalized,
        recent_workspaces=recents[:MAX_RECENT_WORKSPACES],
    )


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

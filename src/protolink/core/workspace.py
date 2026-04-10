from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_FORMAT_VERSION = "protolink-workspace-v1"
WORKSPACE_MANIFEST_FILE = "workspace_manifest.json"


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    root: Path
    profiles: Path
    devices: Path
    rules: Path
    scripts: Path
    captures: Path
    exports: Path
    logs: Path
    plugins: Path


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    format_version: str
    directories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceMigrationResult:
    from_version: str | None
    to_version: str
    changed: bool
    manifest_file: Path


def default_workspace_root(base_dir: Path) -> Path:
    return base_dir / "workspace"


def ensure_workspace_layout(root: Path) -> WorkspaceLayout:
    root.mkdir(parents=True, exist_ok=True)

    layout = WorkspaceLayout(
        root=root,
        profiles=root / "profiles",
        devices=root / "devices",
        rules=root / "rules",
        scripts=root / "scripts",
        captures=root / "captures",
        exports=root / "exports",
        logs=root / "logs",
        plugins=root / "plugins",
    )

    for path in (
        layout.profiles,
        layout.devices,
        layout.rules,
        layout.scripts,
        layout.captures,
        layout.exports,
        layout.logs,
        layout.plugins,
    ):
        path.mkdir(parents=True, exist_ok=True)

    ensure_workspace_manifest(layout)
    return layout


def workspace_manifest_path(root: Path) -> Path:
    return root / WORKSPACE_MANIFEST_FILE


def build_workspace_manifest(layout: WorkspaceLayout) -> WorkspaceManifest:
    return WorkspaceManifest(
        format_version=WORKSPACE_FORMAT_VERSION,
        directories=("profiles", "devices", "rules", "scripts", "captures", "exports", "logs", "plugins"),
    )


def load_workspace_manifest(root: Path) -> WorkspaceManifest | None:
    manifest_file = workspace_manifest_path(root)
    if not manifest_file.exists():
        return None
    try:
        raw_text = manifest_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError("workspace manifest is empty")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("workspace manifest must contain a JSON object")
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        _backup_invalid_config_file(manifest_file)
        return None

    directories_raw = data.get("directories", ())
    directories = tuple(str(item) for item in directories_raw) if isinstance(directories_raw, (list, tuple)) else ()
    return WorkspaceManifest(
        format_version=str(data.get("format_version", "")),
        directories=directories,
    )


def save_workspace_manifest(layout: WorkspaceLayout, manifest: WorkspaceManifest) -> Path:
    manifest_file = workspace_manifest_path(layout.root)
    manifest_file.write_text(
        json.dumps(
            {
                "format_version": manifest.format_version,
                "directories": list(manifest.directories),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_file


def ensure_workspace_manifest(layout: WorkspaceLayout) -> Path:
    manifest = load_workspace_manifest(layout.root)
    if manifest is not None and manifest.format_version == WORKSPACE_FORMAT_VERSION:
        return workspace_manifest_path(layout.root)
    return save_workspace_manifest(layout, build_workspace_manifest(layout))


def migrate_workspace(root: Path) -> WorkspaceMigrationResult:
    previous = load_workspace_manifest(root)
    previous_version = previous.format_version if previous is not None else None
    layout = ensure_workspace_layout(root)
    manifest_file = workspace_manifest_path(root)
    current = load_workspace_manifest(root)
    changed = previous is None or previous.format_version != WORKSPACE_FORMAT_VERSION
    return WorkspaceMigrationResult(
        from_version=previous_version,
        to_version=current.format_version if current is not None else WORKSPACE_FORMAT_VERSION,
        changed=changed,
        manifest_file=manifest_file,
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

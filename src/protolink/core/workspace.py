from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from protolink.core.documents.atomic_io import load_json_object_file, write_json_document

WORKSPACE_FORMAT_VERSION = "protolink-workspace-v1"
WORKSPACE_MANIFEST_FILE = "workspace_manifest.json"
WorkspaceLoadErrorReporter = Callable[[str, str, Mapping[str, str]], None]


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


def ensure_workspace_layout(
    root: Path,
    *,
    on_error: WorkspaceLoadErrorReporter | None = None,
) -> WorkspaceLayout:
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

    ensure_workspace_manifest(layout, on_error=on_error)
    return layout


def workspace_manifest_path(root: Path) -> Path:
    return root / WORKSPACE_MANIFEST_FILE


def build_workspace_manifest(layout: WorkspaceLayout) -> WorkspaceManifest:
    return WorkspaceManifest(
        format_version=WORKSPACE_FORMAT_VERSION,
        directories=("profiles", "devices", "rules", "scripts", "captures", "exports", "logs", "plugins"),
    )


def load_workspace_manifest(
    root: Path,
    *,
    on_error: WorkspaceLoadErrorReporter | None = None,
) -> WorkspaceManifest | None:
    manifest_file = workspace_manifest_path(root)
    if not manifest_file.exists():
        return None

    result = load_json_object_file(
        manifest_file,
        empty_error_message="workspace manifest is empty",
        non_object_error_message="workspace manifest must contain a JSON object",
    )
    data = result.payload
    if data is None:
        if on_error is not None and result.error_message is not None and result.error_type is not None:
            on_error(
                "workspace_manifest_load_failed",
                result.error_message,
                {
                    "manifest_file": str(manifest_file),
                    "backup_file": str(result.backup_file) if result.backup_file is not None else "",
                    "error_type": result.error_type,
                },
            )
        return None

    directories_raw = data.get("directories", ())
    directories = tuple(str(item) for item in directories_raw) if isinstance(directories_raw, (list, tuple)) else ()
    return WorkspaceManifest(
        format_version=str(data.get("format_version", "")),
        directories=directories,
    )


def save_workspace_manifest(layout: WorkspaceLayout, manifest: WorkspaceManifest) -> Path:
    manifest_file = workspace_manifest_path(layout.root)
    write_json_document(
        manifest_file,
        {
            "format_version": manifest.format_version,
            "directories": list(manifest.directories),
        },
    )
    return manifest_file


def ensure_workspace_manifest(
    layout: WorkspaceLayout,
    *,
    on_error: WorkspaceLoadErrorReporter | None = None,
) -> Path:
    manifest = load_workspace_manifest(layout.root, on_error=on_error)
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


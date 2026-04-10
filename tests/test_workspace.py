from pathlib import Path

import json

from protolink.core.workspace import (
    WORKSPACE_FORMAT_VERSION,
    ensure_workspace_layout,
    load_workspace_manifest,
    workspace_manifest_path,
)


def test_workspace_layout_creates_expected_directories(tmp_path: Path) -> None:
    layout = ensure_workspace_layout(tmp_path / "workspace")

    assert layout.root.exists()
    assert layout.profiles.exists()
    assert layout.devices.exists()
    assert layout.rules.exists()
    assert layout.scripts.exists()
    assert layout.captures.exists()
    assert layout.exports.exists()
    assert layout.logs.exists()
    assert layout.plugins.exists()
    manifest = json.loads(workspace_manifest_path(layout.root).read_text(encoding="utf-8"))
    assert manifest["format_version"] == WORKSPACE_FORMAT_VERSION


def test_workspace_manifest_loader_backs_up_malformed_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_file = workspace_manifest_path(workspace)
    manifest_file.write_text("{not-json", encoding="utf-8")

    assert load_workspace_manifest(workspace) is None

    assert not manifest_file.exists()
    assert (workspace / "workspace_manifest.json.invalid").read_text(encoding="utf-8") == "{not-json"


def test_workspace_layout_recreates_manifest_after_invalid_backup(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_file = workspace_manifest_path(workspace)
    manifest_file.write_text("[]", encoding="utf-8")

    ensure_workspace_layout(workspace)

    assert (workspace / "workspace_manifest.json.invalid").exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["format_version"] == WORKSPACE_FORMAT_VERSION

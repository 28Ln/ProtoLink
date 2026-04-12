from datetime import UTC, datetime
from pathlib import Path

import pytest

from protolink.core.errors import ProtoLinkUserError
from protolink.core.import_export import (
    ArtifactKind,
    build_artifact_timestamp,
    build_export_bundle_plan,
    build_export_manifest,
    build_release_bundle_plan,
    find_latest_artifact_file,
    materialize_release_bundle,
    materialize_export_bundle,
    materialize_export_bundle_from_file,
    normalize_export_extension,
    package_release_bundle,
    resolve_artifact_kind,
    sanitize_artifact_name,
    source_directory_for_kind,
)
from protolink.core.workspace import ensure_workspace_layout


def test_sanitize_artifact_name_normalizes_unsafe_text() -> None:
    assert sanitize_artifact_name("  bench a / capture #1  ") == "bench-a-capture-1"
    assert sanitize_artifact_name("..") == "artifact"


def test_source_directory_for_kind_routes_to_workspace_domains(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")

    assert source_directory_for_kind(workspace, ArtifactKind.CAPTURE) == workspace.captures
    assert source_directory_for_kind(workspace, ArtifactKind.LOG) == workspace.logs
    assert source_directory_for_kind(workspace, ArtifactKind.PROFILE) == workspace.profiles


def test_build_export_bundle_plan_creates_stable_bundle_paths(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    exported_at = datetime(2026, 4, 8, 3, 15, 30, tzinfo=UTC)

    plan = build_export_bundle_plan(
        workspace,
        ArtifactKind.CAPTURE,
        "Bench Port 01",
        ".bin",
        exported_at=exported_at,
    )

    assert plan.source_dir == workspace.captures
    assert plan.bundle_name == "20260408-031530-000000-capture-Bench-Port-01"
    assert plan.bundle_dir == workspace.exports / plan.bundle_name
    assert plan.payload_file == plan.bundle_dir / "Bench-Port-01.bin"
    assert plan.manifest_file == plan.bundle_dir / "manifest.json"


def test_build_artifact_timestamp_includes_microseconds_for_parallel_safety() -> None:
    value = datetime(2026, 4, 8, 3, 15, 30, 456789, tzinfo=UTC)

    assert build_artifact_timestamp(value) == "20260408-031530-456789"


def test_build_export_manifest_reflects_bundle_metadata(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plan = build_export_bundle_plan(workspace, ArtifactKind.LOG, "Session Trace", "json")

    manifest = build_export_manifest(plan)

    assert manifest["format_version"] == "protolink-export-v1"
    assert manifest["kind"] == "log"
    assert manifest["source_dir"] == "logs"
    assert manifest["payload_file"].endswith(".json")


def test_normalize_export_extension_rejects_invalid_values() -> None:
    with pytest.raises(ProtoLinkUserError):
        normalize_export_extension("")

    with pytest.raises(ProtoLinkUserError):
        normalize_export_extension("foo/bar")


def test_materialize_export_bundle_writes_manifest_and_payload(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plan = build_export_bundle_plan(workspace, ArtifactKind.LOG, "Session Trace", ".json")

    manifest = materialize_export_bundle(plan, b"{}")

    assert plan.bundle_dir.exists()
    assert plan.payload_file.read_bytes() == b"{}"
    assert plan.manifest_file.exists()
    assert manifest["bundle_name"] == plan.bundle_name


def test_materialize_export_bundle_from_file_copies_runtime_artifact(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    source_file = workspace.logs / "transport-events.jsonl"
    source_file.write_text('{"entry":1}\n', encoding="utf-8")
    plan = build_export_bundle_plan(workspace, ArtifactKind.LOG, "runtime log", ".jsonl")

    manifest = materialize_export_bundle_from_file(plan, source_file)

    assert plan.payload_file.read_text(encoding="utf-8") == '{"entry":1}\n'
    assert manifest["source_file"] == "transport-events.jsonl"


def test_find_latest_artifact_file_returns_most_recent_source(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "captures"
    artifacts_dir.mkdir(parents=True)
    older = artifacts_dir / "older.json"
    newer = artifacts_dir / "newer.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")

    latest = find_latest_artifact_file(artifacts_dir)

    assert latest == newer


def test_materialize_release_bundle_copies_known_runtime_artifacts(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = workspace.logs / "transport-events.jsonl"
    runtime_log.write_text('{"entry":1}\n', encoding="utf-8")
    capture = workspace.captures / "replay.json"
    capture.write_text('{"steps":[]}\n', encoding="utf-8")
    profile = workspace.profiles / "serial_studio.json"
    profile.write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")

    plan = build_release_bundle_plan(
        workspace,
        "bench release",
        runtime_log_file=runtime_log,
        latest_capture_file=capture,
        latest_profile_file=profile,
    )
    manifest = materialize_release_bundle(plan, preflight_report={"ready": True})

    assert plan.manifest_file.exists()
    assert (plan.bundle_dir / runtime_log.name).exists()
    assert (plan.bundle_dir / capture.name).exists()
    assert (plan.bundle_dir / profile.name).exists()
    assert (plan.bundle_dir / "release-preflight.json").exists()
    assert manifest["format_version"] == "protolink-release-bundle-v1"
    assert manifest["missing_artifact_labels"] == []


def test_package_release_bundle_creates_zip_archive(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "exports" / "demo-release"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (bundle_dir / "artifact.bin").write_bytes(b"demo")

    archive_path = package_release_bundle(bundle_dir)

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"


def test_resolve_artifact_kind_rejects_unknown_values() -> None:
    with pytest.raises(ProtoLinkUserError):
        resolve_artifact_kind("unknown")

from __future__ import annotations

import shutil
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from protolink.core.errors import ProtoLinkUserError
from protolink.core.workspace import WorkspaceLayout


class ArtifactKind(StrEnum):
    CAPTURE = "capture"
    LOG = "log"
    PROFILE = "profile"


@dataclass(frozen=True, slots=True)
class ExportBundlePlan:
    kind: ArtifactKind
    source_dir: Path
    bundle_dir: Path
    payload_file: Path
    manifest_file: Path
    bundle_name: str


@dataclass(frozen=True, slots=True)
class ReleaseBundleArtifact:
    label: str
    source_file: Path
    output_file: Path


@dataclass(frozen=True, slots=True)
class ReleaseBundlePlan:
    bundle_dir: Path
    manifest_file: Path
    bundle_name: str
    artifacts: tuple[ReleaseBundleArtifact, ...]
    missing_artifact_labels: tuple[str, ...]


def build_artifact_timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%d-%H%M%S-%f")


def sanitize_artifact_name(name: str) -> str:
    collapsed = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
    normalized = collapsed.strip("._-")
    return normalized or "artifact"


def source_directory_for_kind(workspace: WorkspaceLayout, kind: ArtifactKind) -> Path:
    if kind == ArtifactKind.CAPTURE:
        return workspace.captures
    if kind == ArtifactKind.LOG:
        return workspace.logs
    return workspace.profiles


def build_export_bundle_plan(
    workspace: WorkspaceLayout,
    kind: ArtifactKind,
    name: str,
    extension: str,
    *,
    exported_at: datetime | None = None,
) -> ExportBundlePlan:
    exported_at = exported_at or datetime.now(UTC)
    sanitized_name = sanitize_artifact_name(name)
    normalized_extension = normalize_export_extension(extension)
    timestamp = build_artifact_timestamp(exported_at)
    bundle_name = f"{timestamp}-{kind.value}-{sanitized_name}"
    bundle_dir = workspace.exports / bundle_name
    payload_file = bundle_dir / f"{sanitized_name}{normalized_extension}"
    manifest_file = bundle_dir / "manifest.json"
    return ExportBundlePlan(
        kind=kind,
        source_dir=source_directory_for_kind(workspace, kind),
        bundle_dir=bundle_dir,
        payload_file=payload_file,
        manifest_file=manifest_file,
        bundle_name=bundle_name,
    )


def build_export_manifest(plan: ExportBundlePlan) -> dict[str, str]:
    return {
        "format_version": "protolink-export-v1",
        "kind": plan.kind.value,
        "bundle_name": plan.bundle_name,
        "source_dir": plan.source_dir.name,
        "payload_file": plan.payload_file.name,
        "manifest_file": plan.manifest_file.name,
    }


def resolve_artifact_kind(value: str) -> ArtifactKind:
    normalized = value.strip().lower()
    try:
        return ArtifactKind(normalized)
    except ValueError as exc:
        supported = ", ".join(kind.value for kind in ArtifactKind)
        raise ProtoLinkUserError(
            f"不支持的导出类型“{value}”。",
            action="创建导出骨架",
            recovery=f"请从以下类型中选择：{supported}。",
        ) from exc


def materialize_export_bundle(plan: ExportBundlePlan, payload: bytes = b"") -> dict[str, str]:
    plan.bundle_dir.mkdir(parents=True, exist_ok=True)
    plan.payload_file.write_bytes(payload)
    manifest = build_export_manifest(plan)
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def materialize_export_bundle_from_file(plan: ExportBundlePlan, source_file: Path) -> dict[str, str]:
    if not source_file.exists() or not source_file.is_file():
        raise ProtoLinkUserError(
            f"未找到源文件“{source_file}”。",
            action="导出工作区产物",
            recovery="请先生成运行期产物后再重试导出。",
        )
    plan.bundle_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_file, plan.payload_file)
    manifest = build_export_manifest(plan)
    manifest["source_file"] = source_file.name
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def find_latest_artifact_file(source_dir: Path) -> Path:
    if not source_dir.exists():
        raise ProtoLinkUserError(
            f"源目录“{source_dir}”不存在。",
            action="定位工作区产物",
            recovery="请先初始化工作区产物目录后再重试。",
        )
    candidates = [path for path in source_dir.iterdir() if path.is_file()]
    if not candidates:
        raise ProtoLinkUserError(
            f"目录“{source_dir}”下没有可导出的产物。",
            action="定位工作区产物",
            recovery="请至少生成一个运行期产物后再导出。",
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_release_bundle_plan(
    workspace: WorkspaceLayout,
    name: str,
    *,
    exported_at: datetime | None = None,
    runtime_log_file: Path | None = None,
    latest_capture_file: Path | None = None,
    latest_profile_file: Path | None = None,
) -> ReleaseBundlePlan:
    exported_at = exported_at or datetime.now(UTC)
    bundle_name = f"{build_artifact_timestamp(exported_at)}-release-{sanitize_artifact_name(name)}"
    bundle_dir = workspace.exports / bundle_name
    manifest_file = bundle_dir / "manifest.json"

    artifact_specs = (
        ("runtime_log", runtime_log_file),
        ("latest_capture", latest_capture_file),
        ("latest_profile", latest_profile_file),
    )
    artifacts: list[ReleaseBundleArtifact] = []
    missing: list[str] = []
    for label, source_file in artifact_specs:
        if source_file is None:
            missing.append(label)
            continue
        artifacts.append(
            ReleaseBundleArtifact(
                label=label,
                source_file=source_file,
                output_file=bundle_dir / source_file.name,
            )
        )
    return ReleaseBundlePlan(
        bundle_dir=bundle_dir,
        manifest_file=manifest_file,
        bundle_name=bundle_name,
        artifacts=tuple(artifacts),
        missing_artifact_labels=tuple(missing),
    )


def materialize_release_bundle(
    plan: ReleaseBundlePlan,
    *,
    preflight_report: dict[str, object] | None = None,
) -> dict[str, object]:
    plan.bundle_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[str] = []
    for artifact in plan.artifacts:
        shutil.copyfile(artifact.source_file, artifact.output_file)
        copied_files.append(artifact.output_file.name)

    if preflight_report is not None:
        preflight_file = plan.bundle_dir / "release-preflight.json"
        preflight_file.write_text(json.dumps(preflight_report, ensure_ascii=False, indent=2), encoding="utf-8")
        copied_files.append(preflight_file.name)

    manifest: dict[str, object] = {
        "format_version": "protolink-release-bundle-v1",
        "bundle_name": plan.bundle_name,
        "artifacts": [
            {
                "label": artifact.label,
                "source_file": artifact.source_file.name,
                "output_file": artifact.output_file.name,
            }
            for artifact in plan.artifacts
        ],
        "missing_artifact_labels": list(plan.missing_artifact_labels),
        "files": copied_files,
    }
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def package_release_bundle(bundle_dir: Path) -> Path:
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        raise ProtoLinkUserError(
            f"未找到发布包目录“{bundle_dir}”。",
            action="打包发布包",
            recovery="请先生成发布包目录后再重试。",
        )
    archive_path = bundle_dir.parent / f"{bundle_dir.name}.zip"
    if archive_path.exists():
        archive_path.unlink()
    archive_base = archive_path.with_suffix("")
    created = shutil.make_archive(str(archive_base), "zip", root_dir=bundle_dir.parent, base_dir=bundle_dir.name)
    return Path(created)


def normalize_export_extension(extension: str) -> str:
    value = extension.strip()
    if not value:
        raise ProtoLinkUserError(
            "导出扩展名不能为空。",
            action="构建导出计划",
            recovery="请提供文件后缀，例如 .json 或 .bin。",
        )
    if any(separator in value for separator in ("/", "\\")):
        raise ProtoLinkUserError(
            "导出扩展名不能包含路径分隔符。",
            action="构建导出计划",
            recovery="请仅填写文件后缀，例如 .json。",
        )
    if value == ".":
        raise ProtoLinkUserError(
            "导出扩展名必须包含文件后缀。",
            action="构建导出计划",
            recovery="请提供后缀，例如 .json 或 .bin。",
        )
    return value if value.startswith(".") else f".{value}"

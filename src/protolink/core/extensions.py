from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from protolink.core.plugin_manifests import (
    PLUGIN_MANIFEST_FILE,
    PLUGIN_MANIFEST_FORMAT_VERSION,
    SUPPORTED_EXTENSION_API_VERSION,
    PluginManifestAuditEntry,
    PluginManifestAuditReport,
    audit_workspace_plugin_manifests,
)


EXTENSION_MANIFEST_FILE = PLUGIN_MANIFEST_FILE
EXTENSION_MANIFEST_FORMAT_VERSION = PLUGIN_MANIFEST_FORMAT_VERSION


@dataclass(frozen=True, slots=True)
class ExtensionManifestIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    plugin_id: str
    display_name: str
    plugin_version: str
    extension_api_version: str
    capabilities: tuple[str, ...]
    entrypoint: str
    min_protolink_version: str
    max_protolink_version: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceExtensionAuditEntry:
    plugin_dir: Path
    manifest_file: Path | None
    status: str
    plugin_id: str | None
    display_name: str | None
    issues: tuple[ExtensionManifestIssue, ...]
    manifest: ExtensionManifest | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceExtensionAuditReport:
    plugin_root: Path
    discovered_count: int
    valid_count: int
    invalid_count: int
    ready: bool
    highest_severity: str
    entries: tuple[WorkspaceExtensionAuditEntry, ...]


def audit_workspace_extensions(plugin_root: Path, *, app_version: str) -> WorkspaceExtensionAuditReport:
    report = audit_workspace_plugin_manifests(plugin_root, app_version=app_version)
    entries = tuple(_convert_entry(entry) for entry in report.entries)
    return WorkspaceExtensionAuditReport(
        plugin_root=report.plugins_root,
        discovered_count=report.plugin_directory_count,
        valid_count=report.valid_manifest_count,
        invalid_count=report.invalid_manifest_count,
        ready=report.ready,
        highest_severity="error" if report.invalid_manifest_count > 0 else "clean",
        entries=entries,
    )


def serialize_extension_audit_report(report: WorkspaceExtensionAuditReport) -> dict[str, object]:
    return {
        "plugin_root": str(report.plugin_root),
        "discovered_count": report.discovered_count,
        "valid_count": report.valid_count,
        "invalid_count": report.invalid_count,
        "ready": report.ready,
        "highest_severity": report.highest_severity,
        "entries": [
            {
                "plugin_dir": str(entry.plugin_dir),
                "manifest_file": str(entry.manifest_file) if entry.manifest_file is not None else None,
                "status": entry.status,
                "plugin_id": entry.plugin_id,
                "display_name": entry.display_name,
                "manifest": (
                    {
                        "plugin_id": entry.manifest.plugin_id,
                        "display_name": entry.manifest.display_name,
                        "plugin_version": entry.manifest.plugin_version,
                        "extension_api_version": entry.manifest.extension_api_version,
                        "capabilities": list(entry.manifest.capabilities),
                        "entrypoint": entry.manifest.entrypoint,
                        "min_protolink_version": entry.manifest.min_protolink_version,
                        "max_protolink_version": entry.manifest.max_protolink_version,
                    }
                    if entry.manifest is not None
                    else None
                ),
                "issues": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "severity": issue.severity,
                    }
                    for issue in entry.issues
                ],
            }
            for entry in report.entries
        ],
    }


def _convert_entry(entry: PluginManifestAuditEntry) -> WorkspaceExtensionAuditEntry:
    issues = tuple(
        [
            *(
                ExtensionManifestIssue(code="extension_manifest_validation_failed", message=message)
                for message in entry.errors
            ),
            *(
                ExtensionManifestIssue(
                    code="extension_manifest_warning",
                    message=message,
                    severity="warning",
                )
                for message in entry.warnings
            ),
        ]
    )
    manifest = None
    if entry.valid:
        assert entry.plugin_id is not None
        assert entry.display_name is not None
        assert entry.plugin_version is not None
        assert entry.extension_api_version is not None
        assert entry.entrypoint is not None
        assert entry.min_app_version is not None
        manifest = ExtensionManifest(
            plugin_id=entry.plugin_id,
            display_name=entry.display_name,
            plugin_version=entry.plugin_version,
            extension_api_version=entry.extension_api_version,
            capabilities=entry.capabilities,
            entrypoint=entry.entrypoint,
            min_protolink_version=entry.min_app_version,
            max_protolink_version=entry.max_app_version,
        )
    return WorkspaceExtensionAuditEntry(
        plugin_dir=entry.plugin_dir,
        manifest_file=entry.manifest_file if entry.manifest_exists else None,
        status="valid" if entry.valid else "invalid",
        plugin_id=entry.plugin_id,
        display_name=entry.display_name,
        issues=issues,
        manifest=manifest,
    )

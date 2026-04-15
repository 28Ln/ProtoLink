from __future__ import annotations

import json
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
EXTENSION_REGISTRY_FILE = "registry.json"
EXTENSION_REGISTRY_FORMAT_VERSION = "protolink-extension-registry-v1"

CLASS_A_CAPABILITIES = {
    "protocol_parser",
    "data_transform",
    "import_export_codec",
    "export_codec",
    "payload_inspector",
}
CLASS_B_CAPABILITIES = {
    "read_only_diagnostic",
    "report_export",
    "workspace_asset_analysis",
}
CLASS_C_CAPABILITIES = {
    "transport_adapter",
    "automation_hook",
    "script_host_integration",
    "ui_surface",
}


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
class ExtensionDescriptor:
    plugin_id: str
    display_name: str
    plugin_version: str
    extension_api_version: str
    capabilities: tuple[str, ...]
    entrypoint: str
    min_protolink_version: str
    max_protolink_version: str | None
    plugin_dir: Path
    manifest_file: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "display_name": self.display_name,
            "plugin_version": self.plugin_version,
            "extension_api_version": self.extension_api_version,
            "capabilities": list(self.capabilities),
            "entrypoint": self.entrypoint,
            "min_protolink_version": self.min_protolink_version,
            "max_protolink_version": self.max_protolink_version,
            "plugin_dir": str(self.plugin_dir),
            "manifest_file": str(self.manifest_file),
        }


@dataclass(frozen=True, slots=True)
class ExtensionRegistryConfig:
    config_file: Path
    exists: bool
    valid: bool
    enabled_plugin_ids: tuple[str, ...]
    disabled_plugin_ids: tuple[str, ...]
    allow_high_risk_plugins: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "config_file": str(self.config_file),
            "exists": self.exists,
            "valid": self.valid,
            "enabled_plugin_ids": list(self.enabled_plugin_ids),
            "disabled_plugin_ids": list(self.disabled_plugin_ids),
            "allow_high_risk_plugins": self.allow_high_risk_plugins,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


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
class ExtensionDescriptorRegistry:
    descriptors: tuple[ExtensionDescriptor, ...]

    @property
    def descriptor_count(self) -> int:
        return len(self.descriptors)

    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(descriptor.plugin_id for descriptor in self.descriptors)

    def capabilities(self) -> tuple[str, ...]:
        seen: list[str] = []
        for descriptor in self.descriptors:
            for capability in descriptor.capabilities:
                if capability not in seen:
                    seen.append(capability)
        return tuple(seen)

    def get(self, plugin_id: str) -> ExtensionDescriptor | None:
        return next((descriptor for descriptor in self.descriptors if descriptor.plugin_id == plugin_id), None)

    def descriptors_for_capability(self, capability: str) -> tuple[ExtensionDescriptor, ...]:
        return tuple(descriptor for descriptor in self.descriptors if capability in descriptor.capabilities)

    def to_dict(self) -> dict[str, object]:
        return {
            "descriptor_count": self.descriptor_count,
            "plugin_ids": list(self.plugin_ids()),
            "capabilities": list(self.capabilities()),
            "descriptors": [descriptor.to_dict() for descriptor in self.descriptors],
        }


@dataclass(frozen=True, slots=True)
class ExtensionLoadingPlanEntry:
    plugin_id: str
    display_name: str
    capability_class: str
    desired_state: str
    effective_state: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "display_name": self.display_name,
            "capability_class": self.capability_class,
            "desired_state": self.desired_state,
            "effective_state": self.effective_state,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ExtensionLoadingPlanReport:
    ready: bool
    descriptor_count: int
    enabled_requested_count: int
    blocked_count: int
    review_required_count: int
    entries: tuple[ExtensionLoadingPlanEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "descriptor_count": self.descriptor_count,
            "enabled_requested_count": self.enabled_requested_count,
            "blocked_count": self.blocked_count,
            "review_required_count": self.review_required_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


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


def build_extension_descriptor_registry(
    report: WorkspaceExtensionAuditReport | PluginManifestAuditReport,
) -> ExtensionDescriptorRegistry:
    if isinstance(report, PluginManifestAuditReport):
        report = audit_workspace_extensions(report.plugins_root, app_version=report.app_version)
    descriptors = tuple(
        ExtensionDescriptor(
            plugin_id=entry.manifest.plugin_id,
            display_name=entry.manifest.display_name,
            plugin_version=entry.manifest.plugin_version,
            extension_api_version=entry.manifest.extension_api_version,
            capabilities=entry.manifest.capabilities,
            entrypoint=entry.manifest.entrypoint,
            min_protolink_version=entry.manifest.min_protolink_version,
            max_protolink_version=entry.manifest.max_protolink_version,
            plugin_dir=entry.plugin_dir,
            manifest_file=entry.manifest_file or (entry.plugin_dir / EXTENSION_MANIFEST_FILE),
        )
        for entry in report.entries
        if entry.manifest is not None and entry.status == "valid"
    )
    return ExtensionDescriptorRegistry(descriptors=descriptors)


def load_extension_registry_config(plugin_root: Path) -> ExtensionRegistryConfig:
    config_file = plugin_root / EXTENSION_REGISTRY_FILE
    if not config_file.exists():
        return ExtensionRegistryConfig(
            config_file=config_file,
            exists=False,
            valid=True,
            enabled_plugin_ids=(),
            disabled_plugin_ids=(),
            allow_high_risk_plugins=False,
            errors=(),
            warnings=(),
        )

    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("extension registry config must contain a JSON object")
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return ExtensionRegistryConfig(
            config_file=config_file,
            exists=True,
            valid=False,
            enabled_plugin_ids=(),
            disabled_plugin_ids=(),
            allow_high_risk_plugins=False,
            errors=(f"{type(exc).__name__}: {exc}",),
            warnings=(),
        )

    format_version = payload.get("format_version")
    if format_version != EXTENSION_REGISTRY_FORMAT_VERSION:
        errors.append(
            f"'format_version' must be '{EXTENSION_REGISTRY_FORMAT_VERSION}', got '{format_version}'."
        )

    enabled_plugin_ids = _read_plugin_id_list(payload.get("enabled_plugin_ids"), "enabled_plugin_ids", errors)
    disabled_plugin_ids = _read_plugin_id_list(payload.get("disabled_plugin_ids"), "disabled_plugin_ids", errors)
    overlap = sorted(set(enabled_plugin_ids) & set(disabled_plugin_ids))
    if overlap:
        errors.append(
            "enabled_plugin_ids and disabled_plugin_ids must not overlap: " + ", ".join(overlap)
        )

    allow_high_risk_plugins = payload.get("allow_high_risk_plugins", False)
    if not isinstance(allow_high_risk_plugins, bool):
        errors.append("'allow_high_risk_plugins' must be a boolean value.")
        allow_high_risk_plugins = False

    return ExtensionRegistryConfig(
        config_file=config_file,
        exists=True,
        valid=not errors,
        enabled_plugin_ids=enabled_plugin_ids,
        disabled_plugin_ids=disabled_plugin_ids,
        allow_high_risk_plugins=allow_high_risk_plugins,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def build_extension_loading_plan(
    registry: ExtensionDescriptorRegistry,
    config: ExtensionRegistryConfig,
) -> ExtensionLoadingPlanReport:
    entries: list[ExtensionLoadingPlanEntry] = []
    blocked_count = 0
    review_required_count = 0
    enabled_requested_count = len(config.enabled_plugin_ids)

    known_plugin_ids = set(registry.plugin_ids())
    for plugin_id in config.enabled_plugin_ids:
        if plugin_id not in known_plugin_ids:
            blocked_count += 1
            entries.append(
                ExtensionLoadingPlanEntry(
                    plugin_id=plugin_id,
                    display_name=plugin_id,
                    capability_class="unknown",
                    desired_state="enabled",
                    effective_state="blocked_unknown_plugin",
                    reasons=("registry.json enabled_plugin_ids includes an unknown plugin_id.",),
                )
            )

    for descriptor in registry.descriptors:
        capability_class = _capability_class(descriptor.capabilities)
        desired_state = (
            "disabled"
            if descriptor.plugin_id in config.disabled_plugin_ids
            else "enabled"
            if descriptor.plugin_id in config.enabled_plugin_ids
            else "described_only"
        )
        effective_state = "described_only"
        reasons: list[str] = []

        if desired_state == "disabled":
            effective_state = "disabled"
            reasons.append("plugin is explicitly listed in disabled_plugin_ids.")
        elif desired_state == "enabled":
            if not config.valid:
                effective_state = "blocked_registry_invalid"
                reasons.append("registry.json is invalid.")
                blocked_count += 1
            elif capability_class == "class_a":
                effective_state = "eligible_for_loading"
                reasons.append("Class A capability set can enter controlled loading next.")
            elif capability_class == "class_b":
                effective_state = "review_required"
                reasons.append("Class B capability set requires explicit review before loading.")
                review_required_count += 1
            elif capability_class == "class_c":
                if config.allow_high_risk_plugins:
                    effective_state = "high_risk_enabled"
                    reasons.append("High-risk plugin is enabled only because allow_high_risk_plugins=true.")
                else:
                    effective_state = "blocked_high_risk"
                    reasons.append("Class C capability set is blocked unless allow_high_risk_plugins=true.")
                    blocked_count += 1
            else:
                effective_state = "blocked_unsupported_capability"
                reasons.append("Capabilities are not mapped to a supported extension class.")
                blocked_count += 1
        else:
            reasons.append("Plugin is described and validated, but not enabled in registry.json.")

        entries.append(
            ExtensionLoadingPlanEntry(
                plugin_id=descriptor.plugin_id,
                display_name=descriptor.display_name,
                capability_class=capability_class,
                desired_state=desired_state,
                effective_state=effective_state,
                reasons=tuple(reasons),
            )
        )

    return ExtensionLoadingPlanReport(
        ready=blocked_count == 0 and config.valid,
        descriptor_count=registry.descriptor_count,
        enabled_requested_count=enabled_requested_count,
        blocked_count=blocked_count,
        review_required_count=review_required_count,
        entries=tuple(entries),
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


def _read_plugin_id_list(raw_value: object, field_name: str, errors: list[str]) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        errors.append(f"'{field_name}' must be a list of plugin ids.")
        return ()
    normalized: list[str] = []
    for item in raw_value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"'{field_name}' must contain non-empty plugin ids.")
            return ()
        value = item.strip()
        normalized.append(value)
    return tuple(dict.fromkeys(normalized))


def _capability_class(capabilities: tuple[str, ...]) -> str:
    if not capabilities:
        return "unsupported"
    if any(capability in CLASS_C_CAPABILITIES for capability in capabilities):
        return "class_c"
    if any(capability in CLASS_B_CAPABILITIES for capability in capabilities):
        return "class_b"
    if all(capability in CLASS_A_CAPABILITIES for capability in capabilities):
        return "class_a"
    return "unsupported"


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

from __future__ import annotations

import importlib
import inspect
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
class ExtensionLoadContext:
    plugin_id: str
    plugin_dir: Path
    manifest_file: Path
    workspace_root: Path
    logs_dir: Path
    exports_dir: Path
    scripts_dir: Path
    app_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_dir": str(self.plugin_dir),
            "manifest_file": str(self.manifest_file),
            "workspace_root": str(self.workspace_root),
            "logs_dir": str(self.logs_dir),
            "exports_dir": str(self.exports_dir),
            "scripts_dir": str(self.scripts_dir),
            "app_version": self.app_version,
        }


@dataclass(frozen=True, slots=True)
class ExtensionRuntimeLoadEntry:
    plugin_id: str
    display_name: str
    effective_state: str
    loaded: bool
    module_name: str | None
    callable_name: str | None
    reasons: tuple[str, ...]
    returned_payload: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "display_name": self.display_name,
            "effective_state": self.effective_state,
            "loaded": self.loaded,
            "module_name": self.module_name,
            "callable_name": self.callable_name,
            "reasons": list(self.reasons),
            "returned_payload": self.returned_payload,
        }


@dataclass(frozen=True, slots=True)
class ExtensionRuntimeLoadReport:
    ready: bool
    attempted_count: int
    loaded_count: int
    failed_count: int
    skipped_count: int
    entries: tuple[ExtensionRuntimeLoadEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "attempted_count": self.attempted_count,
            "loaded_count": self.loaded_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
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


def load_enabled_extensions(
    registry: ExtensionDescriptorRegistry,
    config: ExtensionRegistryConfig,
    loading_plan: ExtensionLoadingPlanReport,
    *,
    workspace_root: Path,
    app_version: str,
) -> ExtensionRuntimeLoadReport:
    descriptor_by_id = {descriptor.plugin_id: descriptor for descriptor in registry.descriptors}
    entries: list[ExtensionRuntimeLoadEntry] = []
    attempted_count = 0
    loaded_count = 0
    failed_count = 0

    for plan_entry in loading_plan.entries:
        descriptor = descriptor_by_id.get(plan_entry.plugin_id)
        if descriptor is None:
            entries.append(
                ExtensionRuntimeLoadEntry(
                    plugin_id=plan_entry.plugin_id,
                    display_name=plan_entry.display_name,
                    effective_state=plan_entry.effective_state,
                    loaded=False,
                    module_name=None,
                    callable_name=None,
                    reasons=plan_entry.reasons,
                    returned_payload=None,
                )
            )
            continue

        if plan_entry.effective_state != "eligible_for_loading":
            entries.append(
                ExtensionRuntimeLoadEntry(
                    plugin_id=descriptor.plugin_id,
                    display_name=descriptor.display_name,
                    effective_state=plan_entry.effective_state,
                    loaded=False,
                    module_name=None,
                    callable_name=None,
                    reasons=plan_entry.reasons,
                    returned_payload=None,
                )
            )
            continue

        attempted_count += 1
        module_name = None
        callable_name = None
        try:
            module_name, callable_name = _split_entrypoint(descriptor.entrypoint)
            context = ExtensionLoadContext(
                plugin_id=descriptor.plugin_id,
                plugin_dir=descriptor.plugin_dir,
                manifest_file=descriptor.manifest_file,
                workspace_root=workspace_root,
                logs_dir=workspace_root / "logs",
                exports_dir=workspace_root / "exports",
                scripts_dir=workspace_root / "scripts",
                app_version=app_version,
            )
            returned_payload = _invoke_extension_entrypoint(descriptor, context)
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            entries.append(
                ExtensionRuntimeLoadEntry(
                    plugin_id=descriptor.plugin_id,
                    display_name=descriptor.display_name,
                    effective_state="load_failed",
                    loaded=False,
                    module_name=module_name,
                    callable_name=callable_name,
                    reasons=(*plan_entry.reasons, f"{type(exc).__name__}: {exc}"),
                    returned_payload=None,
                )
            )
            continue

        loaded_count += 1
        entries.append(
            ExtensionRuntimeLoadEntry(
                plugin_id=descriptor.plugin_id,
                display_name=descriptor.display_name,
                effective_state="loaded",
                loaded=True,
                module_name=module_name,
                callable_name=callable_name,
                reasons=plan_entry.reasons,
                returned_payload=returned_payload,
            )
        )

    skipped_count = len(entries) - attempted_count
    ready_states = {"loaded", "described_only", "disabled"}
    return ExtensionRuntimeLoadReport(
        ready=(
            failed_count == 0
            and config.valid
            and all(entry.effective_state in ready_states for entry in entries)
        ),
        attempted_count=attempted_count,
        loaded_count=loaded_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
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


def _split_entrypoint(entrypoint: str) -> tuple[str, str]:
    if ":" not in entrypoint:
        raise ValueError(f"Entrypoint '{entrypoint}' must use 'module:function' format.")
    module_name, callable_name = entrypoint.split(":", maxsplit=1)
    module_name = module_name.strip()
    callable_name = callable_name.strip()
    if not module_name or not callable_name:
        raise ValueError(f"Entrypoint '{entrypoint}' must use 'module:function' format.")
    return module_name, callable_name


def _invoke_extension_entrypoint(
    descriptor: ExtensionDescriptor,
    context: ExtensionLoadContext,
) -> dict[str, object] | None:
    module_name, callable_name = _split_entrypoint(descriptor.entrypoint)
    with _plugin_runtime_scope(descriptor.plugin_dir, module_name):
        module = importlib.import_module(module_name)
        callback = getattr(module, callable_name)
        if not callable(callback):
            raise TypeError(f"Entrypoint '{descriptor.entrypoint}' is not callable.")
        signature = inspect.signature(callback)
        params = [
            param
            for param in signature.parameters.values()
            if param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD}
        ]
        if len(params) == 0:
            result = callback()
        elif len(params) == 1:
            result = callback(context)
        else:
            raise TypeError("Extension register() must accept zero or one positional argument.")
    return _normalize_runtime_payload(result)


def _normalize_runtime_payload(result: object) -> dict[str, object] | None:
    if result is None:
        return None
    if isinstance(result, Mapping):
        normalized: dict[str, object] = {}
        for key, value in result.items():
            normalized[str(key)] = value
        return normalized
    raise TypeError("Extension register() must return a mapping or None.")


@contextmanager
def _plugin_runtime_scope(plugin_dir: Path, module_name: str):
    plugin_root = plugin_dir.resolve()
    plugin_path = str(plugin_root)
    removed_modules = _remove_conflicting_plugin_modules(module_name, plugin_root)
    sys.path.insert(0, plugin_path)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        if sys.path and sys.path[0] == plugin_path:
            sys.path.pop(0)
        elif plugin_path in sys.path:
            sys.path.remove(plugin_path)
        for name, module in removed_modules.items():
            sys.modules.setdefault(name, module)


def _remove_conflicting_plugin_modules(module_name: str, plugin_root: Path) -> dict[str, object]:
    module_root = module_name.split(".", maxsplit=1)[0]
    module_prefix = f"{module_root}."
    removed_modules: dict[str, object] = {}
    for name, module in list(sys.modules.items()):
        if name != module_root and not name.startswith(module_prefix):
            continue
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue
        try:
            module_path = Path(module_file).resolve()
        except OSError:
            module_path = None
        if module_path is not None and _path_is_within(module_path, plugin_root):
            continue
        removed_modules[name] = module
        sys.modules.pop(name, None)
    return removed_modules


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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

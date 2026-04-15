from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path


PLUGIN_MANIFEST_FILE = "manifest.json"
PLUGIN_MANIFEST_FORMAT_VERSION = "protolink-plugin-manifest-v1"
SUPPORTED_EXTENSION_API_VERSION = "protolink-extension-api-v1"

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_VERSION_PATTERN = re.compile(r"^(?P<core>\d+(?:\.\d+)*)(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, slots=True)
class PluginManifestAuditEntry:
    plugin_dir: Path
    manifest_file: Path
    directory_name: str
    manifest_exists: bool
    valid: bool
    plugin_id: str | None
    display_name: str | None
    plugin_version: str | None
    extension_api_version: str | None
    min_app_version: str | None
    max_app_version: str | None
    entrypoint: str | None
    capabilities: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def with_error(self, message: str) -> PluginManifestAuditEntry:
        if message in self.errors:
            return self
        return replace(
            self,
            valid=False,
            errors=(*self.errors, message),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_dir": str(self.plugin_dir),
            "manifest_file": str(self.manifest_file),
            "directory_name": self.directory_name,
            "manifest_exists": self.manifest_exists,
            "valid": self.valid,
            "plugin_id": self.plugin_id,
            "display_name": self.display_name,
            "plugin_version": self.plugin_version,
            "extension_api_version": self.extension_api_version,
            "min_app_version": self.min_app_version,
            "max_app_version": self.max_app_version,
            "entrypoint": self.entrypoint,
            "capabilities": list(self.capabilities),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class PluginManifestAuditReport:
    plugins_root: Path
    app_version: str
    manifest_file_name: str
    manifest_format_version: str
    supported_extension_api_version: str
    plugin_directory_count: int
    discovered_manifest_count: int
    valid_manifest_count: int
    invalid_manifest_count: int
    warning_count: int
    duplicate_plugin_ids: tuple[str, ...]
    blocking_items: tuple[str, ...]
    ready: bool
    entries: tuple[PluginManifestAuditEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugins_root": str(self.plugins_root),
            "app_version": self.app_version,
            "manifest_file_name": self.manifest_file_name,
            "manifest_format_version": self.manifest_format_version,
            "supported_extension_api_version": self.supported_extension_api_version,
            "plugin_directory_count": self.plugin_directory_count,
            "discovered_manifest_count": self.discovered_manifest_count,
            "valid_manifest_count": self.valid_manifest_count,
            "invalid_manifest_count": self.invalid_manifest_count,
            "warning_count": self.warning_count,
            "duplicate_plugin_ids": list(self.duplicate_plugin_ids),
            "blocking_items": list(self.blocking_items),
            "ready": self.ready,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def audit_workspace_plugin_manifests(
    plugins_root: Path,
    *,
    app_version: str,
) -> PluginManifestAuditReport:
    entries = tuple(
        _audit_plugin_directory(plugin_dir, app_version=app_version)
        for plugin_dir in _iter_plugin_directories(plugins_root)
    )

    duplicate_plugin_ids = _duplicate_plugin_ids(entries)
    if duplicate_plugin_ids:
        mutable_entries = list(entries)
        for plugin_id in duplicate_plugin_ids:
            for index, entry in enumerate(mutable_entries):
                if entry.plugin_id != plugin_id:
                    continue
                mutable_entries[index] = entry.with_error(
                    f"Duplicate plugin_id '{plugin_id}' was declared by multiple plugin directories."
                )
        entries = tuple(mutable_entries)

    discovered_manifest_count = sum(1 for entry in entries if entry.manifest_exists)
    valid_manifest_count = sum(1 for entry in entries if entry.valid)
    invalid_manifest_count = len(entries) - valid_manifest_count
    warning_count = sum(len(entry.warnings) for entry in entries)

    blocking_items: list[str] = []
    if any(not entry.manifest_exists for entry in entries):
        blocking_items.append("plugin_manifest_missing")
    if any(entry.manifest_exists and not entry.valid for entry in entries):
        blocking_items.append("plugin_manifest_validation_failed")

    return PluginManifestAuditReport(
        plugins_root=plugins_root,
        app_version=app_version,
        manifest_file_name=PLUGIN_MANIFEST_FILE,
        manifest_format_version=PLUGIN_MANIFEST_FORMAT_VERSION,
        supported_extension_api_version=SUPPORTED_EXTENSION_API_VERSION,
        plugin_directory_count=len(entries),
        discovered_manifest_count=discovered_manifest_count,
        valid_manifest_count=valid_manifest_count,
        invalid_manifest_count=invalid_manifest_count,
        warning_count=warning_count,
        duplicate_plugin_ids=duplicate_plugin_ids,
        blocking_items=tuple(blocking_items),
        ready=invalid_manifest_count == 0,
        entries=entries,
    )


def _iter_plugin_directories(plugins_root: Path) -> tuple[Path, ...]:
    if not plugins_root.exists() or not plugins_root.is_dir():
        return ()
    try:
        directories = [path for path in plugins_root.iterdir() if path.is_dir()]
    except OSError:
        return ()
    return tuple(sorted(directories, key=lambda path: path.name.lower()))


def _audit_plugin_directory(plugin_dir: Path, *, app_version: str) -> PluginManifestAuditEntry:
    manifest_file = plugin_dir / PLUGIN_MANIFEST_FILE
    errors: list[str] = []
    warnings: list[str] = []

    plugin_id: str | None = None
    display_name: str | None = None
    plugin_version: str | None = None
    extension_api_version: str | None = None
    min_app_version: str | None = None
    max_app_version: str | None = None
    entrypoint: str | None = None
    capabilities: tuple[str, ...] = ()

    if not _PLUGIN_ID_PATTERN.fullmatch(plugin_dir.name):
        errors.append(
            "Plugin directory names must be lowercase ids such as 'modbus-tools' or 'bench_plugin'."
        )

    if not manifest_file.exists():
        errors.append(f"Required plugin manifest '{PLUGIN_MANIFEST_FILE}' was not found.")
        return PluginManifestAuditEntry(
            plugin_dir=plugin_dir,
            manifest_file=manifest_file,
            directory_name=plugin_dir.name,
            manifest_exists=False,
            valid=False,
            plugin_id=plugin_id,
            display_name=display_name,
            plugin_version=plugin_version,
            extension_api_version=extension_api_version,
            min_app_version=min_app_version,
            max_app_version=max_app_version,
            entrypoint=entrypoint,
            capabilities=capabilities,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    payload = _read_manifest_payload(manifest_file, errors)
    if payload is not None:
        format_version = _read_required_string(payload, "format_version", errors)
        if format_version is not None and format_version != PLUGIN_MANIFEST_FORMAT_VERSION:
            errors.append(
                f"'format_version' must be '{PLUGIN_MANIFEST_FORMAT_VERSION}', got '{format_version}'."
            )

        plugin_id = _read_required_string(payload, "plugin_id", errors)
        if plugin_id is not None:
            if not _PLUGIN_ID_PATTERN.fullmatch(plugin_id):
                errors.append(
                    "plugin_id must use lowercase letters, numbers, dots, underscores, or dashes."
                )
            if plugin_id != plugin_dir.name:
                errors.append(
                    f"plugin_id '{plugin_id}' must match the plugin directory name '{plugin_dir.name}'."
                )

        display_name = _read_required_string(payload, "display_name", errors)
        plugin_version = _read_required_string(payload, "plugin_version", errors)
        if plugin_version is not None and _parse_version(plugin_version) is None:
            errors.append(
                f"plugin_version '{plugin_version}' must be a numeric dotted version such as '1.2.3'."
            )

        extension_api_version = _read_alias_string(
            payload,
            canonical_field="extension_api_version",
            legacy_field="api_version",
            required=True,
            errors=errors,
            warnings=warnings,
        )
        if extension_api_version is not None and extension_api_version != SUPPORTED_EXTENSION_API_VERSION:
            errors.append(
                f"extension_api_version must be '{SUPPORTED_EXTENSION_API_VERSION}', got '{extension_api_version}'."
            )

        capabilities = _read_required_string_list(payload, "capabilities", errors)
        entrypoint = _read_required_string(payload, "entrypoint", errors)
        if entrypoint is not None and not _is_valid_entrypoint(entrypoint):
            errors.append("entrypoint must use 'module:function' format.")

        min_app_version = _read_alias_string(
            payload,
            canonical_field="min_app_version",
            legacy_field="min_protolink_version",
            required=True,
            errors=errors,
            warnings=warnings,
        )
        max_app_version = _read_alias_string(
            payload,
            canonical_field="max_app_version",
            legacy_field="max_protolink_version",
            required=False,
            errors=errors,
            warnings=warnings,
        )

        app_version_key = _parse_version(app_version)
        min_app_version_key = _parse_version(min_app_version) if min_app_version is not None else None
        max_app_version_key = _parse_version(max_app_version) if max_app_version is not None else None

        if min_app_version is not None and min_app_version_key is None:
            errors.append(
                f"min_app_version '{min_app_version}' must be a numeric dotted version such as '0.2.5'."
            )
        if max_app_version is not None and max_app_version_key is None:
            errors.append(
                f"max_app_version '{max_app_version}' must be a numeric dotted version such as '0.2.5'."
            )
        if (
            min_app_version_key is not None
            and max_app_version_key is not None
            and min_app_version_key > max_app_version_key
        ):
            errors.append("min_app_version must not be greater than max_app_version.")
        if app_version_key is not None and min_app_version_key is not None and app_version_key < min_app_version_key:
            errors.append(
                f"Current app version '{app_version}' is lower than manifest min_app_version '{min_app_version}'."
            )
        if app_version_key is not None and max_app_version_key is not None and app_version_key > max_app_version_key:
            errors.append(
                f"Current app version '{app_version}' is higher than manifest max_app_version '{max_app_version}'."
            )

    return PluginManifestAuditEntry(
        plugin_dir=plugin_dir,
        manifest_file=manifest_file,
        directory_name=plugin_dir.name,
        manifest_exists=True,
        valid=not errors,
        plugin_id=plugin_id,
        display_name=display_name,
        plugin_version=plugin_version,
        extension_api_version=extension_api_version,
        min_app_version=min_app_version,
        max_app_version=max_app_version,
        entrypoint=entrypoint,
        capabilities=capabilities,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _read_manifest_payload(manifest_file: Path, errors: list[str]) -> dict[str, object] | None:
    try:
        raw_text = manifest_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise ValueError("plugin manifest is empty")
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("plugin manifest must contain a JSON object")
        return payload
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        return None


def _read_required_string(
    payload: dict[str, object],
    field_name: str,
    errors: list[str],
) -> str | None:
    raw_value = payload.get(field_name)
    if raw_value is None:
        errors.append(f"'{field_name}' is required.")
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        errors.append(f"'{field_name}' must be a non-empty string.")
        return None
    return raw_value.strip()


def _read_alias_string(
    payload: dict[str, object],
    *,
    canonical_field: str,
    legacy_field: str,
    required: bool,
    errors: list[str],
    warnings: list[str],
) -> str | None:
    canonical_value = payload.get(canonical_field)
    legacy_value = payload.get(legacy_field)

    canonical_string = _normalize_optional_string(canonical_value, canonical_field, errors)
    legacy_string = _normalize_optional_string(legacy_value, legacy_field, errors)

    if canonical_string is not None and legacy_string is not None and canonical_string != legacy_string:
        errors.append(f"'{canonical_field}' conflicts with legacy field '{legacy_field}'.")
        return canonical_string

    selected = canonical_string if canonical_string is not None else legacy_string
    if selected is None:
        if required:
            errors.append(f"'{canonical_field}' is required.")
        return None

    if canonical_string is None and legacy_string is not None:
        warnings.append(f"'{legacy_field}' is accepted temporarily; rename it to '{canonical_field}'.")
    return selected


def _normalize_optional_string(
    raw_value: object,
    field_name: str,
    errors: list[str],
) -> str | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        errors.append(f"'{field_name}' must be a non-empty string.")
        return None
    return raw_value.strip()


def _read_required_string_list(
    payload: dict[str, object],
    field_name: str,
    errors: list[str],
) -> tuple[str, ...]:
    raw_value = payload.get(field_name)
    if raw_value is None:
        errors.append(f"'{field_name}' is required.")
        return ()
    if not isinstance(raw_value, list) or not raw_value:
        errors.append(f"'{field_name}' must be a non-empty list of strings.")
        return ()

    normalized: list[str] = []
    for item in raw_value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"'{field_name}' must contain only non-empty strings.")
            return ()
        normalized.append(item.strip())
    return tuple(dict.fromkeys(normalized))


def _is_valid_entrypoint(value: str) -> bool:
    if ":" not in value:
        return False
    module_name, callable_name = value.split(":", maxsplit=1)
    return bool(module_name.strip() and callable_name.strip())


def _parse_version(value: str | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    core = match.group("core")
    return tuple(int(part) for part in core.split("."))


def _duplicate_plugin_ids(entries: tuple[PluginManifestAuditEntry, ...]) -> tuple[str, ...]:
    seen: dict[str, int] = {}
    duplicates: set[str] = set()
    for entry in entries:
        if entry.plugin_id is None:
            continue
        count = seen.get(entry.plugin_id, 0) + 1
        seen[entry.plugin_id] = count
        if count > 1:
            duplicates.add(entry.plugin_id)
    return tuple(sorted(duplicates))

import json
from pathlib import Path

from protolink import __version__
from protolink.core.extensions import (
    EXTENSION_REGISTRY_FILE,
    EXTENSION_REGISTRY_FORMAT_VERSION,
    build_extension_descriptor_registry,
    build_extension_loading_plan,
    load_extension_registry_config,
)
from protolink.core.plugin_manifests import (
    PLUGIN_MANIFEST_FILE,
    PLUGIN_MANIFEST_FORMAT_VERSION,
    SUPPORTED_EXTENSION_API_VERSION,
    audit_workspace_plugin_manifests,
)
from protolink.core.workspace import ensure_workspace_layout


def _write_plugin_manifest(plugin_dir: Path, **overrides: object) -> Path:
    manifest = {
        "format_version": PLUGIN_MANIFEST_FORMAT_VERSION,
        "plugin_id": plugin_dir.name,
        "display_name": "Bench Plugin",
        "plugin_version": "1.2.3",
        "extension_api_version": SUPPORTED_EXTENSION_API_VERSION,
        "capabilities": ["protocol_parser", "export_codec"],
        "entrypoint": "bench_plugin.plugin:register",
        "min_app_version": "0.2.0",
    }
    manifest.update(overrides)
    manifest_file = plugin_dir / PLUGIN_MANIFEST_FILE
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_file


def test_audit_workspace_plugin_manifests_reports_valid_entries(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir)

    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)

    assert report.ready is True
    assert report.plugin_directory_count == 1
    assert report.discovered_manifest_count == 1
    assert report.valid_manifest_count == 1
    assert report.invalid_manifest_count == 0
    assert report.blocking_items == ()
    assert report.entries[0].plugin_id == "bench-plugin"
    assert report.entries[0].capabilities == ("protocol_parser", "export_codec")

    registry = build_extension_descriptor_registry(report)
    assert registry.descriptor_count == 1
    assert registry.plugin_ids() == ("bench-plugin",)
    assert registry.capabilities() == ("protocol_parser", "export_codec")
    assert registry.get("bench-plugin") is not None
    assert registry.get("missing-plugin") is None


def test_audit_workspace_plugin_manifests_flags_missing_manifest(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "missing-manifest"
    plugin_dir.mkdir()

    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)

    assert report.ready is False
    assert report.invalid_manifest_count == 1
    assert report.blocking_items == ("plugin_manifest_missing",)
    assert report.entries[0].manifest_exists is False
    assert "Required plugin manifest 'manifest.json' was not found." in report.entries[0].errors


def test_audit_workspace_plugin_manifests_rejects_duplicate_plugin_ids(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    first = workspace.plugins / "bench-plugin"
    second = workspace.plugins / "bench-plugin-copy"
    first.mkdir()
    second.mkdir()
    _write_plugin_manifest(first)
    _write_plugin_manifest(second, plugin_id="bench-plugin")

    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)

    assert report.ready is False
    assert report.invalid_manifest_count == 2
    assert report.duplicate_plugin_ids == ("bench-plugin",)
    assert report.blocking_items == ("plugin_manifest_validation_failed",)
    assert all("Duplicate plugin_id 'bench-plugin'" in " ".join(entry.errors) for entry in report.entries)


def test_audit_workspace_plugin_manifests_accepts_legacy_version_fields_with_warning(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "legacy-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(
        plugin_dir,
        extension_api_version=None,
        min_app_version=None,
        api_version=SUPPORTED_EXTENSION_API_VERSION,
        min_protolink_version="0.2.0",
    )

    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)

    assert report.ready is True
    assert report.warning_count == 2
    assert "api_version" in report.entries[0].warnings[0]
    assert "min_protolink_version" in report.entries[0].warnings[1]


def test_audit_workspace_plugin_manifests_rejects_incompatible_app_version(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "future-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir, min_app_version="9.0.0")

    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)

    assert report.ready is False
    assert report.invalid_manifest_count == 1
    assert report.blocking_items == ("plugin_manifest_validation_failed",)
    assert "Current app version" in report.entries[0].errors[-1]


def test_load_extension_registry_config_reads_enabled_plugins(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": EXTENSION_REGISTRY_FORMAT_VERSION,
                "enabled_plugin_ids": ["bench-plugin"],
                "disabled_plugin_ids": [],
                "allow_high_risk_plugins": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    config = load_extension_registry_config(workspace.plugins)

    assert config.valid is True
    assert config.enabled_plugin_ids == ("bench-plugin",)
    assert config.disabled_plugin_ids == ()


def test_build_extension_loading_plan_blocks_unknown_enabled_plugin(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir)
    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    registry = build_extension_descriptor_registry(report)
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": EXTENSION_REGISTRY_FORMAT_VERSION,
                "enabled_plugin_ids": ["missing-plugin"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config = load_extension_registry_config(workspace.plugins)

    loading_plan = build_extension_loading_plan(registry, config)

    assert loading_plan.ready is False
    assert loading_plan.blocked_count == 1
    assert loading_plan.entries[0].effective_state == "blocked_unknown_plugin"


def test_build_extension_loading_plan_marks_class_b_plugins_for_review(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir, capabilities=["read_only_diagnostic"])
    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    registry = build_extension_descriptor_registry(report)
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": EXTENSION_REGISTRY_FORMAT_VERSION,
                "enabled_plugin_ids": ["bench-plugin"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config = load_extension_registry_config(workspace.plugins)

    loading_plan = build_extension_loading_plan(registry, config)

    assert loading_plan.ready is True
    assert loading_plan.blocked_count == 0
    assert loading_plan.review_required_count == 1
    assert loading_plan.entries[0].capability_class == "class_b"
    assert loading_plan.entries[0].effective_state == "review_required"


def test_build_extension_loading_plan_blocks_high_risk_plugins_without_opt_in(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir, capabilities=["ui_surface"])
    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    registry = build_extension_descriptor_registry(report)
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": EXTENSION_REGISTRY_FORMAT_VERSION,
                "enabled_plugin_ids": ["bench-plugin"],
                "allow_high_risk_plugins": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config = load_extension_registry_config(workspace.plugins)

    loading_plan = build_extension_loading_plan(registry, config)

    assert loading_plan.ready is False
    assert loading_plan.blocked_count == 1
    assert loading_plan.review_required_count == 0
    assert loading_plan.entries[0].capability_class == "class_c"
    assert loading_plan.entries[0].effective_state == "blocked_high_risk"


def test_build_extension_loading_plan_allows_high_risk_plugins_with_opt_in(tmp_path: Path) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir, capabilities=["ui_surface"])
    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    registry = build_extension_descriptor_registry(report)
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": EXTENSION_REGISTRY_FORMAT_VERSION,
                "enabled_plugin_ids": ["bench-plugin"],
                "allow_high_risk_plugins": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config = load_extension_registry_config(workspace.plugins)

    loading_plan = build_extension_loading_plan(registry, config)

    assert loading_plan.ready is True
    assert loading_plan.blocked_count == 0
    assert loading_plan.entries[0].effective_state == "high_risk_enabled"


def test_build_extension_loading_plan_blocks_enabled_plugins_when_registry_config_is_invalid(
    tmp_path: Path,
) -> None:
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    plugin_dir = workspace.plugins / "bench-plugin"
    plugin_dir.mkdir()
    _write_plugin_manifest(plugin_dir)
    report = audit_workspace_plugin_manifests(workspace.plugins, app_version=__version__)
    registry = build_extension_descriptor_registry(report)
    config_file = workspace.plugins / EXTENSION_REGISTRY_FILE
    config_file.write_text(
        json.dumps(
            {
                "format_version": "invalid-format",
                "enabled_plugin_ids": ["bench-plugin"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config = load_extension_registry_config(workspace.plugins)

    loading_plan = build_extension_loading_plan(registry, config)

    assert config.valid is False
    assert loading_plan.ready is False
    assert loading_plan.blocked_count == 1
    assert loading_plan.entries[0].effective_state == "blocked_registry_invalid"

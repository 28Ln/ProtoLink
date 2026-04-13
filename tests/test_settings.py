import protolink.core.settings as settings_module
from pathlib import Path

from protolink.core.logging import RuntimeFailureEvidenceRecorder, default_config_failure_evidence_path, load_config_failure_evidence
from protolink.app import main
from protolink.core.settings import (
    AppSettings,
    PROTOLINK_BASE_DIR_ENV,
    ensure_settings_layout,
    load_app_settings,
    remember_workspace,
    resolve_application_base_dir,
    resolve_workspace_root,
    save_app_settings,
)


def test_save_and_load_settings_round_trip(tmp_path: Path) -> None:
    layout = ensure_settings_layout(tmp_path / ".protolink")
    settings = AppSettings(
        active_workspace=str((tmp_path / "workspace-a").resolve()),
        recent_workspaces=[str((tmp_path / "workspace-a").resolve())],
    )

    save_app_settings(layout, settings)
    loaded = load_app_settings(layout)

    assert loaded.active_workspace == settings.active_workspace
    assert loaded.recent_workspaces == settings.recent_workspaces


def test_remember_workspace_deduplicates_and_prioritizes_latest(tmp_path: Path) -> None:
    first = (tmp_path / "workspace-a").resolve()
    second = (tmp_path / "workspace-b").resolve()
    settings = AppSettings(
        active_workspace=str(first),
        recent_workspaces=[str(first), str(second)],
    )

    updated = remember_workspace(settings, second)

    assert updated.active_workspace == str(second)
    assert updated.recent_workspaces[0] == str(second)
    assert updated.recent_workspaces[1] == str(first)
    assert len(updated.recent_workspaces) == 2


def test_resolve_workspace_root_prefers_override_then_settings_then_default(tmp_path: Path) -> None:
    default_root = (tmp_path / "workspace").resolve()
    settings = AppSettings(active_workspace=str((tmp_path / "saved-workspace").resolve()))
    override = tmp_path / "override-workspace"

    assert resolve_workspace_root(tmp_path, settings, override) == override.resolve()
    assert resolve_workspace_root(tmp_path, settings) == Path(settings.active_workspace)
    assert resolve_workspace_root(tmp_path, AppSettings()) == default_root


def test_headless_summary_does_not_persist_settings_without_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = main(["--headless-summary"])

    assert result == 0
    assert not (tmp_path / ".protolink" / "app_settings.json").exists()


def test_load_settings_backs_up_malformed_file_and_returns_defaults(tmp_path: Path) -> None:
    layout = ensure_settings_layout(tmp_path / ".protolink")
    layout.settings_file.write_text("{not-json", encoding="utf-8")

    loaded = load_app_settings(layout)

    assert loaded == AppSettings()
    assert not layout.settings_file.exists()
    assert (layout.settings_file.parent / "app_settings.json.invalid").read_text(encoding="utf-8") == "{not-json"


def test_load_settings_records_failure_evidence_when_error_reporter_is_configured(tmp_path: Path) -> None:
    layout = ensure_settings_layout(tmp_path / ".protolink")
    layout.settings_file.write_text("{not-json", encoding="utf-8")
    recorder = RuntimeFailureEvidenceRecorder(default_config_failure_evidence_path(layout.root))

    loaded = load_app_settings(
        layout,
        on_error=lambda code, message, details: recorder.append(
            source="settings",
            code=code,
            message=message,
            details=details,
        ),
    )

    evidence_file, evidence_entries, evidence_error = load_config_failure_evidence(layout.root)

    assert loaded == AppSettings()
    assert evidence_error is None
    assert evidence_file is not None
    assert len(evidence_entries) == 1
    assert evidence_entries[0]["source"] == "settings"
    assert evidence_entries[0]["code"] == "settings_load_failed"
    assert evidence_entries[0]["details"]["settings_file"] == str(layout.settings_file)
    assert evidence_entries[0]["details"]["backup_file"].endswith("app_settings.json.invalid")
    assert evidence_entries[0]["details"]["error_type"] == "JSONDecodeError"


def test_load_settings_backs_up_non_object_file_and_returns_defaults(tmp_path: Path) -> None:
    layout = ensure_settings_layout(tmp_path / ".protolink")
    layout.settings_file.write_text("[]", encoding="utf-8")

    loaded = load_app_settings(layout)

    assert loaded == AppSettings()
    assert not layout.settings_file.exists()
    assert (layout.settings_file.parent / "app_settings.json.invalid").exists()


def test_resolve_application_base_dir_prefers_env_override(tmp_path: Path, monkeypatch) -> None:
    override = tmp_path / "portable-root"
    monkeypatch.setenv(PROTOLINK_BASE_DIR_ENV, str(override))

    assert resolve_application_base_dir(tmp_path / "cwd") == override.resolve()


def test_resolve_application_base_dir_detects_bundled_layout(tmp_path: Path, monkeypatch) -> None:
    bundled_root = tmp_path / "bundle"
    fake_settings_file = bundled_root / "sp" / "protolink" / "core" / "settings.py"
    fake_settings_file.parent.mkdir(parents=True, exist_ok=True)
    fake_settings_file.write_text("# test\n", encoding="utf-8")
    (bundled_root / "runtime").mkdir(parents=True, exist_ok=True)
    (bundled_root / "runtime" / "python.exe").write_bytes(b"runtime")
    monkeypatch.setattr(settings_module, "__file__", str(fake_settings_file))

    assert resolve_application_base_dir(tmp_path / "cwd") == bundled_root.resolve()

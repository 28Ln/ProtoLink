from pathlib import Path

from protolink.app import main
from protolink.core.settings import (
    AppSettings,
    ensure_settings_layout,
    load_app_settings,
    remember_workspace,
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


def test_load_settings_backs_up_non_object_file_and_returns_defaults(tmp_path: Path) -> None:
    layout = ensure_settings_layout(tmp_path / ".protolink")
    layout.settings_file.write_text("[]", encoding="utf-8")

    loaded = load_app_settings(layout)

    assert loaded == AppSettings()
    assert not layout.settings_file.exists()
    assert (layout.settings_file.parent / "app_settings.json.invalid").exists()

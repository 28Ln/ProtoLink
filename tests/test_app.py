import hashlib
import json
from pathlib import Path

from protolink.app import main
from protolink.core.errors import CliExitCode, ProtoLinkUserError
from protolink.core.logging import default_workspace_log_path
from protolink.core.packaging import (
    DISTRIBUTION_PACKAGE_FORMAT_VERSION,
    INSTALLER_PACKAGE_FORMAT_VERSION,
    INSTALLER_STAGING_FORMAT_VERSION,
    PORTABLE_MANIFEST_FILE,
    PORTABLE_PACKAGE_FORMAT_VERSION,
)
from protolink.core.workspace import WORKSPACE_MANIFEST_FILE, WORKSPACE_FORMAT_VERSION, ensure_workspace_layout
from protolink.transports.serial import SerialPortSummary


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_portable_archive(archive_file: Path) -> None:
    from zipfile import ZIP_DEFLATED, ZipFile

    file_payloads = {
        "README.md": b"# ProtoLink\n",
        "INSTALL.ps1": b"echo install\n",
    }
    manifest = {
        "format_version": PORTABLE_PACKAGE_FORMAT_VERSION,
        "package_name": archive_file.stem,
        "release_archive_file": "demo-release.zip",
        "archive_file": archive_file.name,
        "install_scripts": ["INSTALL.ps1"],
        "checksums": {
            name: hashlib.sha256(payload).hexdigest()
            for name, payload in {
                **file_payloads,
                "demo-release.zip": b"release-bytes",
            }.items()
        },
        "included_entries": ["README.md", "INSTALL.ps1", "demo-release.zip"],
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in file_payloads.items():
            archive.writestr(name, payload)
        archive.writestr("demo-release.zip", b"release-bytes")
        archive.writestr(PORTABLE_MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))


def test_main_lists_serial_ports_without_bootstrap(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "protolink.app.list_serial_ports",
        lambda: [
            SerialPortSummary(
                device="COM7",
                description="Bench Port",
                hardware_id="USB VID:PID=1234:5678",
            )
        ],
    )
    monkeypatch.setattr(
        "protolink.app.bootstrap_app_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("bootstrap should not run")),
    )

    exit_code = main(["--list-serial-ports"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.OK)
    assert captured.out.strip() == "COM7\tBench Port\tUSB VID:PID=1234:5678"


def test_main_returns_user_error_exit_code_for_expected_cli_failures(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "protolink.app.list_serial_ports",
        lambda: (_ for _ in ()).throw(
            ProtoLinkUserError(
                "Port enumeration is unavailable.",
                action="list serial ports",
                recovery="Check the local driver installation and retry.",
            )
        ),
    )

    exit_code = main(["--list-serial-ports"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "list serial ports failed: Port enumeration is unavailable." in captured.out
    assert "Recovery: Check the local driver installation and retry." in captured.out


def test_main_returns_runtime_error_exit_code_for_unexpected_cli_failures(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "protolink.app.bootstrap_app_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("disk offline")),
    )

    exit_code = main(["--headless-summary"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.RUNTIME_ERROR)
    assert captured.out.strip() == "CLI command failed: disk offline"


def test_main_creates_export_scaffold_under_workspace(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--create-export-scaffold", "log", "bench trace", ".json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["manifest"]["kind"] == "log"
    assert tmp_path.joinpath("workspace", "exports").exists()
    assert Path(payload["payload_file"]).exists()
    assert Path(payload["manifest_file"]).exists()


def test_main_returns_user_error_for_invalid_export_kind(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--create-export-scaffold", "badkind", "bench trace", ".json"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "create export scaffold failed: Unsupported export kind 'badkind'." in captured.out


def test_main_exports_runtime_log_bundle_from_workspace(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = default_workspace_log_path(workspace.logs)
    runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")

    exit_code = main(["--export-runtime-log", "bench runtime"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["manifest"]["kind"] == "log"
    assert Path(payload["payload_file"]).read_text(encoding="utf-8") == '{"category":"transport.message"}\n'
    assert payload["manifest"]["source_file"] == runtime_log.name


def test_main_exports_latest_capture_bundle_from_workspace(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    capture_file = workspace.captures / "20260409-replay-demo.json"
    capture_file.write_text('{"steps":[]}\n', encoding="utf-8")

    exit_code = main(["--export-latest-capture", "bench capture"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["manifest"]["kind"] == "capture"
    assert Path(payload["payload_file"]).read_text(encoding="utf-8") == '{"steps":[]}\n'
    assert payload["manifest"]["source_file"] == capture_file.name


def test_main_exports_latest_profile_bundle_from_workspace(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    profile_file = workspace.profiles / "serial_studio.json"
    profile_file.write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")

    exit_code = main(["--export-latest-profile", "bench profile"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["manifest"]["kind"] == "profile"
    source_file = workspace.profiles / payload["manifest"]["source_file"]
    assert source_file.exists()
    assert Path(payload["payload_file"]).read_text(encoding="utf-8") == source_file.read_text(encoding="utf-8")


def test_main_runs_smoke_check(monkeypatch, capsys) -> None:
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--smoke-check"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.OK)
    assert captured.out.strip() == "smoke-check-ok"


def test_main_migrates_workspace_and_prints_report(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    exit_code = main(["--migrate-workspace"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["workspace"] == str(workspace_root.resolve())
    assert payload["to_version"] == WORKSPACE_FORMAT_VERSION
    assert Path(payload["manifest_file"]).name == WORKSPACE_MANIFEST_FILE
    assert Path(payload["manifest_file"]).exists()


def test_main_runs_release_preflight(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = default_workspace_log_path(workspace.logs)
    runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
    (workspace.captures / "replay.json").write_text('{"steps":[]}\n', encoding="utf-8")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["workspace"] == str(workspace.root.resolve())
    assert payload["manifest_exists"] is True
    assert payload["log_file_exists"] is True
    assert payload["profile_file_count"] >= 1
    assert payload["smoke_check"] == "smoke-check-ok"
    assert payload["blocking_items"] == []
    assert payload["ready"] is True


def test_main_release_preflight_reports_missing_capture_artifacts(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = default_workspace_log_path(workspace.logs)
    runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "capture_artifacts_missing" in payload["blocking_items"]
    assert payload["ready"] is False


def test_main_exports_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = default_workspace_log_path(workspace.logs)
    runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
    (workspace.captures / "replay.json").write_text('{"steps":[]}\n', encoding="utf-8")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--export-release-bundle", "bench release"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    bundle_dir = Path(payload["bundle_dir"])
    assert bundle_dir.exists()
    assert (bundle_dir / "release-preflight.json").exists()
    assert payload["manifest"]["format_version"] == "protolink-release-bundle-v1"


def test_main_generates_smoke_artifacts(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--generate-smoke-artifacts"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["log_file"]).exists()
    assert Path(payload["capture_file"]).exists()
    assert payload["replay_step_count"] >= 1


def test_main_prepares_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--prepare-release", "bench release"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["preflight"]["ready"] is True
    assert payload["generated_artifacts"]["replay_step_count"] == 1
    bundle_dir = Path(payload["bundle_dir"])
    assert bundle_dir.exists()
    assert (bundle_dir / "release-preflight.json").exists()
    assert payload["manifest"]["format_version"] == "protolink-release-bundle-v1"


def test_main_packages_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--package-release", "bench release"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["bundle_dir"]).exists()
    assert Path(payload["archive_file"]).exists()
    assert Path(payload["archive_file"]).suffix == ".zip"


def test_main_builds_portable_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--build-portable-package", "bench portable"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["portable_package_dir"]).exists()
    assert Path(payload["portable_archive_file"]).exists()
    assert Path(payload["portable_archive_file"]).suffix == ".zip"
    assert payload["portable_manifest"]["format_version"] == "protolink-portable-package-v1"


def test_main_installs_portable_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    archive_file = tmp_path / "portable.zip"
    _write_portable_archive(archive_file)

    target_dir = tmp_path / "installed"
    exit_code = main(["--install-portable-package", str(archive_file), str(target_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["target_dir"]).exists()
    assert (target_dir / "README.md").exists()
    assert (target_dir / "INSTALL.ps1").exists()
    assert Path(payload["receipt_file"]).exists()


def test_main_builds_distribution_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--build-distribution-package", "bench distribution"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["distribution_package_dir"]).exists()
    assert Path(payload["distribution_archive_file"]).exists()
    assert Path(payload["distribution_archive_file"]).suffix == ".zip"
    assert payload["distribution_manifest"]["format_version"] == "protolink-distribution-package-v1"


def test_main_installs_distribution_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile

    staging_source = tmp_path / "dist-src"
    staging_source.mkdir(parents=True)
    portable_archive = staging_source / "portable.zip"
    _write_portable_archive(portable_archive)
    release_archive = staging_source / "release.zip"
    release_archive.write_bytes(b"release")
    (staging_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": _sha256_file(portable_archive),
                    "release.zip": _sha256_file(release_archive),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    distribution_archive = tmp_path / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in staging_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    exit_code = main(["--install-distribution-package", str(distribution_archive), str(staging_dir), str(install_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["staging_dir"]).exists()
    assert Path(payload["install_dir"]).exists()
    assert (install_dir / "README.md").exists()
    assert Path(payload["portable_receipt_file"]).exists()


def test_main_builds_installer_staging_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--build-installer-staging", "bench installer"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["installer_package_dir"]).exists()
    assert Path(payload["installer_archive_file"]).exists()
    assert Path(payload["installer_archive_file"]).suffix == ".zip"
    assert payload["installer_manifest"]["format_version"] == "protolink-installer-staging-v1"


def test_main_installs_installer_staging_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile
    import shutil

    installer_source = tmp_path / "installer-src"
    installer_source.mkdir(parents=True)
    portable_archive = installer_source / "portable.zip"
    _write_portable_archive(portable_archive)

    distribution_source = tmp_path / "distribution-src"
    distribution_source.mkdir(parents=True)
    release_archive = distribution_source / "release.zip"
    release_archive.write_bytes(b"release")
    (distribution_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": _sha256_file(portable_archive),
                    "release.zip": _sha256_file(release_archive),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(portable_archive, distribution_source / "portable.zip")
    distribution_archive = installer_source / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in distribution_source.iterdir():
            archive.write(path, arcname=path.name)
    distribution_checksum = _sha256_file(distribution_archive)

    (installer_source / "installer-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                "distribution_archive_file": "distribution.zip",
                "checksum": distribution_checksum,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    installer_archive = tmp_path / "installer.zip"
    with ZipFile(installer_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    exit_code = main(["--install-installer-staging", str(installer_archive), str(staging_dir), str(install_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["staging_dir"]).exists()
    assert Path(payload["install_dir"]).exists()
    assert (install_dir / "README.md").exists()


def test_main_builds_installer_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    (workspace.profiles / "serial_studio.json").write_text('{"format_version":"protolink-serial-studio-v1"}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = default_workspace_log_path(context.workspace.logs)
        runtime_log.write_text('{"category":"transport.message"}\n', encoding="utf-8")
        capture_file = context.workspace.captures / "release-smoke.json"
        capture_file.write_text('{"steps":[]}\n', encoding="utf-8")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 1,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--build-installer-package", "bench installer package"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["installer_package_dir"]).exists()
    assert Path(payload["installer_archive_file"]).exists()
    assert Path(payload["installer_archive_file"]).suffix == ".zip"
    assert payload["installer_manifest"]["format_version"] == "protolink-installer-package-v1"


def test_main_installs_installer_package_through_clean_release_staging(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile
    import shutil

    installer_source = tmp_path / "installer-package-src"
    installer_source.mkdir(parents=True)

    portable_archive = installer_source / "portable.zip"
    _write_portable_archive(portable_archive)

    distribution_source = tmp_path / "distribution-src"
    distribution_source.mkdir(parents=True)
    release_archive = distribution_source / "release.zip"
    release_archive.write_bytes(b"release")
    (distribution_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": _sha256_file(portable_archive),
                    "release.zip": _sha256_file(release_archive),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(portable_archive, distribution_source / "portable.zip")
    distribution_archive = installer_source / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in distribution_source.iterdir():
            archive.write(path, arcname=path.name)
    distribution_checksum = _sha256_file(distribution_archive)

    installer_staging_source = tmp_path / "installer-staging-src"
    installer_staging_source.mkdir(parents=True)
    (installer_staging_source / "installer-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                "distribution_archive_file": "distribution.zip",
                "checksum": distribution_checksum,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(distribution_archive, installer_staging_source / "distribution.zip")
    installer_staging_archive = installer_source / "installer-staging.zip"
    with ZipFile(installer_staging_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_staging_source.iterdir():
            archive.write(path, arcname=path.name)
    installer_staging_checksum = _sha256_file(installer_staging_archive)

    (installer_source / "installer-package-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                "installer_staging_archive_file": "installer-staging.zip",
                "checksum": installer_staging_checksum,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    installer_archive = tmp_path / "installer-package.zip"
    with ZipFile(installer_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    assert not staging_dir.exists()
    assert not install_dir.exists()

    exit_code = main(["--install-installer-package", str(installer_archive), str(staging_dir), str(install_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert Path(payload["staging_dir"]).exists()
    assert Path(payload["install_dir"]).exists()
    assert (staging_dir / "installer-package-manifest.json").exists()
    assert (staging_dir / "installer-staging" / "installer-manifest.json").exists()
    assert (staging_dir / "installer-staging" / "distribution" / "distribution-manifest.json").exists()
    assert (install_dir / "README.md").exists()
    assert (install_dir / "INSTALL.ps1").exists()
    receipt_file = Path(payload["portable_receipt_file"])
    assert receipt_file == install_dir / "install-receipt.json"
    assert receipt_file.exists()
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["format_version"] == "protolink-install-receipt-v1"
    assert {"README.md", "INSTALL.ps1", "demo-release.zip"} <= set(receipt["extracted_entries"])


def test_main_rejects_installer_package_with_checksum_mismatch(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile
    import shutil

    installer_source = tmp_path / "installer-package-src"
    installer_source.mkdir(parents=True)
    portable_archive = installer_source / "portable.zip"
    _write_portable_archive(portable_archive)

    distribution_source = tmp_path / "distribution-src"
    distribution_source.mkdir(parents=True)
    release_archive = distribution_source / "release.zip"
    release_archive.write_bytes(b"release")
    (distribution_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": _sha256_file(portable_archive),
                    "release.zip": _sha256_file(release_archive),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(portable_archive, distribution_source / "portable.zip")
    distribution_archive = installer_source / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in distribution_source.iterdir():
            archive.write(path, arcname=path.name)
    distribution_checksum = _sha256_file(distribution_archive)

    installer_staging_source = tmp_path / "installer-staging-src"
    installer_staging_source.mkdir(parents=True)
    (installer_staging_source / "installer-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                "distribution_archive_file": "distribution.zip",
                "checksum": distribution_checksum,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(distribution_archive, installer_staging_source / "distribution.zip")
    installer_staging_archive = installer_source / "installer-staging.zip"
    with ZipFile(installer_staging_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_staging_source.iterdir():
            archive.write(path, arcname=path.name)

    (installer_source / "installer-package-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                "installer_staging_archive_file": "installer-staging.zip",
                "checksum": _sha256_file(installer_staging_archive)[:-1] + "0",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    installer_archive = tmp_path / "installer-package.zip"
    with ZipFile(installer_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    exit_code = main(["--install-installer-package", str(installer_archive), str(staging_dir), str(install_dir)])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "checksum mismatch" in captured.out


def test_main_verifies_installer_staging_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile
    import hashlib

    archive_file = tmp_path / "installer.zip"
    distribution_bytes = b"distribution"
    checksum = hashlib.sha256(distribution_bytes).hexdigest()
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-manifest.json",
            json.dumps(
                {
                    "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                    "distribution_archive_file": "distribution.zip",
                    "checksum": checksum,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("distribution.zip", distribution_bytes)
        archive.writestr("Install-Distribution.ps1", "echo install\n")
        archive.writestr("Install-Distribution.bat", "echo install\r\n")

    exit_code = main(["--verify-installer-staging", str(archive_file)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["checksum_matches"] is True
    assert set(payload["install_scripts_present"]) == {"Install-Distribution.ps1", "Install-Distribution.bat"}


def test_main_verifies_installer_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile

    archive_file = tmp_path / "installer-package.zip"
    installer_staging_bytes = b"installer-staging"
    checksum = hashlib.sha256(installer_staging_bytes).hexdigest()
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-package-manifest.json",
            json.dumps(
                {
                    "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                    "installer_staging_archive_file": "installer-staging.zip",
                    "checksum": checksum,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("installer-staging.zip", installer_staging_bytes)
        archive.writestr("Install-ProtoLink.ps1", "echo install\n")
        archive.writestr("Install-ProtoLink.bat", "echo install\r\n")

    exit_code = main(["--verify-installer-package", str(archive_file)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["checksum_matches"] is True
    assert set(payload["install_scripts_present"]) == {"Install-ProtoLink.ps1", "Install-ProtoLink.bat"}


def test_main_verifies_portable_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    archive_file = tmp_path / "portable.zip"
    _write_portable_archive(archive_file)

    exit_code = main(["--verify-portable-package", str(archive_file)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["checksum_matches"] is True
    assert payload["portable_manifest_file"] == PORTABLE_MANIFEST_FILE
    assert payload["release_archive_file"] == "demo-release.zip"


def test_main_verifies_distribution_package(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    from zipfile import ZIP_DEFLATED, ZipFile

    archive_file = tmp_path / "distribution.zip"
    portable_bytes = b"portable-archive"
    release_bytes = b"release-archive"
    checksum_map = {
        "portable.zip": hashlib.sha256(portable_bytes).hexdigest(),
        "release.zip": hashlib.sha256(release_bytes).hexdigest(),
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "distribution-manifest.json",
            json.dumps(
                {
                    "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                    "portable_archive_file": "portable.zip",
                    "release_archive_file": "release.zip",
                    "checksums": checksum_map,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("portable.zip", portable_bytes)
        archive.writestr("release.zip", release_bytes)

    exit_code = main(["--verify-distribution-package", str(archive_file)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["checksum_matches"] is True
    assert payload["distribution_manifest_file"] == "distribution-manifest.json"
    assert payload["portable_archive_file"] == "portable.zip"
    assert payload["release_archive_file"] == "release.zip"

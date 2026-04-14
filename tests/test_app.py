import hashlib
import json
import os
from pathlib import Path
import tempfile

from protolink.app import main
from protolink.core.logging import create_log_entry, LogLevel
from protolink.core.errors import CliExitCode, ProtoLinkUserError
from protolink.core.logging import (
    default_config_failure_evidence_path,
    default_runtime_failure_evidence_path,
    default_workspace_log_path,
    load_config_failure_evidence,
    load_runtime_failure_evidence,
    serialize_log_entry,
)
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


def _write_valid_runtime_log(workspace) -> Path:
    runtime_log = default_workspace_log_path(workspace.logs)
    session_id = "bench-session"
    entries = [
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Outbound payload (6 bytes)",
            session_id=session_id,
            transport_kind="serial",
            raw_payload=b"\x01\x03\x00\x0A\x00\x02",
            metadata={"source": "release_smoke", "protocol": "modbus_rtu"},
        ),
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (6 bytes)",
            session_id=session_id,
            transport_kind="serial",
            raw_payload=b"\x01\x03\x00\x0A\x00\x02",
            metadata={"source": "serial"},
        ),
    ]
    runtime_log.write_text(
        "".join(json.dumps(serialize_log_entry(entry), ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return runtime_log


def _write_valid_serial_profile(workspace) -> Path:
    profile_file = workspace.profiles / "serial_studio.json"
    profile_file.write_text(
        json.dumps(
            {
                "format_version": "protolink-serial-studio-v1",
                "selected_preset_name": None,
                "draft": {
                    "target": "loop://",
                    "baudrate": 9600,
                    "send_mode": "hex",
                    "line_ending": "none",
                    "send_text": "",
                    "selected_preset_name": None,
                },
                "presets": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return profile_file


def _write_valid_capture(workspace, *, name: str = "replay.json") -> Path:
    capture_file = workspace.captures / name
    capture_file.write_text(
        json.dumps(
            {
                "format_version": "protolink-packet-replay-v1",
                "name": "release-smoke-capture",
                "created_at": "2026-04-11T00:00:00+00:00",
                "steps": [
                    {
                        "delay_ms": 0,
                        "direction": "outbound",
                        "session_id": "bench-session",
                        "transport_kind": "serial",
                        "payload_hex": "01 03 00 0a 00 02",
                        "metadata": {"source": "release_smoke", "protocol": "modbus_rtu"},
                        "source_message": "Outbound payload (6 bytes)",
                    },
                    {
                        "delay_ms": 5,
                        "direction": "inbound",
                        "session_id": "bench-session",
                        "transport_kind": "serial",
                        "payload_hex": "01 03 00 0a 00 02",
                        "metadata": {"source": "serial"},
                        "source_message": "Inbound payload (6 bytes)",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return capture_file


def _configure_fake_bundled_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime-src"
    site_packages = tmp_path / "site-packages-src"
    (runtime_root / "DLLs").mkdir(parents=True, exist_ok=True)
    (runtime_root / "Lib" / "encodings").mkdir(parents=True, exist_ok=True)
    (site_packages / "demo_pkg").mkdir(parents=True, exist_ok=True)
    for file_name in ("python.exe", "pythonw.exe", "python3.dll", "python311.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        (runtime_root / file_name).write_bytes(b"runtime")
    (runtime_root / "DLLs" / "libcrypto-3.dll").write_bytes(b"dll")
    (runtime_root / "Lib" / "encodings" / "__init__.py").write_text("# encodings\n", encoding="utf-8")
    (site_packages / "demo_pkg" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    monkeypatch.setenv("PROTOLINK_BUNDLED_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("PROTOLINK_BUNDLED_SITE_PACKAGES", str(site_packages))


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
                "串口枚举不可用。",
                action="列出串口",
                recovery="请检查本机驱动安装后重试。",
            )
        ),
    )

    exit_code = main(["--list-serial-ports"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "列出串口失败： 串口枚举不可用。" in captured.out
    assert "恢复建议：请检查本机驱动安装后重试。" in captured.out


def test_main_returns_runtime_error_exit_code_for_unexpected_cli_failures(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "protolink.app.bootstrap_app_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("disk offline")),
    )

    exit_code = main(["--headless-summary"])
    captured = capsys.readouterr()

    assert exit_code == int(CliExitCode.RUNTIME_ERROR)
    assert captured.out.strip() == "命令行命令失败：disk offline"


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
    assert "创建导出骨架失败： 不支持的导出类型“badkind”。" in captured.out


def test_main_records_cli_user_error_to_workspace_evidence(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--export-latest-capture", "bench capture"])
    captured = capsys.readouterr()
    workspace_logs = tmp_path / "workspace" / "logs"
    workspace_log = default_workspace_log_path(workspace_logs)
    evidence_file, evidence_entries, evidence_error = load_runtime_failure_evidence(workspace_logs)

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "定位工作区产物失败：" in captured.out
    assert workspace_log.exists()
    log_lines = workspace_log.read_text(encoding="utf-8").strip().splitlines()
    assert '"category": "cli.error"' in log_lines[-1]
    assert evidence_error is None
    assert evidence_file == default_runtime_failure_evidence_path(workspace_logs)
    assert len(evidence_entries) == 1
    assert evidence_entries[0]["source"] == "cli"
    assert evidence_entries[0]["code"] == "cli_user_error"


def test_main_records_cli_user_error_to_explicit_workspace_without_context(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace_root = tmp_path / "portable-workspace"

    def fail_bootstrap(*args, **kwargs):
        raise ProtoLinkUserError(
            "工作区初始化失败。",
            action="初始化工作区",
            recovery="请修复工作区配置后重试。",
        )

    monkeypatch.setattr("protolink.app.bootstrap_app_context", fail_bootstrap)

    exit_code = main(["--workspace", str(workspace_root), "--headless-summary"])
    captured = capsys.readouterr()
    workspace_logs = workspace_root / "logs"
    workspace_log = default_workspace_log_path(workspace_logs)
    evidence_file, evidence_entries, evidence_error = load_runtime_failure_evidence(workspace_logs)

    assert exit_code == int(CliExitCode.USER_ERROR)
    assert "初始化工作区失败： 工作区初始化失败。" in captured.out
    assert workspace_log.exists()
    assert '"category": "cli.error"' in workspace_log.read_text(encoding="utf-8")
    assert evidence_error is None
    assert evidence_file == default_runtime_failure_evidence_path(workspace_logs)
    assert len(evidence_entries) == 1
    assert evidence_entries[0]["code"] == "cli_user_error"
    assert evidence_entries[0]["details"]["workspace"] == str(workspace_root.resolve())


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
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
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
    _write_valid_runtime_log(workspace)
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "capture_artifacts_missing" in payload["blocking_items"]
    assert payload["ready"] is False


def test_main_release_preflight_rejects_invalid_runtime_log(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    runtime_log = default_workspace_log_path(workspace.logs)
    runtime_log.write_text("{not-json\n", encoding="utf-8")
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "runtime_log_invalid_jsonl" in payload["blocking_items"]
    assert payload["runtime_log_valid"] is False
    assert payload["ready"] is False


def test_main_release_preflight_rejects_junk_profile_and_capture_artifacts(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    (workspace.profiles / "junk.txt").write_text("not-a-profile", encoding="utf-8")
    (workspace.captures / "junk.bin").write_text("not-a-capture", encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "capture_artifacts_missing" in payload["blocking_items"]
    assert any(path.endswith("junk.txt") for path in payload["invalid_profile_artifact_files"])
    assert any(path.endswith("junk.bin") for path in payload["invalid_capture_artifact_files"])
    assert payload["ready"] is False


def test_main_release_preflight_uses_latest_valid_capture_and_profile(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_serial_profile(workspace)
    _write_valid_capture(workspace, name="20260411-valid-capture.json")
    (workspace.captures / "20260411-stale-invalid.json").write_text('{"steps":[]}\n', encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["selected_capture_file"].endswith("20260411-valid-capture.json")
    assert payload["selected_profile_file"].endswith("serial_studio.json")
    assert payload["ready"] is True


def test_main_release_preflight_rejects_event_handler_errors(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def inject_handler_error(base_dir, *args, **kwargs):
        from protolink.core.bootstrap import bootstrap_app_context

        context = bootstrap_app_context(base_dir, *args, **kwargs)

        def fail(entry) -> None:
            raise RuntimeError("handler failed")

        context.event_bus.subscribe(type(create_log_entry(level=LogLevel.INFO, category="audit", message="x")), fail)
        context.event_bus.publish(create_log_entry(level=LogLevel.INFO, category="audit", message="x"))
        return context

    monkeypatch.setattr("protolink.app.bootstrap_app_context", inject_handler_error)

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "event_handler_errors_present" in payload["blocking_items"]
    assert payload["event_handler_error_count"] == 1
    assert payload["ready"] is False


def test_main_release_preflight_rejects_runtime_log_write_failures(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def inject_writer_failure(base_dir, *args, **kwargs):
        from protolink.core.bootstrap import bootstrap_app_context

        context = bootstrap_app_context(base_dir, *args, **kwargs)
        context.workspace_log_writer.failed_write_count = 2
        context.workspace_log_writer.last_error = "disk full"
        return context

    monkeypatch.setattr("protolink.app.bootstrap_app_context", inject_writer_failure)

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert "runtime_log_write_failures_detected" in payload["blocking_items"]
    assert payload["workspace_log_failed_write_count"] == 2
    assert payload["workspace_log_last_error"] == "disk full"
    assert payload["ready"] is False


def test_main_release_preflight_rejects_settings_config_failures(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    settings_dir = tmp_path / ".protolink"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "app_settings.json").write_text("{not-json", encoding="utf-8")
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    evidence_file, evidence_entries, evidence_error = load_config_failure_evidence(settings_dir)

    assert exit_code == int(CliExitCode.OK)
    assert "settings_config_failures_present" in payload["blocking_items"]
    assert payload["settings_config_failure_count"] == 1
    assert payload["settings_config_failure_entries"][0]["code"] == "settings_load_failed"
    assert payload["settings_invalid_backup_files"]
    assert payload["ready"] is False
    assert evidence_error is None
    assert evidence_file == default_config_failure_evidence_path(settings_dir)
    assert len(evidence_entries) == 1
    assert evidence_entries[0]["code"] == "settings_load_failed"


def test_main_release_preflight_rejects_workspace_config_failures(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
    (workspace.root / WORKSPACE_MANIFEST_FILE).write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    exit_code = main(["--release-preflight"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    evidence_file, evidence_entries, evidence_error = load_config_failure_evidence(workspace.root)

    assert exit_code == int(CliExitCode.OK)
    assert "workspace_config_failures_present" in payload["blocking_items"]
    assert payload["workspace_config_failure_count"] == 1
    assert payload["workspace_config_failure_entries"][0]["code"] == "workspace_manifest_load_failed"
    assert payload["workspace_invalid_backup_files"]
    assert payload["ready"] is False
    assert evidence_error is None
    assert evidence_file == default_config_failure_evidence_path(workspace.root)
    assert len(evidence_entries) == 1
    assert evidence_entries[0]["code"] == "workspace_manifest_load_failed"


def test_main_exports_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_runtime_log(workspace)
    _write_valid_capture(workspace)
    _write_valid_serial_profile(workspace)
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
    assert payload["replay_step_count"] >= 2


def test_main_prepares_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--prepare-release", "bench release"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    assert payload["preflight"]["ready"] is True
    assert payload["generated_artifacts"]["replay_step_count"] == 2
    bundle_dir = Path(payload["bundle_dir"])
    assert bundle_dir.exists()
    assert (bundle_dir / "release-preflight.json").exists()
    assert payload["manifest"]["format_version"] == "protolink-release-bundle-v1"


def test_main_packages_release_bundle(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
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
    _configure_fake_bundled_runtime(monkeypatch, tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
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


def test_main_portable_bundle_installs_bundled_runtime_and_launch_scripts(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _configure_fake_bundled_runtime(monkeypatch, tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "w")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
        }

    monkeypatch.setattr("protolink.app.generate_smoke_artifacts", _fake_generate_smoke_artifacts)

    exit_code = main(["--build-portable-package", "p"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == int(CliExitCode.OK)
    install_dir = tmp_path / "i"
    exit_code = main(["--install-portable-package", str(payload["portable_archive_file"]), str(install_dir)])
    captured = capsys.readouterr()
    install_payload = json.loads(captured.out)
    assert exit_code == int(CliExitCode.OK)
    runtime_python = install_dir / "runtime" / "python.exe"
    assert runtime_python.exists()
    assert (install_dir / "runtime" / "pythonw.exe").exists()
    assert (install_dir / "sp").exists()
    assert (install_dir / "Launch-ProtoLink.ps1").exists()
    assert (install_dir / "Launch-ProtoLink.bat").exists()
    install_script = (install_dir / "INSTALL.ps1").read_text(encoding="utf-8")
    launch_ps1 = (install_dir / "Launch-ProtoLink.ps1").read_text(encoding="utf-8")
    launch_bat = (install_dir / "Launch-ProtoLink.bat").read_text(encoding="utf-8")
    assert "runtime\\python.exe" in install_script
    assert "PYTHONPATH" in install_script
    assert "PROTOLINK_BASE_DIR" in install_script
    assert "ProtoLinkArgs" in launch_ps1
    assert "python.exe" in launch_ps1
    assert "pythonw.exe" in launch_ps1
    assert "@ProtoLinkArgs" in launch_ps1
    assert "PROTOLINK_BASE_DIR" in launch_ps1
    assert 'if not "%~1"==""' in launch_bat
    assert "python.exe" in launch_bat
    assert "pythonw.exe" in launch_bat
    assert "%*" in launch_bat
    assert "PROTOLINK_BASE_DIR" in launch_bat
    assert install_payload["target_dir"] == str(install_dir)


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
    _configure_fake_bundled_runtime(monkeypatch, tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
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
    _configure_fake_bundled_runtime(monkeypatch, tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
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
    _configure_fake_bundled_runtime(monkeypatch, tmp_path)
    workspace = ensure_workspace_layout(tmp_path / "workspace")
    _write_valid_serial_profile(workspace)
    monkeypatch.setattr("protolink.app.run_ui_smoke_check", lambda: "smoke-check-ok")

    def _fake_generate_smoke_artifacts(context):
        runtime_log = _write_valid_runtime_log(context.workspace)
        capture_file = _write_valid_capture(context.workspace, name="release-smoke.json")
        return {
            "workspace": str(context.workspace.root),
            "log_file": str(runtime_log),
            "capture_file": str(capture_file),
            "replay_step_count": 2,
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
                "checksum": ("0" if _sha256_file(installer_staging_archive)[0] != "0" else "1")
                + _sha256_file(installer_staging_archive)[1:],
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

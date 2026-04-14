from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
import tempfile
import time

from protolink import __version__
from protolink.catalog import build_module_catalog
from protolink.core.bootstrap import AppContext, bootstrap_app_context
from protolink.core.errors import CliExitCode, ProtoLinkUserError, format_cli_error, format_unexpected_cli_error
from protolink.core.models import ModuleStatus
from protolink.core.import_export import (
    ArtifactKind,
    build_export_bundle_plan,
    build_release_bundle_plan,
    find_latest_artifact_file,
    materialize_release_bundle,
    materialize_export_bundle,
    materialize_export_bundle_from_file,
    package_release_bundle,
    resolve_artifact_kind,
)
from protolink.core.logging import (
    LogLevel,
    RuntimeFailureEvidenceRecorder,
    WorkspaceJsonlLogWriter,
    create_log_entry,
    default_runtime_failure_evidence_path,
    default_workspace_log_path,
    load_config_failure_evidence,
    load_runtime_failure_evidence,
)
from protolink.core.packaging import (
    build_native_installer_scaffold_plan,
    build_installer_staging_plan,
    build_installer_package_plan,
    build_distribution_package_plan,
    build_portable_package_plan,
    install_distribution_package,
    install_installer_package,
    install_installer_staging_package,
    install_portable_package,
    materialize_installer_package,
    materialize_installer_staging_package,
    materialize_distribution_package,
    materialize_native_installer_scaffold,
    materialize_portable_package,
    uninstall_portable_package,
    verify_distribution_package,
    verify_native_installer_scaffold,
    verify_native_installer_toolchain,
    verify_portable_package,
    verify_installer_package,
    verify_installer_staging_package,
)
from protolink.core.packet_replay import (
    ReplayDirection,
    build_packet_replay_plan,
    default_packet_replay_path,
    infer_replay_direction,
    load_packet_replay_plan,
    save_packet_replay_plan,
)
from protolink.core.settings import resolve_application_base_dir
from protolink.core.workspace import migrate_workspace, workspace_manifest_path
from protolink.presentation import APPLICATION_SUBTITLE, APPLICATION_TITLE, HEADLESS_GOAL
from protolink.transports.serial import list_serial_ports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ProtoLink 桌面端工具")
    parser.add_argument("--version", action="store_true", help="输出应用版本并退出。")
    parser.add_argument(
        "--print-workspace",
        action="store_true",
        help="初始化默认工作区并输出其路径。",
    )
    parser.add_argument(
        "--headless-summary",
        action="store_true",
        help="输出无界面项目摘要，供 CI 或快速核验使用。",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="使用指定工作区路径，并将其记为当前活动工作区。",
    )
    parser.add_argument(
        "--list-recent-workspaces",
        action="store_true",
        help="输出最近使用的工作区并退出。",
    )
    parser.add_argument(
        "--print-settings",
        action="store_true",
        help="输出持久化设置文件路径并退出。",
    )
    parser.add_argument(
        "--list-serial-ports",
        action="store_true",
        help="输出检测到的串口列表并退出。",
    )
    parser.add_argument(
        "--create-export-scaffold",
        nargs=3,
        metavar=("KIND", "NAME", "EXT"),
        help="在当前工作区的 exports 目录下创建导出包骨架。",
    )
    parser.add_argument(
        "--export-runtime-log",
        metavar="NAME",
        help="将当前工作区运行期传输日志导出为正式导出包。",
    )
    parser.add_argument(
        "--export-latest-capture",
        metavar="NAME",
        help="将工作区最新抓包产物导出为正式导出包。",
    )
    parser.add_argument(
        "--export-latest-profile",
        metavar="NAME",
        help="将工作区最新配置产物导出为正式导出包。",
    )
    parser.add_argument(
        "--smoke-check",
        action="store_true",
        help="执行内置离屏冒烟检查并退出。",
    )
    parser.add_argument(
        "--migrate-workspace",
        action="store_true",
        help="确保当前工作区符合最新格式，并输出迁移报告。",
    )
    parser.add_argument(
        "--release-preflight",
        action="store_true",
        help="针对当前工作区执行发布预检，并输出 JSON 报告。",
    )
    parser.add_argument(
        "--export-release-bundle",
        metavar="NAME",
        help="导出发布包，包含最新运行日志、抓包、配置和预检报告。",
    )
    parser.add_argument(
        "--generate-smoke-artifacts",
        action="store_true",
        help="通过受控冒烟流程生成真实工作区运行产物。",
    )
    parser.add_argument(
        "--prepare-release",
        metavar="NAME",
        help="执行工作区迁移、按需补齐冒烟产物、完成预检，并导出发布包。",
    )
    parser.add_argument(
        "--package-release",
        metavar="NAME",
        help="执行发布准备，并将发布包压缩为 zip 归档。",
    )
    parser.add_argument(
        "--build-portable-package",
        metavar="NAME",
        help="构建便携包 zip，包含发布归档及安装元数据。",
    )
    parser.add_argument(
        "--install-portable-package",
        nargs=2,
        metavar=("ARCHIVE", "TARGET_DIR"),
        help="将便携包归档安装到目标目录。",
    )
    parser.add_argument(
        "--uninstall-portable-package",
        metavar="TARGET_DIR",
        help="依据安装回执卸载便携包已安装文件。",
    )
    parser.add_argument(
        "--verify-portable-package",
        metavar="ARCHIVE",
        help="校验便携包归档的清单、发布归档和校验和。",
    )
    parser.add_argument(
        "--build-distribution-package",
        metavar="NAME",
        help="构建分发包 zip，包含便携包、发布归档及分发元数据。",
    )
    parser.add_argument(
        "--verify-distribution-package",
        metavar="ARCHIVE",
        help="校验分发包归档的清单、引用的便携包/发布归档及校验和。",
    )
    parser.add_argument(
        "--install-distribution-package",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="将分发包解压到暂存目录，并把其中的便携包安装到目标目录。",
    )
    parser.add_argument(
        "--build-installer-staging",
        metavar="NAME",
        help="构建安装器暂存包，封装分发归档、安装元数据和启动脚本。",
    )
    parser.add_argument(
        "--install-installer-staging",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="解压安装器暂存归档，暂存其中分发包，并安装便携包到目标目录。",
    )
    parser.add_argument(
        "--verify-installer-staging",
        metavar="ARCHIVE",
        help="校验安装器暂存归档的清单、引用的分发归档及校验和。",
    )
    parser.add_argument(
        "--build-installer-package",
        metavar="NAME",
        help="构建顶层安装器归档，封装安装器暂存包和安装元数据。",
    )
    parser.add_argument(
        "--verify-installer-package",
        metavar="ARCHIVE",
        help="校验安装器归档的清单、引用的安装器暂存归档及校验和。",
    )
    parser.add_argument(
        "--build-native-installer-scaffold",
        metavar="NAME",
        help="基于当前安装器包构建 WiX/MSI 原生安装器脚手架目录。",
    )
    parser.add_argument(
        "--verify-native-installer-scaffold",
        metavar="DIR",
        help="校验已生成的 WiX/MSI 原生安装器脚手架目录。",
    )
    parser.add_argument(
        "--verify-native-installer-toolchain",
        action="store_true",
        help="检测当前环境中的 WiX / signtool 原生安装器工具链可用性。",
    )
    parser.add_argument(
        "--install-installer-package",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="解压安装器归档，暂存其中安装器包，并安装便携包到目标目录。",
    )
    return parser


def run_ui_smoke_check() -> str:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if os.name == "nt" and "QT_QPA_FONTDIR" not in os.environ:
        windows_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
        font_dir = windows_root / "Fonts"
        if font_dir.exists():
            os.environ["QT_QPA_FONTDIR"] = str(font_dir)
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    from protolink.ui.main_window import ProtoLinkMainWindow
    from protolink.ui.qt_dispatch import QtCallbackDispatcher
    from protolink.ui.theme import APP_STYLESHEET

    previous_qt_message_handler = None

    def handle_qt_message(mode, context, message) -> None:
        if message == "This plugin does not support propagateSizeHints()":
            return
        if previous_qt_message_handler is not None:
            previous_qt_message_handler(mode, context, message)

    previous_qt_message_handler = qInstallMessageHandler(handle_qt_message)
    app = QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = bootstrap_app_context(Path(temp_dir), persist_settings=False)
            dispatcher = QtCallbackDispatcher()
            context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
            context.packet_replay_service.set_dispatch_scheduler(dispatcher.dispatch)
            window = ProtoLinkMainWindow(
                workspace=context.workspace,
                inspector=context.packet_inspector,
                data_tools_service=context.data_tools_service,
                network_tools_service=context.network_tools_service,
                serial_service=context.serial_session_service,
                mqtt_client_service=context.mqtt_client_service,
                mqtt_server_service=context.mqtt_server_service,
                tcp_client_service=context.tcp_client_service,
                tcp_server_service=context.tcp_server_service,
                udp_service=context.udp_service,
                packet_replay_service=context.packet_replay_service,
                register_monitor_service=context.register_monitor_service,
                rule_engine_service=context.rule_engine_service,
                auto_response_runtime_service=context.auto_response_runtime_service,
                script_console_service=context.script_console_service,
                timed_task_service=context.timed_task_service,
                channel_bridge_runtime_service=context.channel_bridge_runtime_service,
            )
            window.show()
            app.processEvents()
            window.close()
            context.serial_session_service.shutdown()
            context.mqtt_client_service.shutdown()
            context.mqtt_server_service.shutdown()
            context.tcp_client_service.shutdown()
            context.tcp_server_service.shutdown()
            context.udp_service.shutdown()
            context.packet_replay_service.shutdown()
            context.channel_bridge_runtime_service.shutdown()
            context.timed_task_service.shutdown()
    finally:
        app.quit()
        qInstallMessageHandler(previous_qt_message_handler)
    return "smoke-check-ok"


def _invalid_config_backups(directory: Path, file_name: str) -> list[str]:
    return sorted(
        str(path)
        for path in directory.glob(f"{file_name}.invalid*")
        if path.is_file()
    )


def _record_cli_failure(
    context: AppContext | None,
    *,
    code: str,
    message: str,
    command_args: list[str],
    workspace_override: Path | None = None,
    recovery: str | None = None,
) -> None:
    workspace_root: Path | None = None
    if context is not None:
        workspace_root = context.workspace.root
    elif workspace_override is not None:
        workspace_root = workspace_override.expanduser().resolve()

    metadata = {
        "argv": " ".join(command_args),
    }
    if workspace_root is not None:
        metadata["workspace"] = str(workspace_root)
    if recovery:
        metadata["recovery"] = recovery

    entry = create_log_entry(
        level=LogLevel.ERROR,
        category="cli.error",
        message=message,
        metadata=metadata,
    )
    if context is not None:
        context.log_store.append(entry)
        context.event_bus.publish(entry)
        context.runtime_failure_evidence_recorder.append(
            source="cli",
            code=code,
            message=message,
            details=metadata,
        )
        return

    if workspace_root is None:
        return

    logs_dir = workspace_root / "logs"
    recorder = RuntimeFailureEvidenceRecorder(default_runtime_failure_evidence_path(logs_dir))
    writer = WorkspaceJsonlLogWriter(
        default_workspace_log_path(logs_dir),
        failure_evidence_recorder=recorder,
    )
    writer.append(entry)
    recorder.append(
        source="cli",
        code=code,
        message=message,
        details=metadata,
    )


def _inspect_workspace_log_jsonl(log_file: Path) -> tuple[bool, int, str | None]:
    if not log_file.exists():
        return False, 0, None

    line_count = 0
    try:
        with log_file.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                line_count += 1
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    return False, line_count, f"line {line_number} must contain a JSON object"
                required_string_fields = ("entry_id", "timestamp", "level", "category", "message")
                if not all(isinstance(payload.get(field), str) and str(payload.get(field, "")).strip() for field in required_string_fields):
                    return False, line_count, f"line {line_number} is missing required structured-log fields"
                if payload.get("session_id") is not None and not isinstance(payload.get("session_id"), str):
                    return False, line_count, f"line {line_number} has an invalid session_id field"
                if payload.get("transport_kind") is not None and not isinstance(payload.get("transport_kind"), str):
                    return False, line_count, f"line {line_number} has an invalid transport_kind field"
                raw_payload_hex = payload.get("raw_payload_hex")
                if raw_payload_hex is not None and not isinstance(raw_payload_hex, str):
                    return False, line_count, f"line {line_number} has an invalid raw_payload_hex field"
                if not isinstance(payload.get("metadata", {}), dict):
                    return False, line_count, f"line {line_number} must contain an object metadata field"
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return False, line_count, str(exc)

    return True, line_count, None


def _artifact_candidates(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return [
        path
        for path in directory.iterdir()
        if path.is_file() and ".invalid" not in path.name
    ]


def _inspect_profile_artifacts(profiles_dir: Path) -> tuple[list[Path], list[Path]]:
    valid: list[Path] = []
    invalid: list[Path] = []
    for path in _artifact_candidates(profiles_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            invalid.append(path)
            continue
        if not isinstance(payload, dict):
            invalid.append(path)
            continue
        format_version = payload.get("format_version")
        if not isinstance(format_version, str) or not format_version.startswith("protolink-"):
            invalid.append(path)
            continue
        valid.append(path)
    return valid, invalid


def _capture_plan_has_round_trip(plan) -> bool:
    if len(plan.steps) < 2:
        return False
    saw_outbound = False
    for step in plan.steps:
        if step.direction == ReplayDirection.OUTBOUND:
            saw_outbound = True
            continue
        if saw_outbound and step.direction == ReplayDirection.INBOUND:
            return True
    return False


def _inspect_capture_artifacts(captures_dir: Path) -> tuple[list[Path], list[Path]]:
    valid: list[Path] = []
    invalid: list[Path] = []
    for path in _artifact_candidates(captures_dir):
        try:
            plan = load_packet_replay_plan(path)
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            invalid.append(path)
            continue
        if not _capture_plan_has_round_trip(plan):
            invalid.append(path)
            continue
        valid.append(path)
    return valid, invalid


def _latest_artifact(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def build_release_preflight_report(context) -> dict[str, object]:
    workspace = context.workspace
    log_file = default_workspace_log_path(workspace.logs)
    valid_profile_candidates, invalid_profile_candidates = _inspect_profile_artifacts(workspace.profiles)
    valid_capture_candidates, invalid_capture_candidates = _inspect_capture_artifacts(workspace.captures)
    selected_profile_file = _latest_artifact(valid_profile_candidates)
    selected_capture_file = _latest_artifact(valid_capture_candidates)
    smoke_result = run_ui_smoke_check()
    manifest_file = workspace_manifest_path(workspace.root)
    settings_invalid_backup_files = _invalid_config_backups(context.settings_layout.root, context.settings_layout.settings_file.name)
    workspace_invalid_backup_files = _invalid_config_backups(workspace.root, manifest_file.name)
    runtime_log_valid, runtime_log_line_count, runtime_log_parse_error = _inspect_workspace_log_jsonl(log_file)
    runtime_failure_evidence_file, runtime_failure_evidence_entries, runtime_failure_evidence_error = load_runtime_failure_evidence(
        workspace.logs
    )
    settings_config_failure_file, settings_config_failure_entries, settings_config_failure_error = load_config_failure_evidence(
        context.settings_layout.root
    )
    workspace_config_failure_file, workspace_config_failure_entries, workspace_config_failure_error = load_config_failure_evidence(
        workspace.root
    )
    event_handler_errors = [
        entry for entry in runtime_failure_evidence_entries if entry.get("code") == "event_handler_error"
    ]
    log_write_failures = [
        entry for entry in runtime_failure_evidence_entries if entry.get("code") == "workspace_log_write_failure"
    ]
    service_close_failures = [
        entry
        for entry in runtime_failure_evidence_entries
        if entry.get("code") in {"service_shutdown_close_failed", "service_close_failed"}
    ]
    current_event_handler_errors = [
        {
            "event_type": error.event_type.__name__,
            "error": error.error,
        }
        for error in context.event_bus.handler_errors
    ]
    current_log_write_failure_count = context.workspace_log_writer.failed_write_count
    current_log_write_last_error = context.workspace_log_writer.last_error
    effective_event_handler_errors = event_handler_errors if event_handler_errors else current_event_handler_errors
    effective_log_write_failure_count = len(log_write_failures) if log_write_failures else current_log_write_failure_count
    effective_log_write_last_error = (
        log_write_failures[-1]["message"]
        if log_write_failures
        else current_log_write_last_error
    )
    blocking_items: list[str] = []
    if not manifest_file.exists():
        blocking_items.append("workspace_manifest_missing")
    if not log_file.exists():
        blocking_items.append("runtime_log_missing")
    elif not runtime_log_valid:
        blocking_items.append("runtime_log_invalid_jsonl")
    if not selected_profile_file:
        blocking_items.append("profile_artifacts_missing")
    if not selected_capture_file:
        blocking_items.append("capture_artifacts_missing")
    if runtime_failure_evidence_error is not None:
        blocking_items.append("runtime_failure_evidence_invalid")
    if settings_config_failure_error is not None:
        blocking_items.append("settings_config_failure_evidence_invalid")
    if workspace_config_failure_error is not None:
        blocking_items.append("workspace_config_failure_evidence_invalid")
    if settings_config_failure_entries:
        blocking_items.append("settings_config_failures_present")
    if workspace_config_failure_entries:
        blocking_items.append("workspace_config_failures_present")
    if effective_event_handler_errors:
        blocking_items.append("event_handler_errors_present")
    if effective_log_write_failure_count > 0:
        blocking_items.append("runtime_log_write_failures_detected")
    if service_close_failures:
        blocking_items.append("service_close_failures_present")
    if smoke_result != "smoke-check-ok":
        blocking_items.append("smoke_check_failed")
    return {
        "workspace": str(workspace.root),
        "manifest_file": str(manifest_file),
        "manifest_exists": manifest_file.exists(),
        "log_file": str(log_file),
        "log_file_exists": log_file.exists(),
        "runtime_log_valid": runtime_log_valid,
        "runtime_log_line_count": runtime_log_line_count,
        "runtime_log_parse_error": runtime_log_parse_error,
        "profile_file_count": len(valid_profile_candidates),
        "selected_profile_file": str(selected_profile_file) if selected_profile_file is not None else None,
        "capture_file_count": len(valid_capture_candidates),
        "selected_capture_file": str(selected_capture_file) if selected_capture_file is not None else None,
        "invalid_profile_artifact_files": [str(path) for path in invalid_profile_candidates],
        "invalid_capture_artifact_files": [str(path) for path in invalid_capture_candidates],
        "settings_invalid_backup_files": settings_invalid_backup_files,
        "workspace_invalid_backup_files": workspace_invalid_backup_files,
        "exports_dir": str(workspace.exports),
        "event_handler_error_count": len(effective_event_handler_errors),
        "event_handler_errors": effective_event_handler_errors,
        "workspace_log_failed_write_count": effective_log_write_failure_count,
        "workspace_log_last_error": effective_log_write_last_error,
        "service_close_failure_count": len(service_close_failures),
        "service_close_failures": service_close_failures,
        "settings_config_failure_file": str(settings_config_failure_file) if settings_config_failure_file is not None else None,
        "settings_config_failure_count": len(settings_config_failure_entries),
        "settings_config_failure_entries": settings_config_failure_entries,
        "settings_config_failure_error": settings_config_failure_error,
        "workspace_config_failure_file": str(workspace_config_failure_file) if workspace_config_failure_file is not None else None,
        "workspace_config_failure_count": len(workspace_config_failure_entries),
        "workspace_config_failure_entries": workspace_config_failure_entries,
        "workspace_config_failure_error": workspace_config_failure_error,
        "runtime_failure_evidence_file": str(runtime_failure_evidence_file) if runtime_failure_evidence_file is not None else None,
        "runtime_failure_evidence_count": len(runtime_failure_evidence_entries),
        "runtime_failure_evidence_entries": runtime_failure_evidence_entries,
        "runtime_failure_evidence_error": runtime_failure_evidence_error,
        "smoke_check": smoke_result,
        "blocking_items": blocking_items,
        "ready": not blocking_items,
    }


def find_optional_latest_file(directory: Path) -> Path | None:
    try:
        return find_latest_artifact_file(directory)
    except ProtoLinkUserError:
        return None


def find_optional_latest_valid_profile_file(directory: Path) -> Path | None:
    valid, _invalid = _inspect_profile_artifacts(directory)
    return _latest_artifact(valid)


def find_optional_latest_valid_capture_file(directory: Path) -> Path | None:
    valid, _invalid = _inspect_capture_artifacts(directory)
    return _latest_artifact(valid)


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise TimeoutError("Timed out waiting for smoke artifact condition.")


def generate_smoke_artifacts(context) -> dict[str, object]:
    service = context.serial_session_service
    service.set_target("loop://")
    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state.name in {"CONNECTED", "ERROR"})
    if service.snapshot.connection_state.name != "CONNECTED":
        raise RuntimeError(service.snapshot.last_error or "串口冒烟会话连接失败。")

    session_id = service.snapshot.active_session_id
    if not session_id:
        raise RuntimeError("串口冒烟会话未暴露有效的活动会话 ID。")

    service.send_replay_payload(b"\x01\x03\x00\x0A\x00\x02", {"source": "release_smoke", "protocol": "modbus_rtu"})

    def has_round_trip_messages() -> bool:
        entries = [
            entry
            for entry in context.log_store.latest(500)
            if entry.category == "transport.message" and entry.session_id == session_id
        ]
        saw_outbound = False
        for entry in entries:
            direction = infer_replay_direction(entry)
            if direction == ReplayDirection.OUTBOUND:
                saw_outbound = True
                continue
            if saw_outbound and direction == ReplayDirection.INBOUND:
                return True
        return False

    _wait_until(has_round_trip_messages)
    _wait_until(lambda: default_workspace_log_path(context.workspace.logs).exists())

    session_entries = [
        entry
        for entry in context.log_store.latest(500)
        if entry.category == "transport.message" and entry.session_id == session_id
    ]

    plan = build_packet_replay_plan(
        session_entries,
        name="release-smoke-capture",
        include_directions={ReplayDirection.OUTBOUND, ReplayDirection.INBOUND},
    )
    if not _capture_plan_has_round_trip(plan):
        raise RuntimeError("冒烟抓包未生成有效的出站/入站往返链路。")
    capture_path = default_packet_replay_path(context.workspace.captures, plan.name, created_at=plan.created_at)
    save_packet_replay_plan(capture_path, plan)

    service.close_session()
    _wait_until(lambda: service.snapshot.connection_state.name == "DISCONNECTED")
    service.shutdown()

    return {
        "workspace": str(context.workspace.root),
        "log_file": str(default_workspace_log_path(context.workspace.logs)),
        "capture_file": str(capture_path),
        "replay_step_count": len(plan.steps),
    }


def prepare_release_bundle(context, name: str) -> dict[str, object]:
    migration = migrate_workspace(context.workspace.root)
    generated_artifacts: dict[str, object] | None = None

    log_file = default_workspace_log_path(context.workspace.logs)
    capture_file = find_optional_latest_valid_capture_file(context.workspace.captures)
    if not log_file.exists() or capture_file is None:
        generated_artifacts = generate_smoke_artifacts(context)

    preflight_report = build_release_preflight_report(context)
    if not preflight_report["ready"]:
        blocking = ", ".join(str(item) for item in preflight_report["blocking_items"]) or "unknown"
        raise ProtoLinkUserError(
            "Release preflight is not ready.",
            action="准备发布",
            recovery=f"请先处理以下阻断项：{blocking}。",
        )

    plan = build_release_bundle_plan(
        context.workspace,
        name,
        runtime_log_file=default_workspace_log_path(context.workspace.logs),
        latest_capture_file=find_optional_latest_valid_capture_file(context.workspace.captures),
        latest_profile_file=find_optional_latest_valid_profile_file(context.workspace.profiles),
    )
    manifest = materialize_release_bundle(plan, preflight_report=preflight_report)
    return {
        "workspace": str(context.workspace.root),
        "migration": {
            "from_version": migration.from_version,
            "to_version": migration.to_version,
            "changed": migration.changed,
            "manifest_file": str(migration.manifest_file),
        },
        "generated_artifacts": generated_artifacts,
        "preflight": preflight_report,
        "bundle_dir": str(plan.bundle_dir),
        "manifest_file": str(plan.manifest_file),
        "manifest": manifest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command_args = list(argv if argv is not None else sys.argv[1:])
    context: AppContext | None = None
    workspace_override = Path(args.workspace) if args.workspace else None

    base_dir = resolve_application_base_dir(Path.cwd())

    if args.version:
        print(__version__)
        return int(CliExitCode.OK)

    try:
        if args.list_serial_ports:
            for port in list_serial_ports():
                print(f"{port.device}\t{port.description}\t{port.hardware_id}")
            return int(CliExitCode.OK)

        if args.verify_native_installer_toolchain:
            result = verify_native_installer_toolchain()
            print(
                json.dumps(
                    {
                        "target_platform": result.target_platform,
                        "current_platform": result.current_platform,
                        "ready": result.ready,
                        "available_tools": list(result.available_tools),
                        "missing_tools": list(result.missing_tools),
                        "tools": {
                            tool.tool_key: {
                                "display_name": tool.display_name,
                                "executable_name": tool.executable_name,
                                "available": tool.available,
                                "resolved_path": tool.resolved_path,
                                "detection_source": tool.detection_source,
                                "probe_command": list(tool.probe_command),
                                "probe_output": tool.probe_output,
                                "error": tool.error,
                                "install_hint": tool.install_hint,
                                "recommended_command": tool.recommended_command,
                            }
                            for tool in result.tools
                        },
                        "recommended_commands": result.recommended_commands,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        read_only_mode = any(
            (
                args.print_workspace,
                args.print_settings,
                args.list_recent_workspaces,
                args.headless_summary,
                args.list_serial_ports,
                args.smoke_check,
                args.migrate_workspace,
                args.release_preflight,
                args.export_release_bundle,
                args.generate_smoke_artifacts,
                args.prepare_release,
                args.package_release,
                args.build_portable_package,
                bool(args.install_portable_package),
                args.uninstall_portable_package,
                args.verify_portable_package,
                args.build_distribution_package,
                args.verify_distribution_package,
                bool(args.install_distribution_package),
                args.build_installer_staging,
                bool(args.install_installer_staging),
                args.verify_installer_staging,
                args.build_installer_package,
                args.verify_installer_package,
                args.build_native_installer_scaffold,
                args.verify_native_installer_scaffold,
                args.verify_native_installer_toolchain,
                bool(args.install_installer_package),
            )
        )
        context = bootstrap_app_context(
            base_dir,
            workspace_override=workspace_override,
            persist_settings=not read_only_mode,
        )

        if args.print_workspace:
            print(context.workspace.root)
            return int(CliExitCode.OK)

        if args.print_settings:
            print(context.settings_layout.settings_file)
            return int(CliExitCode.OK)

        if args.list_recent_workspaces:
            recent_paths = context.settings.recent_workspaces
            if not recent_paths and context.settings.active_workspace:
                recent_paths = [context.settings.active_workspace]
            for path in recent_paths:
                print(path)
            return int(CliExitCode.OK)

        if args.headless_summary:
            modules = build_module_catalog()
            counts = Counter(module.status.value for module in modules)
            print("ProtoLink")
            print(f"定位：{HEADLESS_GOAL}")
            print(f"工作区：{context.workspace.root}")
            print(f"设置：{context.settings_layout.settings_file}")
            print(f"应用标题：{APPLICATION_TITLE}")
            print(f"应用副标题：{APPLICATION_SUBTITLE}")
            print(f"已注册传输：{len(context.transport_registry.registered_kinds())}")
            print(f"模块数：{len(modules)}")
            print(f"已落地：{counts.get(ModuleStatus.BOOTSTRAPPED.value, 0)}")
            print(f"下一阶段：{counts.get(ModuleStatus.NEXT.value, 0)}")
            print(f"规划中：{counts.get(ModuleStatus.PLANNED.value, 0)}")
            return int(CliExitCode.OK)

        if args.create_export_scaffold:
            kind_value, name, extension = args.create_export_scaffold
            artifact_kind = resolve_artifact_kind(kind_value)
            plan = build_export_bundle_plan(context.workspace, artifact_kind, name, extension)
            manifest = materialize_export_bundle(plan)
            print(
                json.dumps(
                    {
                        "bundle_dir": str(plan.bundle_dir),
                        "payload_file": str(plan.payload_file),
                        "manifest_file": str(plan.manifest_file),
                        "manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.export_runtime_log:
            source_file = default_workspace_log_path(context.workspace.logs)
            extension = source_file.suffix or ".jsonl"
            plan = build_export_bundle_plan(context.workspace, ArtifactKind.LOG, args.export_runtime_log, extension)
            manifest = materialize_export_bundle_from_file(plan, source_file)
            print(
                json.dumps(
                    {
                        "bundle_dir": str(plan.bundle_dir),
                        "payload_file": str(plan.payload_file),
                        "manifest_file": str(plan.manifest_file),
                        "source_file": str(source_file),
                        "manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.export_latest_capture:
            source_file = find_latest_artifact_file(context.workspace.captures)
            extension = source_file.suffix or ".bin"
            plan = build_export_bundle_plan(context.workspace, ArtifactKind.CAPTURE, args.export_latest_capture, extension)
            manifest = materialize_export_bundle_from_file(plan, source_file)
            print(
                json.dumps(
                    {
                        "bundle_dir": str(plan.bundle_dir),
                        "payload_file": str(plan.payload_file),
                        "manifest_file": str(plan.manifest_file),
                        "source_file": str(source_file),
                        "manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.export_latest_profile:
            source_file = find_latest_artifact_file(context.workspace.profiles)
            extension = source_file.suffix or ".json"
            plan = build_export_bundle_plan(context.workspace, ArtifactKind.PROFILE, args.export_latest_profile, extension)
            manifest = materialize_export_bundle_from_file(plan, source_file)
            print(
                json.dumps(
                    {
                        "bundle_dir": str(plan.bundle_dir),
                        "payload_file": str(plan.payload_file),
                        "manifest_file": str(plan.manifest_file),
                        "source_file": str(source_file),
                        "manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.smoke_check:
            try:
                print(run_ui_smoke_check())
                return int(CliExitCode.OK)
            except ModuleNotFoundError:
                print("未安装 GUI 依赖。请执行：uv sync --python 3.11 --extra dev --extra ui")
                return int(CliExitCode.GUI_DEPENDENCY_MISSING)

        if args.migrate_workspace:
            result = migrate_workspace(context.workspace.root)
            print(
                json.dumps(
                    {
                        "workspace": str(context.workspace.root),
                        "from_version": result.from_version,
                        "to_version": result.to_version,
                        "changed": result.changed,
                        "manifest_file": str(result.manifest_file),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.release_preflight:
            print(json.dumps(build_release_preflight_report(context), ensure_ascii=False, indent=2))
            return int(CliExitCode.OK)

        if args.export_release_bundle:
            preflight_report = build_release_preflight_report(context)
            plan = build_release_bundle_plan(
                context.workspace,
                args.export_release_bundle,
                runtime_log_file=default_workspace_log_path(context.workspace.logs) if default_workspace_log_path(context.workspace.logs).exists() else None,
                latest_capture_file=find_optional_latest_valid_capture_file(context.workspace.captures),
                latest_profile_file=find_optional_latest_valid_profile_file(context.workspace.profiles),
            )
            manifest = materialize_release_bundle(plan, preflight_report=preflight_report)
            print(
                json.dumps(
                    {
                        "bundle_dir": str(plan.bundle_dir),
                        "manifest_file": str(plan.manifest_file),
                        "manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.generate_smoke_artifacts:
            print(json.dumps(generate_smoke_artifacts(context), ensure_ascii=False, indent=2))
            return int(CliExitCode.OK)

        if args.prepare_release:
            print(json.dumps(prepare_release_bundle(context, args.prepare_release), ensure_ascii=False, indent=2))
            return int(CliExitCode.OK)

        if args.package_release:
            release_payload = prepare_release_bundle(context, args.package_release)
            archive_path = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            print(
                json.dumps(
                    {
                        **release_payload,
                        "archive_file": str(archive_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.build_portable_package:
            release_payload = prepare_release_bundle(context, args.build_portable_package)
            release_archive = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            plan = build_portable_package_plan(
                base_dir,
                context.workspace,
                args.build_portable_package,
                release_archive,
            )
            manifest = materialize_portable_package(plan, base_dir)
            print(
                json.dumps(
                    {
                        **release_payload,
                        "release_archive_file": str(release_archive),
                        "portable_package_dir": str(plan.package_dir),
                        "portable_archive_file": str(plan.archive_file),
                        "portable_manifest": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.install_portable_package:
            archive_value, target_dir_value = args.install_portable_package
            result = install_portable_package(Path(archive_value), Path(target_dir_value))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "target_dir": str(result.target_dir),
                        "extracted_entries": list(result.extracted_entries),
                        "receipt_file": str(result.receipt_file),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.uninstall_portable_package:
            result = uninstall_portable_package(Path(args.uninstall_portable_package))
            print(
                json.dumps(
                    {
                        "target_dir": str(result.target_dir),
                        "removed_entries": list(result.removed_entries),
                        "removed_receipt": result.removed_receipt,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.verify_portable_package:
            result = verify_portable_package(Path(args.verify_portable_package))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "portable_manifest_file": result.portable_manifest_file,
                        "release_archive_file": result.release_archive_file,
                        "checksum_matches": result.checksum_matches,
                        "install_scripts_present": list(result.install_scripts_present),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.build_distribution_package:
            release_payload = prepare_release_bundle(context, args.build_distribution_package)
            release_archive = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            portable_plan = build_portable_package_plan(
                base_dir,
                context.workspace,
                args.build_distribution_package,
                release_archive,
            )
            portable_manifest = materialize_portable_package(portable_plan, base_dir)
            distribution_plan = build_distribution_package_plan(
                context.workspace,
                args.build_distribution_package,
                portable_plan.archive_file,
                release_archive,
            )
            distribution_manifest = materialize_distribution_package(distribution_plan, base_dir)
            print(
                json.dumps(
                    {
                        **release_payload,
                        "release_archive_file": str(release_archive),
                        "portable_package_dir": str(portable_plan.package_dir),
                        "portable_archive_file": str(portable_plan.archive_file),
                        "portable_manifest": portable_manifest,
                        "distribution_package_dir": str(distribution_plan.package_dir),
                        "distribution_archive_file": str(distribution_plan.archive_file),
                        "distribution_manifest": distribution_manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.verify_distribution_package:
            result = verify_distribution_package(Path(args.verify_distribution_package))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "distribution_manifest_file": result.distribution_manifest_file,
                        "portable_archive_file": result.portable_archive_file,
                        "release_archive_file": result.release_archive_file,
                        "checksum_matches": result.checksum_matches,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.install_distribution_package:
            archive_value, staging_dir_value, install_dir_value = args.install_distribution_package
            result = install_distribution_package(Path(archive_value), Path(staging_dir_value), Path(install_dir_value))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "staging_dir": str(result.staging_dir),
                        "install_dir": str(result.install_dir),
                        "distribution_manifest_file": str(result.distribution_manifest_file),
                        "portable_archive_file": str(result.portable_install.archive_file),
                        "portable_extracted_entries": list(result.portable_install.extracted_entries),
                        "portable_receipt_file": str(result.portable_install.receipt_file),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.build_installer_staging:
            release_payload = prepare_release_bundle(context, args.build_installer_staging)
            release_archive = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            portable_plan = build_portable_package_plan(
                base_dir,
                context.workspace,
                args.build_installer_staging,
                release_archive,
            )
            portable_manifest = materialize_portable_package(portable_plan, base_dir)
            distribution_plan = build_distribution_package_plan(
                context.workspace,
                args.build_installer_staging,
                portable_plan.archive_file,
                release_archive,
            )
            distribution_manifest = materialize_distribution_package(distribution_plan, base_dir)
            installer_plan = build_installer_staging_plan(
                context.workspace,
                args.build_installer_staging,
                distribution_plan.archive_file,
            )
            installer_manifest = materialize_installer_staging_package(installer_plan, base_dir)
            print(
                json.dumps(
                    {
                        **release_payload,
                        "release_archive_file": str(release_archive),
                        "portable_package_dir": str(portable_plan.package_dir),
                        "portable_archive_file": str(portable_plan.archive_file),
                        "portable_manifest": portable_manifest,
                        "distribution_package_dir": str(distribution_plan.package_dir),
                        "distribution_archive_file": str(distribution_plan.archive_file),
                        "distribution_manifest": distribution_manifest,
                        "installer_package_dir": str(installer_plan.package_dir),
                        "installer_archive_file": str(installer_plan.archive_file),
                        "installer_manifest": installer_manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.install_installer_staging:
            archive_value, staging_dir_value, install_dir_value = args.install_installer_staging
            result = install_installer_staging_package(Path(archive_value), Path(staging_dir_value), Path(install_dir_value))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "staging_dir": str(result.staging_dir),
                        "install_dir": str(result.install_dir),
                        "installer_manifest_file": str(result.installer_manifest_file),
                        "distribution_manifest_file": str(result.distribution_install.distribution_manifest_file),
                        "portable_archive_file": str(result.distribution_install.portable_install.archive_file),
                        "portable_extracted_entries": list(result.distribution_install.portable_install.extracted_entries),
                        "portable_receipt_file": str(result.distribution_install.portable_install.receipt_file),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.verify_installer_staging:
            result = verify_installer_staging_package(Path(args.verify_installer_staging))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "installer_manifest_file": result.installer_manifest_file,
                        "distribution_archive_file": result.distribution_archive_file,
                        "checksum_matches": result.checksum_matches,
                        "install_scripts_present": list(result.install_scripts_present),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.verify_installer_package:
            result = verify_installer_package(Path(args.verify_installer_package))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "installer_package_manifest_file": result.installer_package_manifest_file,
                        "installer_staging_archive_file": result.installer_staging_archive_file,
                        "checksum_matches": result.checksum_matches,
                        "install_scripts_present": list(result.install_scripts_present),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.build_native_installer_scaffold:
            release_payload = prepare_release_bundle(context, args.build_native_installer_scaffold)
            release_archive = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            portable_plan = build_portable_package_plan(
                base_dir,
                context.workspace,
                args.build_native_installer_scaffold,
                release_archive,
            )
            portable_manifest = materialize_portable_package(portable_plan, base_dir)
            distribution_plan = build_distribution_package_plan(
                context.workspace,
                args.build_native_installer_scaffold,
                portable_plan.archive_file,
                release_archive,
            )
            distribution_manifest = materialize_distribution_package(distribution_plan, base_dir)
            installer_staging_plan = build_installer_staging_plan(
                context.workspace,
                args.build_native_installer_scaffold,
                distribution_plan.archive_file,
            )
            installer_staging_manifest = materialize_installer_staging_package(installer_staging_plan, base_dir)
            installer_plan = build_installer_package_plan(
                context.workspace,
                args.build_native_installer_scaffold,
                installer_staging_plan.archive_file,
            )
            installer_manifest = materialize_installer_package(installer_plan, base_dir)
            native_plan = build_native_installer_scaffold_plan(
                context.workspace,
                args.build_native_installer_scaffold,
                installer_plan.archive_file,
            )
            native_manifest = materialize_native_installer_scaffold(native_plan, base_dir)
            print(
                json.dumps(
                    {
                        **release_payload,
                        "release_archive_file": str(release_archive),
                        "portable_archive_file": str(portable_plan.archive_file),
                        "portable_manifest": portable_manifest,
                        "distribution_archive_file": str(distribution_plan.archive_file),
                        "distribution_manifest": distribution_manifest,
                        "installer_staging_archive_file": str(installer_staging_plan.archive_file),
                        "installer_staging_manifest": installer_staging_manifest,
                        "installer_archive_file": str(installer_plan.archive_file),
                        "installer_manifest": installer_manifest,
                        "native_installer_scaffold_dir": str(native_plan.package_dir),
                        "native_installer_manifest_file": str(native_plan.manifest_file),
                        "native_installer_wix_source_file": str(native_plan.wix_source_file),
                        "native_installer_wix_include_file": str(native_plan.wix_include_file),
                        "native_installer_payload_file": str(native_plan.installer_package_file),
                        "native_installer_manifest": native_manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.verify_native_installer_scaffold:
            result = verify_native_installer_scaffold(Path(args.verify_native_installer_scaffold))
            print(
                json.dumps(
                    {
                        "scaffold_dir": str(result.scaffold_dir),
                        "manifest_file": str(result.manifest_file),
                        "wix_source_file": result.wix_source_file,
                        "wix_include_file": result.wix_include_file,
                        "installer_package_file": result.installer_package_file,
                        "checksum_matches": result.checksum_matches,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.build_installer_package:
            release_payload = prepare_release_bundle(context, args.build_installer_package)
            release_archive = package_release_bundle(Path(str(release_payload["bundle_dir"])))
            portable_plan = build_portable_package_plan(
                base_dir,
                context.workspace,
                args.build_installer_package,
                release_archive,
            )
            portable_manifest = materialize_portable_package(portable_plan, base_dir)
            distribution_plan = build_distribution_package_plan(
                context.workspace,
                args.build_installer_package,
                portable_plan.archive_file,
                release_archive,
            )
            distribution_manifest = materialize_distribution_package(distribution_plan, base_dir)
            installer_staging_plan = build_installer_staging_plan(
                context.workspace,
                args.build_installer_package,
                distribution_plan.archive_file,
            )
            installer_staging_manifest = materialize_installer_staging_package(installer_staging_plan, base_dir)
            installer_plan = build_installer_package_plan(
                context.workspace,
                args.build_installer_package,
                installer_staging_plan.archive_file,
            )
            installer_manifest = materialize_installer_package(installer_plan, base_dir)
            print(
                json.dumps(
                    {
                        **release_payload,
                        "release_archive_file": str(release_archive),
                        "portable_package_dir": str(portable_plan.package_dir),
                        "portable_archive_file": str(portable_plan.archive_file),
                        "portable_manifest": portable_manifest,
                        "distribution_package_dir": str(distribution_plan.package_dir),
                        "distribution_archive_file": str(distribution_plan.archive_file),
                        "distribution_manifest": distribution_manifest,
                        "installer_staging_package_dir": str(installer_staging_plan.package_dir),
                        "installer_staging_archive_file": str(installer_staging_plan.archive_file),
                        "installer_staging_manifest": installer_staging_manifest,
                        "installer_package_dir": str(installer_plan.package_dir),
                        "installer_archive_file": str(installer_plan.archive_file),
                        "installer_manifest": installer_manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)

        if args.install_installer_package:
            archive_value, staging_dir_value, install_dir_value = args.install_installer_package
            result = install_installer_package(Path(archive_value), Path(staging_dir_value), Path(install_dir_value))
            print(
                json.dumps(
                    {
                        "archive_file": str(result.archive_file),
                        "staging_dir": str(result.staging_dir),
                        "install_dir": str(result.install_dir),
                        "installer_package_manifest_file": str(result.installer_package_manifest_file),
                        "installer_manifest_file": str(result.installer_staging_install.installer_manifest_file),
                        "distribution_manifest_file": str(result.installer_staging_install.distribution_install.distribution_manifest_file),
                        "portable_archive_file": str(result.installer_staging_install.distribution_install.portable_install.archive_file),
                        "portable_extracted_entries": list(result.installer_staging_install.distribution_install.portable_install.extracted_entries),
                        "portable_receipt_file": str(result.installer_staging_install.distribution_install.portable_install.receipt_file),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(CliExitCode.OK)
    except ProtoLinkUserError as exc:
        formatted_error = format_cli_error(exc, fallback_action="命令行命令")
        _record_cli_failure(
            context,
            code="cli_user_error",
            message=formatted_error,
            command_args=command_args,
            workspace_override=workspace_override,
            recovery=exc.recovery,
        )
        print(formatted_error)
        return int(CliExitCode.USER_ERROR)
    except Exception as exc:
        formatted_error = format_unexpected_cli_error("命令行命令", exc)
        _record_cli_failure(
            context,
            code="cli_runtime_error",
            message=formatted_error,
            command_args=command_args,
            workspace_override=workspace_override,
        )
        print(formatted_error)
        return int(CliExitCode.RUNTIME_ERROR)

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("未安装 GUI 依赖。请执行：uv sync --python 3.11 --extra dev --extra ui")
        return int(CliExitCode.GUI_DEPENDENCY_MISSING)

    from protolink.ui.main_window import ProtoLinkMainWindow
    from protolink.ui.qt_dispatch import QtCallbackDispatcher
    from protolink.ui.theme import APP_STYLESHEET

    app = QApplication([])
    app.setApplicationName("ProtoLink")
    app.setStyleSheet(APP_STYLESHEET)
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.packet_replay_service.set_dispatch_scheduler(dispatcher.dispatch)
    app.aboutToQuit.connect(context.serial_session_service.shutdown)
    app.aboutToQuit.connect(context.mqtt_client_service.shutdown)
    app.aboutToQuit.connect(context.mqtt_server_service.shutdown)
    app.aboutToQuit.connect(context.tcp_client_service.shutdown)
    app.aboutToQuit.connect(context.tcp_server_service.shutdown)
    app.aboutToQuit.connect(context.udp_service.shutdown)
    app.aboutToQuit.connect(context.packet_replay_service.shutdown)
    app.aboutToQuit.connect(context.channel_bridge_runtime_service.shutdown)
    app.aboutToQuit.connect(context.timed_task_service.shutdown)

    window = ProtoLinkMainWindow(
        workspace=context.workspace,
        inspector=context.packet_inspector,
        data_tools_service=context.data_tools_service,
        network_tools_service=context.network_tools_service,
        serial_service=context.serial_session_service,
        mqtt_client_service=context.mqtt_client_service,
        mqtt_server_service=context.mqtt_server_service,
        tcp_client_service=context.tcp_client_service,
        tcp_server_service=context.tcp_server_service,
        udp_service=context.udp_service,
        packet_replay_service=context.packet_replay_service,
        register_monitor_service=context.register_monitor_service,
        rule_engine_service=context.rule_engine_service,
        auto_response_runtime_service=context.auto_response_runtime_service,
        script_console_service=context.script_console_service,
        timed_task_service=context.timed_task_service,
        channel_bridge_runtime_service=context.channel_bridge_runtime_service,
    )
    window.show()
    return app.exec()

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import tempfile
import time

from protolink import __version__
from protolink.catalog import build_module_catalog
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.errors import CliExitCode, ProtoLinkUserError, format_cli_error, format_unexpected_cli_error
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
from protolink.core.logging import default_workspace_log_path
from protolink.core.packaging import (
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
    materialize_portable_package,
    uninstall_portable_package,
    verify_distribution_package,
    verify_portable_package,
    verify_installer_package,
    verify_installer_staging_package,
)
from protolink.core.packet_replay import ReplayDirection, build_packet_replay_plan, default_packet_replay_path, save_packet_replay_plan
from protolink.core.workspace import migrate_workspace, workspace_manifest_path
from protolink.transports.serial import list_serial_ports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ProtoLink desktop application")
    parser.add_argument("--version", action="store_true", help="Print the application version and exit.")
    parser.add_argument(
        "--print-workspace",
        action="store_true",
        help="Initialize the default workspace and print its path.",
    )
    parser.add_argument(
        "--headless-summary",
        action="store_true",
        help="Print a non-GUI project summary for CI or quick verification.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Use the given workspace path and remember it as the active workspace.",
    )
    parser.add_argument(
        "--list-recent-workspaces",
        action="store_true",
        help="Print recently used workspaces and exit.",
    )
    parser.add_argument(
        "--print-settings",
        action="store_true",
        help="Print the path of the persisted settings file and exit.",
    )
    parser.add_argument(
        "--list-serial-ports",
        action="store_true",
        help="Print detected serial ports and exit.",
    )
    parser.add_argument(
        "--create-export-scaffold",
        nargs=3,
        metavar=("KIND", "NAME", "EXT"),
        help="Create an export bundle scaffold under the active workspace exports directory.",
    )
    parser.add_argument(
        "--export-runtime-log",
        metavar="NAME",
        help="Export the current workspace runtime transport log into a real export bundle.",
    )
    parser.add_argument(
        "--export-latest-capture",
        metavar="NAME",
        help="Export the latest workspace capture artifact into a real export bundle.",
    )
    parser.add_argument(
        "--export-latest-profile",
        metavar="NAME",
        help="Export the latest workspace profile artifact into a real export bundle.",
    )
    parser.add_argument(
        "--smoke-check",
        action="store_true",
        help="Run the built-in offscreen smoke check and exit.",
    )
    parser.add_argument(
        "--migrate-workspace",
        action="store_true",
        help="Ensure the active workspace matches the current workspace format and print the migration report.",
    )
    parser.add_argument(
        "--release-preflight",
        action="store_true",
        help="Run a release-preparation preflight against the active workspace and print a JSON report.",
    )
    parser.add_argument(
        "--export-release-bundle",
        metavar="NAME",
        help="Export a release bundle that packages the latest runtime log, capture, profile, and preflight report.",
    )
    parser.add_argument(
        "--generate-smoke-artifacts",
        action="store_true",
        help="Generate real workspace runtime artifacts using a controlled smoke flow.",
    )
    parser.add_argument(
        "--prepare-release",
        metavar="NAME",
        help="Run workspace migration, generate missing smoke artifacts when needed, verify preflight, and export a release bundle.",
    )
    parser.add_argument(
        "--package-release",
        metavar="NAME",
        help="Run release preparation and package the resulting release bundle into a zip archive.",
    )
    parser.add_argument(
        "--build-portable-package",
        metavar="NAME",
        help="Build a portable package zip that contains the packaged release archive plus install metadata.",
    )
    parser.add_argument(
        "--install-portable-package",
        nargs=2,
        metavar=("ARCHIVE", "TARGET_DIR"),
        help="Extract a portable package archive into the target directory.",
    )
    parser.add_argument(
        "--uninstall-portable-package",
        metavar="TARGET_DIR",
        help="Remove files previously installed by a portable package using its install receipt.",
    )
    parser.add_argument(
        "--verify-portable-package",
        metavar="ARCHIVE",
        help="Verify the portable package archive manifest, release archive, and checksums.",
    )
    parser.add_argument(
        "--build-distribution-package",
        metavar="NAME",
        help="Build a distributable package zip that contains portable/release archives plus distribution metadata.",
    )
    parser.add_argument(
        "--verify-distribution-package",
        metavar="ARCHIVE",
        help="Verify the distribution package archive manifest, referenced portable/release archives, and checksums.",
    )
    parser.add_argument(
        "--install-distribution-package",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="Extract a distribution package into a staging directory and install its portable package into the target directory.",
    )
    parser.add_argument(
        "--build-installer-staging",
        metavar="NAME",
        help="Build an installer-staging package that wraps a distribution archive with install metadata and launch scripts.",
    )
    parser.add_argument(
        "--install-installer-staging",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="Extract an installer-staging archive, stage its distribution package, and install the portable package into the target directory.",
    )
    parser.add_argument(
        "--verify-installer-staging",
        metavar="ARCHIVE",
        help="Verify the installer-staging archive manifest, referenced distribution archive, and checksum.",
    )
    parser.add_argument(
        "--build-installer-package",
        metavar="NAME",
        help="Build a top-level installer package archive that wraps the installer-staging package with install metadata.",
    )
    parser.add_argument(
        "--verify-installer-package",
        metavar="ARCHIVE",
        help="Verify the installer package archive manifest, referenced installer-staging archive, and checksum.",
    )
    parser.add_argument(
        "--install-installer-package",
        nargs=3,
        metavar=("ARCHIVE", "STAGING_DIR", "INSTALL_DIR"),
        help="Extract an installer package archive, stage its installer package, and install the portable package into the target directory.",
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
                serial_service=context.serial_session_service,
                mqtt_client_service=context.mqtt_client_service,
                mqtt_server_service=context.mqtt_server_service,
                tcp_client_service=context.tcp_client_service,
                tcp_server_service=context.tcp_server_service,
                udp_service=context.udp_service,
                packet_replay_service=context.packet_replay_service,
                register_monitor_service=context.register_monitor_service,
                rule_engine_service=context.rule_engine_service,
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
    finally:
        app.quit()
        qInstallMessageHandler(previous_qt_message_handler)
    return "smoke-check-ok"


def build_release_preflight_report(context) -> dict[str, object]:
    workspace = context.workspace
    log_file = default_workspace_log_path(workspace.logs)
    profile_candidates = [path for path in workspace.profiles.iterdir() if path.is_file()] if workspace.profiles.exists() else []
    capture_candidates = [path for path in workspace.captures.iterdir() if path.is_file()] if workspace.captures.exists() else []
    smoke_result = run_ui_smoke_check()
    manifest_file = workspace_manifest_path(workspace.root)
    blocking_items: list[str] = []
    if not manifest_file.exists():
        blocking_items.append("workspace_manifest_missing")
    if not log_file.exists():
        blocking_items.append("runtime_log_missing")
    if not profile_candidates:
        blocking_items.append("profile_artifacts_missing")
    if not capture_candidates:
        blocking_items.append("capture_artifacts_missing")
    if smoke_result != "smoke-check-ok":
        blocking_items.append("smoke_check_failed")
    return {
        "workspace": str(workspace.root),
        "manifest_file": str(manifest_file),
        "manifest_exists": manifest_file.exists(),
        "log_file": str(log_file),
        "log_file_exists": log_file.exists(),
        "profile_file_count": len(profile_candidates),
        "capture_file_count": len(capture_candidates),
        "exports_dir": str(workspace.exports),
        "smoke_check": smoke_result,
        "blocking_items": blocking_items,
        "ready": not blocking_items,
    }


def find_optional_latest_file(directory: Path) -> Path | None:
    try:
        return find_latest_artifact_file(directory)
    except ProtoLinkUserError:
        return None


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
        raise RuntimeError(service.snapshot.last_error or "Serial smoke session failed to connect.")

    log_count_before = len(context.log_store.latest(500))
    service.send_replay_payload(b"\x01\x03\x00\x0A\x00\x02", {"source": "release_smoke", "protocol": "modbus_rtu"})
    _wait_until(lambda: len(context.log_store.latest(500)) > log_count_before)
    _wait_until(lambda: default_workspace_log_path(context.workspace.logs).exists())

    plan = build_packet_replay_plan(
        context.log_store.latest(500),
        name="release-smoke-capture",
        include_directions={ReplayDirection.OUTBOUND, ReplayDirection.INBOUND},
    )
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
    capture_file = find_optional_latest_file(context.workspace.captures)
    if not log_file.exists() or capture_file is None:
        generated_artifacts = generate_smoke_artifacts(context)

    preflight_report = build_release_preflight_report(context)
    if not preflight_report["ready"]:
        blocking = ", ".join(str(item) for item in preflight_report["blocking_items"]) or "unknown"
        raise ProtoLinkUserError(
            "Release preflight is not ready.",
            action="prepare release",
            recovery=f"Resolve blocking items: {blocking}.",
        )

    plan = build_release_bundle_plan(
        context.workspace,
        name,
        runtime_log_file=default_workspace_log_path(context.workspace.logs),
        latest_capture_file=find_optional_latest_file(context.workspace.captures),
        latest_profile_file=find_optional_latest_file(context.workspace.profiles),
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

    base_dir = Path.cwd()

    if args.version:
        print(__version__)
        return int(CliExitCode.OK)

    try:
        if args.list_serial_ports:
            for port in list_serial_ports():
                print(f"{port.device}\t{port.description}\t{port.hardware_id}")
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
                bool(args.install_installer_package),
            )
        )
        context = bootstrap_app_context(
            base_dir,
            workspace_override=Path(args.workspace) if args.workspace else None,
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
            print("Goal: Windows-first industrial communication and protocol debugging platform")
            print(f"Workspace: {context.workspace.root}")
            print(f"Settings: {context.settings_layout.settings_file}")
            print(f"Registered transports: {len(context.transport_registry.registered_kinds())}")
            print(f"Modules: {len(modules)}")
            for name in ("Bootstrapped", "Next", "Planned"):
                print(f"{name}: {counts.get(name, 0)}")
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
                print("GUI dependencies are not installed. Run: uv sync --python 3.11 --extra dev --extra ui")
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
                latest_capture_file=find_optional_latest_file(context.workspace.captures),
                latest_profile_file=find_optional_latest_file(context.workspace.profiles),
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
        print(format_cli_error(exc, fallback_action="CLI command"))
        return int(CliExitCode.USER_ERROR)
    except Exception as exc:
        print(format_unexpected_cli_error("CLI command", exc))
        return int(CliExitCode.RUNTIME_ERROR)

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("GUI dependencies are not installed. Run: uv sync --python 3.11 --extra dev --extra ui")
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

    window = ProtoLinkMainWindow(
        workspace=context.workspace,
        inspector=context.packet_inspector,
        serial_service=context.serial_session_service,
        mqtt_client_service=context.mqtt_client_service,
        mqtt_server_service=context.mqtt_server_service,
        tcp_client_service=context.tcp_client_service,
        tcp_server_service=context.tcp_server_service,
        udp_service=context.udp_service,
        packet_replay_service=context.packet_replay_service,
        register_monitor_service=context.register_monitor_service,
        rule_engine_service=context.rule_engine_service,
    )
    window.show()
    return app.exec()

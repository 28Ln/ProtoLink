from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOLINK_BASE_DIR_ENV = "PROTOLINK_BASE_DIR"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 ProtoLink 的 release-staging 安装与运行链路。")
    parser.add_argument("--name", default="release-staging", help="产物名称前缀。")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留临时暂存、安装和工作区目录。")
    parser.add_argument(
        "--skip-native-installer-lane",
        action="store_true",
        help="跳过附加的 native installer lane 结构化探针。",
    )
    return parser


def _run_command(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def _run_json(command: list[str]) -> dict[str, object]:
    completed = _run_command(command)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            "Command did not return JSON:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}"
        ) from exc


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _python(script: Path, *args: str) -> list[str]:
    return [sys.executable, str(script), *args]


def _sanitized_environment(*, python_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "__PYVENV_LAUNCHER__",
        PROTOLINK_BASE_DIR_ENV,
    ):
        env.pop(variable, None)
    if python_path is not None:
        env["PYTHONPATH"] = str(python_path)
    return env


def _parse_headless_summary(label: str, output: str, install_root: Path) -> dict[str, object]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or lines[0] != "ProtoLink":
        raise SystemExit(f"{label} did not produce the expected headless summary output.\n\nstdout:\n{output}")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        separator = "："
        if separator in line:
            key, value = line.split(separator, 1)
            fields[key.strip()] = value.strip()
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()

    workspace = Path(fields.get("工作区", "")).resolve()
    settings = Path(fields.get("设置", "")).resolve()
    install_root = install_root.resolve()
    if not workspace.exists():
        raise SystemExit(f"{label} reported a workspace that does not exist: {workspace}")
    if not workspace.is_relative_to(install_root):
        raise SystemExit(
            f"{label} escaped the install root.\nworkspace: {workspace}\ninstall_root: {install_root}"
        )
    if not settings.is_relative_to(install_root):
        raise SystemExit(
            f"{label} escaped the install root.\nsettings: {settings}\ninstall_root: {install_root}"
        )

    return {
        "workspace": str(workspace),
        "settings": str(settings),
        "summary_lines": lines,
    }


def execute_release_staging(
    *,
    name: str = "release-staging",
    workspace: Path | None = None,
    include_native_installer_lane: bool = True,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-release-staging-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()
    temp_root = workspace.parent if temp_root is None else temp_root
    staging_dir = temp_root / "installer-staging"
    install_dir = temp_root / "installer-install"

    generate_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--generate-smoke-artifacts"))
    build_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--build-installer-package", name))

    portable_archive = str(build_payload["portable_archive_file"])
    distribution_archive = str(build_payload["distribution_archive_file"])
    installer_archive = str(build_payload["installer_archive_file"])

    verify_portable = _run_json(_uv("protolink", "--verify-portable-package", portable_archive))
    verify_distribution = _run_json(_uv("protolink", "--verify-distribution-package", distribution_archive))
    verify_installer = _run_json(_uv("protolink", "--verify-installer-package", installer_archive))

    install_payload = _run_json(
        _uv(
            "protolink",
            "--install-installer-package",
            installer_archive,
            str(staging_dir),
            str(install_dir),
        )
    )

    required_files = {
        "installer_package_manifest_file": install_payload["installer_package_manifest_file"],
        "installer_manifest_file": install_payload["installer_manifest_file"],
        "distribution_manifest_file": install_payload["distribution_manifest_file"],
        "portable_receipt_file": install_payload["portable_receipt_file"],
    }
    for label, path_value in required_files.items():
        if not Path(str(path_value)).exists():
            raise SystemExit(f"Release-staging verification is missing expected file: {label} -> {path_value}")

    installed_scripts = {
        "install_script": install_dir / "INSTALL.ps1",
        "launch_ps1": install_dir / "Launch-ProtoLink.ps1",
        "launch_bat": install_dir / "Launch-ProtoLink.bat",
    }
    for label, path_value in installed_scripts.items():
        if not path_value.exists():
            raise SystemExit(f"Release-staging verification is missing expected installed script: {label} -> {path_value}")

    runtime_python = install_dir / "runtime" / "python.exe"
    site_packages = install_dir / "sp"
    if not runtime_python.exists():
        raise SystemExit(f"Bundled runtime executable was not installed: {runtime_python}")
    if not site_packages.exists():
        raise SystemExit(f"Bundled site-packages directory was not installed: {site_packages}")
    launcher_exe = install_dir / "ProtoLink.exe"
    if not launcher_exe.exists():
        raise SystemExit(f"Native launcher executable was not installed: {launcher_exe}")

    runtime_env = _sanitized_environment(python_path=site_packages)
    installed_summary = _run_command(
        [str(runtime_python), "-m", "protolink", "--headless-summary"],
        env=runtime_env,
        cwd=temp_root,
    ).stdout
    installed_summary_details = _parse_headless_summary(
        "runtime/python.exe -m protolink --headless-summary",
        installed_summary,
        install_dir,
    )
    launcher_exe_summary = _run_command(
        [str(launcher_exe), "--headless-summary"],
        env=_sanitized_environment(),
        cwd=temp_root,
    ).stdout
    launcher_exe_details = _parse_headless_summary("ProtoLink.exe", launcher_exe_summary, install_dir)

    launcher_env = _sanitized_environment()
    install_script_summary = _run_command(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(installed_scripts["install_script"])],
        env=launcher_env,
        cwd=temp_root,
    ).stdout
    install_script_details = _parse_headless_summary("INSTALL.ps1", install_script_summary, install_dir)
    launch_ps1_summary = _run_command(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(installed_scripts["launch_ps1"]),
            "--headless-summary",
        ],
        env=launcher_env,
        cwd=temp_root,
    ).stdout
    launch_ps1_details = _parse_headless_summary("Launch-ProtoLink.ps1", launch_ps1_summary, install_dir)
    launch_bat_summary = _run_command(
        ["cmd", "/c", str(installed_scripts["launch_bat"]), "--headless-summary"],
        env=launcher_env,
        cwd=temp_root,
    ).stdout
    launch_bat_details = _parse_headless_summary("Launch-ProtoLink.bat", launch_bat_summary, install_dir)

    uninstall_payload = _run_json(_uv("protolink", "--uninstall-portable-package", str(install_dir)))
    if not uninstall_payload.get("removed_receipt"):
        raise SystemExit("Portable uninstall did not remove the install receipt.")

    native_installer_lane = None
    if include_native_installer_lane:
        native_workspace = temp_root / "ni"
        native_installer_lane = _run_json(
            _python(
                ROOT / "scripts" / "verify_native_installer_lane.py",
                "--workspace",
                str(native_workspace),
                "--name",
                f"{name}-native",
            )
        )

    return {
        "workspace": str(workspace),
        "temp_root": str(temp_root),
        "generate_smoke_artifacts": {
            "log_file": generate_payload["log_file"],
            "capture_file": generate_payload["capture_file"],
            "replay_step_count": generate_payload["replay_step_count"],
        },
        "build_installer_package": {
            "release_archive_file": build_payload["release_archive_file"],
            "portable_archive_file": build_payload["portable_archive_file"],
            "distribution_archive_file": build_payload["distribution_archive_file"],
            "installer_archive_file": build_payload["installer_archive_file"],
        },
        "verify_portable_package": {
            "archive_file": verify_portable["archive_file"],
            "checksum_matches": verify_portable["checksum_matches"],
        },
        "verify_distribution_package": {
            "archive_file": verify_distribution["archive_file"],
            "checksum_matches": verify_distribution["checksum_matches"],
        },
        "verify_installer_package": {
            "archive_file": verify_installer["archive_file"],
            "checksum_matches": verify_installer["checksum_matches"],
        },
        "install_installer_package": {
            "archive_file": install_payload["archive_file"],
            "install_dir": install_payload["install_dir"],
            "portable_receipt_file": install_payload["portable_receipt_file"],
        },
            "installed_headless_summary": installed_summary_details,
            "launcher_exe_headless_summary": launcher_exe_details,
            "install_script_headless_summary": install_script_details,
            "launch_ps1_headless_summary": launch_ps1_details,
            "launch_bat_headless_summary": launch_bat_details,
        "uninstall_portable_package": {
            "target_dir": uninstall_payload["target_dir"],
            "removed_receipt": uninstall_payload["removed_receipt"],
        },
        "native_installer_lane": native_installer_lane,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute_release_staging(
            name=args.name,
            include_native_installer_lane=not args.skip_native_installer_lane,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        temp_root = Path(str(result["temp_root"])) if 'result' in locals() else None
        if not args.keep_artifacts:
            if temp_root is not None:
                shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

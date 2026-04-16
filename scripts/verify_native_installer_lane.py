from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验证 ProtoLink 的 native installer lane（toolchain / scaffold / msi / signature）。")
    parser.add_argument("--workspace", type=Path, help="可选，使用指定 workspace。默认创建临时 workspace。")
    parser.add_argument("--name", default="native-lane", help="scaffold/build 名称前缀。")
    parser.add_argument("--require-toolchain", action="store_true", help="若 WiX 或 SignTool 缺失则返回非零退出码。")
    parser.add_argument("--require-signed", action="store_true", help="若 MSI 签名校验未通过则返回非零退出码。")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留临时目录。")
    return parser


def _run_command(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return completed


def _run_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    completed = _run_command(command, cwd=cwd)
    if completed.returncode != 0:
        raise VerificationError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(
            "Command did not return JSON:\n"
            f"{' '.join(command)}\n\nstdout:\n{completed.stdout}"
        ) from exc


def _run_optional_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    completed = _run_command(command, cwd=cwd)
    payload: dict[str, object] | None = None
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload": payload,
    }


def _run_optional_command(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _tool_available(toolchain: dict[str, object], tool_key: str) -> bool:
    tools = toolchain.get("tools", {})
    if not isinstance(tools, dict):
        return False
    payload = tools.get(tool_key, {})
    return isinstance(payload, dict) and bool(payload.get("available", False))


def _build_lane_readiness(
    *,
    toolchain: dict[str, object],
    scaffold_built: bool,
    scaffold_verified: bool,
    msi_built: bool,
    msi_installed: bool,
    installed_payload_verified: bool,
    installed_payload_runnable: bool,
    msi_uninstalled: bool,
    signature_verified: bool,
) -> dict[str, bool]:
    wix_available = _tool_available(toolchain, "wix")
    signtool_available = _tool_available(toolchain, "signtool")
    ready_for_build = scaffold_built and scaffold_verified and wix_available
    ready_for_install_verification = (
        ready_for_build and msi_built and msi_installed and installed_payload_verified and installed_payload_runnable and msi_uninstalled
    )
    ready_for_signing = ready_for_install_verification and signtool_available
    ready_for_release = ready_for_signing and signature_verified
    return {
        "ready_for_build": ready_for_build,
        "ready_for_install_verification": ready_for_install_verification,
        "ready_for_signing": ready_for_signing,
        "ready_for_release": ready_for_release,
    }


def _build_lane_blocking_items(
    *,
    toolchain: dict[str, object],
    scaffold_built: bool,
    scaffold_verified: bool,
    msi_build: dict[str, object] | None,
    msi_install: dict[str, object] | None,
    installed_payload_file: Path | None,
    installed_payload_verify: dict[str, object] | None,
    installed_payload_install: dict[str, object] | None,
    installed_headless_summary: dict[str, object] | None,
    msi_uninstall: dict[str, object] | None,
    signature_verify: dict[str, object] | None,
) -> list[str]:
    blocking_items: list[str] = []
    if not _tool_available(toolchain, "wix"):
        blocking_items.append("native_installer_wix_missing")
    if not _tool_available(toolchain, "signtool"):
        blocking_items.append("native_installer_signtool_missing")
    if not scaffold_built:
        blocking_items.append("native_installer_scaffold_not_built")
    if not scaffold_verified:
        blocking_items.append("native_installer_scaffold_invalid")
    if _tool_available(toolchain, "wix") and msi_build is not None and not bool(msi_build.get("ok")):
        blocking_items.append("native_installer_msi_build_failed")
    if _tool_available(toolchain, "wix") and msi_build is None:
        blocking_items.append("native_installer_msi_not_attempted")
    if msi_install is not None and not bool(msi_install.get("ok")):
        blocking_items.append("native_installer_msi_install_failed")
    if msi_install is not None and installed_payload_file is None:
        blocking_items.append("native_installer_installed_payload_missing")
    if installed_payload_verify is not None and not bool(installed_payload_verify.get("ok")):
        blocking_items.append("native_installer_installed_payload_invalid")
    if installed_payload_install is not None and not bool(installed_payload_install.get("ok")):
        blocking_items.append("native_installer_installed_payload_install_failed")
    if installed_payload_install is not None and installed_headless_summary is None:
        blocking_items.append("native_installer_installed_payload_not_runnable")
    if msi_uninstall is not None and not bool(msi_uninstall.get("ok")):
        blocking_items.append("native_installer_msi_uninstall_failed")
    if _tool_available(toolchain, "signtool") and signature_verify is None:
        blocking_items.append("native_installer_signature_not_attempted")
    if signature_verify is not None and not bool(signature_verify.get("ok")):
        blocking_items.append("native_installer_signature_not_verified")
    return blocking_items


def _build_lane_status(
    *,
    readiness: dict[str, bool],
    blocking_items: list[str],
) -> str:
    if readiness["ready_for_release"]:
        return "signed_ready"
    if any(item in blocking_items for item in ("native_installer_wix_missing", "native_installer_signtool_missing")):
        return "toolchain_missing"
    if "native_installer_scaffold_invalid" in blocking_items or "native_installer_scaffold_not_built" in blocking_items:
        return "scaffold_not_ready"
    if "native_installer_msi_build_failed" in blocking_items or "native_installer_msi_not_attempted" in blocking_items:
        return "msi_not_ready"
    if (
        "native_installer_signature_not_attempted" in blocking_items
        or "native_installer_signature_not_verified" in blocking_items
    ):
        return "signature_not_ready"
    return "probe_only"


def _build_next_actions(*, blocking_items: list[str]) -> list[str]:
    actions: list[str] = []
    if "native_installer_wix_missing" in blocking_items:
        actions.append("Install WiX Toolset v4 or set PROTOLINK_WIX before attempting MSI builds.")
    if "native_installer_signtool_missing" in blocking_items:
        actions.append("Install Windows SDK signing tools or set PROTOLINK_SIGNTOOL before signature verification.")
    if "native_installer_scaffold_not_built" in blocking_items:
        actions.append("Build a fresh native installer scaffold and verify its manifest / payload mapping.")
    if "native_installer_scaffold_invalid" in blocking_items:
        actions.append("Repair scaffold generation or payload checksums before continuing the installer lane.")
    if "native_installer_msi_not_attempted" in blocking_items:
        actions.append("Run MSI build once WiX is available to move the lane from scaffold-ready to build-ready.")
    if "native_installer_msi_build_failed" in blocking_items:
        actions.append("Fix the WiX/MSI build failure and rerun lane validation before signing.")
    if "native_installer_msi_install_failed" in blocking_items:
        actions.append("Fix the MSI install behavior or INSTALLDIR override before using the native installer lane as a release gate.")
    if "native_installer_installed_payload_missing" in blocking_items:
        actions.append("Ensure MSI install lays down the installer-package payload under the expected payload directory.")
    if "native_installer_installed_payload_invalid" in blocking_items:
        actions.append("Repair the installed payload contents until verify-installer-package succeeds against the MSI-installed archive.")
    if "native_installer_installed_payload_install_failed" in blocking_items:
        actions.append("Fix the installer-package install chain extracted from the MSI-installed payload.")
    if "native_installer_installed_payload_not_runnable" in blocking_items:
        actions.append("Fix the runnable install smoke so the MSI-installed payload can pass headless-summary.")
    if "native_installer_msi_uninstall_failed" in blocking_items:
        actions.append("Fix MSI uninstall behavior before promoting the native installer lane.")
    if "native_installer_signature_not_attempted" in blocking_items:
        actions.append("Run signature verification after producing an MSI and wiring the signing toolchain.")
    if "native_installer_signature_not_verified" in blocking_items:
        actions.append("Fix Authenticode signing or timestamp configuration until MSI signature verification passes.")
    return actions


def _sanitized_environment(*, python_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "__PYVENV_LAUNCHER__",
        "PROTOLINK_BASE_DIR",
    ):
        env.pop(variable, None)
    if python_path is not None:
        env["PYTHONPATH"] = str(python_path)
    return env


def _parse_headless_summary(output: str, *, install_root: Path) -> dict[str, object]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or lines[0] != "ProtoLink":
        raise VerificationError(f"Unexpected headless summary output:\n{output}")

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
        raise VerificationError(f"Installed headless summary reported a missing workspace: {workspace}")
    if not workspace.is_relative_to(install_root):
        raise VerificationError(f"Installed workspace escaped install root: {workspace}")
    if not settings.is_relative_to(install_root):
        raise VerificationError(f"Installed settings escaped install root: {settings}")

    return {
        "workspace": str(workspace),
        "settings": str(settings),
        "summary_lines": lines,
    }


def _summarize_scaffold_build(scaffold_build: dict[str, object]) -> dict[str, object]:
    preflight = scaffold_build.get("preflight", {})
    generated_artifacts = scaffold_build.get("generated_artifacts", {})
    native_manifest = scaffold_build.get("native_installer_manifest", {})
    migration = scaffold_build.get("migration", {})
    blocking_items = preflight.get("blocking_items", []) if isinstance(preflight, dict) else []
    verification_expectations = (
        native_manifest.get("verification_expectations", [])
        if isinstance(native_manifest, dict)
        else []
    )
    return {
        "workspace": scaffold_build.get("workspace"),
        "migration_changed": bool(migration.get("changed", False)) if isinstance(migration, dict) else False,
        "generated_artifacts": {
            "log_file": generated_artifacts.get("log_file") if isinstance(generated_artifacts, dict) else None,
            "capture_file": generated_artifacts.get("capture_file") if isinstance(generated_artifacts, dict) else None,
            "replay_step_count": generated_artifacts.get("replay_step_count") if isinstance(generated_artifacts, dict) else None,
        },
        "preflight_ready": bool(preflight.get("ready", False)) if isinstance(preflight, dict) else False,
        "blocking_items": list(blocking_items) if isinstance(blocking_items, list) else [],
        "release_archive_file": scaffold_build.get("release_archive_file"),
        "portable_archive_file": scaffold_build.get("portable_archive_file"),
        "distribution_archive_file": scaffold_build.get("distribution_archive_file"),
        "installer_staging_archive_file": scaffold_build.get("installer_staging_archive_file"),
        "installer_archive_file": scaffold_build.get("installer_archive_file"),
        "native_installer_scaffold_dir": scaffold_build.get("native_installer_scaffold_dir"),
        "native_installer_manifest_file": scaffold_build.get("native_installer_manifest_file"),
        "native_installer_wix_source_file": scaffold_build.get("native_installer_wix_source_file"),
        "native_installer_wix_include_file": scaffold_build.get("native_installer_wix_include_file"),
        "native_installer_payload_file": scaffold_build.get("native_installer_payload_file"),
        "application_version": native_manifest.get("application_version") if isinstance(native_manifest, dict) else None,
        "wix_product_version": native_manifest.get("wix_product_version") if isinstance(native_manifest, dict) else None,
        "verification_expectations": list(verification_expectations) if isinstance(verification_expectations, list) else [],
    }


def execute_native_installer_lane(
    *,
    workspace: Path | None = None,
    name: str = "native-lane",
    require_toolchain: bool = False,
    require_signed: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-native-installer-lane-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()
    started_at = time.perf_counter()

    toolchain = _run_json(_uv("protolink", "--verify-native-installer-toolchain"))
    scaffold_build_raw = _run_json(_uv("protolink", "--workspace", str(workspace), "--build-native-installer-scaffold", name))
    scaffold_build = _summarize_scaffold_build(scaffold_build_raw)
    scaffold_dir = Path(str(scaffold_build["native_installer_scaffold_dir"])).resolve()
    scaffold_verify = _run_json(_uv("protolink", "--verify-native-installer-scaffold", str(scaffold_dir)))

    msi_build = None
    msi_install = None
    installed_payload_verify = None
    installed_payload_install = None
    installed_headless_summary = None
    installed_payload_uninstall = None
    msi_uninstall = None
    signature_verify = None
    msi_file: Path | None = None
    installed_payload_file: Path | None = None

    if _tool_available(toolchain, "wix"):
        msi_build = _run_optional_json(_uv("protolink", "--build-native-installer-msi", str(scaffold_dir)))
        payload = msi_build.get("payload") if isinstance(msi_build, dict) else None
        if isinstance(payload, dict) and payload.get("output_file"):
            msi_file = Path(str(payload["output_file"])).resolve()

    if msi_file is not None:
        install_root = workspace.parent / "native-msi-install"
        install_log = workspace.parent / "native-msi-install.log"
        uninstall_log = workspace.parent / "native-msi-uninstall.log"
        msi_install = _run_optional_command(
            [
                "msiexec",
                "/i",
                str(msi_file),
                "/qn",
                "/norestart",
                f"INSTALLDIR={install_root}",
                "/l*v",
                str(install_log),
            ]
        )
        expected_installed_payload = install_root / "payload" / Path(str(scaffold_build["native_installer_payload_file"])).name
        installed_payload_file = expected_installed_payload if expected_installed_payload.exists() else None
        if installed_payload_file is not None:
            installed_payload_verify = _run_optional_json(
                _uv("protolink", "--verify-installer-package", str(installed_payload_file))
            )
            payload_staging_dir = workspace.parent / "native-msi-payload-staging"
            payload_install_dir = workspace.parent / "native-msi-payload-install"
            installed_payload_install = _run_optional_json(
                _uv(
                    "protolink",
                    "--install-installer-package",
                    str(installed_payload_file),
                    str(payload_staging_dir),
                    str(payload_install_dir),
                )
            )
            if bool(installed_payload_install.get("ok")):
                payload = installed_payload_install.get("payload")
                if isinstance(payload, dict):
                    runtime_python = Path(str(payload["install_dir"])) / "runtime" / "python.exe"
                    site_packages = Path(str(payload["install_dir"])) / "sp"
                    if runtime_python.exists() and site_packages.exists():
                        headless = _run_optional_command(
                            [str(runtime_python), "-m", "protolink", "--headless-summary"],
                            cwd=workspace.parent,
                            env=_sanitized_environment(python_path=site_packages),
                        )
                        if bool(headless.get("ok")):
                            installed_headless_summary = _parse_headless_summary(
                                str(headless.get("stdout", "")),
                                install_root=Path(str(payload["install_dir"])),
                            )
                    installed_payload_uninstall = _run_optional_json(
                        _uv("protolink", "--uninstall-portable-package", str(payload["install_dir"]))
                    )
        msi_uninstall = _run_optional_command(
            [
                "msiexec",
                "/x",
                str(msi_file),
                "/qn",
                "/norestart",
                "/l*v",
                str(uninstall_log),
            ]
        )

    if msi_file is not None and _tool_available(toolchain, "signtool"):
        signature_verify = _run_optional_json(_uv("protolink", "--verify-native-installer-signature", str(msi_file)))

    stage_status = {
        "toolchain_ready": bool(toolchain.get("ready", False)),
        "scaffold_built": bool(scaffold_build.get("native_installer_scaffold_dir")),
        "scaffold_verified": bool(scaffold_verify.get("checksum_matches", False)),
        "msi_built": bool(msi_build and msi_build.get("ok")),
        "msi_installed": bool(msi_install and msi_install.get("ok")),
        "installed_payload_verified": bool(installed_payload_verify and installed_payload_verify.get("ok")),
        "installed_payload_runnable": installed_headless_summary is not None,
        "msi_uninstalled": bool(msi_uninstall and msi_uninstall.get("ok")),
        "signature_verified": bool(signature_verify and signature_verify.get("ok")),
    }
    readiness = _build_lane_readiness(
        toolchain=toolchain,
        scaffold_built=stage_status["scaffold_built"],
        scaffold_verified=stage_status["scaffold_verified"],
        msi_built=stage_status["msi_built"],
        msi_installed=stage_status["msi_installed"],
        installed_payload_verified=stage_status["installed_payload_verified"],
        installed_payload_runnable=stage_status["installed_payload_runnable"],
        msi_uninstalled=stage_status["msi_uninstalled"],
        signature_verified=stage_status["signature_verified"],
    )
    blocking_items = _build_lane_blocking_items(
        toolchain=toolchain,
        scaffold_built=stage_status["scaffold_built"],
        scaffold_verified=stage_status["scaffold_verified"],
        msi_build=msi_build,
        msi_install=msi_install,
        installed_payload_file=installed_payload_file,
        installed_payload_verify=installed_payload_verify,
        installed_payload_install=installed_payload_install,
        installed_headless_summary=installed_headless_summary,
        msi_uninstall=msi_uninstall,
        signature_verify=signature_verify,
    )
    lane_status = _build_lane_status(
        readiness=readiness,
        blocking_items=blocking_items,
    )
    next_actions = _build_next_actions(blocking_items=blocking_items)

    result = {
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "stage_status": stage_status,
        "readiness": readiness,
        "lane_status": lane_status,
        "blocking_items": blocking_items,
        "next_actions": next_actions,
        "toolchain": toolchain,
        "scaffold_build": scaffold_build,
        "scaffold_verify": scaffold_verify,
        "msi_build": msi_build,
        "msi_file": str(msi_file) if msi_file is not None else None,
        "msi_install": msi_install,
        "installed_payload_file": str(installed_payload_file) if installed_payload_file is not None else None,
        "installed_payload_verify": installed_payload_verify,
        "installed_payload_install": installed_payload_install,
        "installed_headless_summary": installed_headless_summary,
        "installed_payload_uninstall": installed_payload_uninstall,
        "msi_uninstall": msi_uninstall,
        "signature_verify": signature_verify,
        "ready_for_release": readiness["ready_for_release"],
    }

    if require_toolchain and not bool(toolchain.get("ready", False)):
        raise VerificationError("Native installer toolchain is not ready on this machine.")
    if require_signed and not readiness["ready_for_release"]:
        raise VerificationError("Native installer lane is not signed-and-ready on this machine.")
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    temp_root: Path | None = None
    workspace = args.workspace
    try:
        result = execute_native_installer_lane(
            workspace=workspace,
            name=args.name,
            require_toolchain=args.require_toolchain,
            require_signed=args.require_signed,
        )
        if args.workspace is None and not args.keep_artifacts:
            temporary_root = result.get("temporary_root")
            temp_root = Path(str(temporary_root)).resolve() if temporary_root else None
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root is not None and not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

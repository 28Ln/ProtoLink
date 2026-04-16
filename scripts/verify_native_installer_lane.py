from __future__ import annotations

import argparse
import json
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


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _tool_available(toolchain: dict[str, object], tool_key: str) -> bool:
    tools = toolchain.get("tools", {})
    if not isinstance(tools, dict):
        return False
    payload = tools.get(tool_key, {})
    return isinstance(payload, dict) and bool(payload.get("available", False))


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


def _native_installer_lane_phase(stage_status: dict[str, bool]) -> str:
    if stage_status.get("signature_verified", False):
        return "signed-release-candidate"
    if stage_status.get("msi_built", False):
        return "unsigned-msi"
    if (
        stage_status.get("scaffold_built", False)
        and stage_status.get("scaffold_verified", False)
        and not stage_status.get("lifecycle_contract_ready", False)
    ):
        return "contract-incomplete"
    if stage_status.get("toolchain_ready", False):
        return "toolchain-ready"
    if stage_status.get("scaffold_built", False) and stage_status.get("scaffold_verified", False):
        return "probe-only"
    return "probe-failed"


def _build_cutover_policy(
    *,
    toolchain: dict[str, object],
    stage_status: dict[str, bool],
    ready_for_release: bool,
) -> dict[str, object]:
    probe_ready = bool(stage_status.get("scaffold_built", False) and stage_status.get("scaffold_verified", False))
    blocking_items: list[str] = []

    if not stage_status.get("scaffold_built", False):
        blocking_items.append("scaffold_not_built")
    if not stage_status.get("scaffold_verified", False):
        blocking_items.append("scaffold_not_verified")
    if stage_status.get("scaffold_verified", False) and not stage_status.get("lifecycle_contract_ready", False):
        blocking_items.append("lifecycle_contract_incomplete")
    if not _tool_available(toolchain, "wix"):
        blocking_items.append("missing_wix")
    if not _tool_available(toolchain, "signtool"):
        blocking_items.append("missing_signtool")
    if probe_ready and _tool_available(toolchain, "wix") and not stage_status.get("msi_built", False):
        blocking_items.append("msi_not_built")
    if stage_status.get("msi_built", False) and not stage_status.get("signature_verified", False):
        blocking_items.append("signature_not_verified")

    if not probe_ready:
        next_action = "stabilize_scaffold_probe"
    elif not stage_status.get("lifecycle_contract_ready", False):
        next_action = "repair_lifecycle_contract"
    elif not stage_status.get("toolchain_ready", False):
        next_action = "install_wix_and_signtool"
    elif not stage_status.get("msi_built", False):
        next_action = "build_unsigned_msi"
    elif not stage_status.get("signature_verified", False):
        next_action = "sign_and_verify_msi"
    else:
        next_action = "run_cutover_install_validation"

    return {
        "current_canonical_release_lane": "bundled-runtime-installer-package",
        "native_installer_lane_phase": _native_installer_lane_phase(stage_status),
        "probe_ready": probe_ready,
        "cutover_ready": ready_for_release,
        "blocking_items": blocking_items,
        "next_action": next_action,
        "manual_cutover_requirements": [
            "approved_code_signing_certificate",
            "approved_rfc3161_timestamp_service",
            "documented_release_approval",
            "bundled_runtime_rollback_artifact_retained",
        ],
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
    signature_verify = None
    msi_file: Path | None = None

    if _tool_available(toolchain, "wix"):
        msi_build = _run_optional_json(_uv("protolink", "--build-native-installer-msi", str(scaffold_dir)))
        payload = msi_build.get("payload") if isinstance(msi_build, dict) else None
        if isinstance(payload, dict) and payload.get("output_file"):
            msi_file = Path(str(payload["output_file"])).resolve()

    if msi_file is not None and _tool_available(toolchain, "signtool"):
        signature_verify = _run_optional_json(_uv("protolink", "--verify-native-installer-signature", str(msi_file)))

    stage_status = {
        "toolchain_ready": bool(toolchain.get("ready", False)),
        "scaffold_built": bool(scaffold_build.get("native_installer_scaffold_dir")),
        "scaffold_verified": bool(scaffold_verify.get("checksum_matches", False)),
        "lifecycle_contract_ready": bool(scaffold_verify.get("lifecycle_contract_ready", False)),
        "msi_built": bool(msi_build and msi_build.get("ok")),
        "signature_verified": bool(signature_verify and signature_verify.get("ok")),
    }
    ready_for_release = all(stage_status.values())
    cutover_policy = _build_cutover_policy(
        toolchain=toolchain,
        stage_status=stage_status,
        ready_for_release=ready_for_release,
    )

    result = {
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "stage_status": stage_status,
        "cutover_policy": cutover_policy,
        "toolchain": toolchain,
        "scaffold_build": scaffold_build,
        "scaffold_verify": scaffold_verify,
        "msi_build": msi_build,
        "signature_verify": signature_verify,
        "ready_for_release": ready_for_release,
    }

    if require_toolchain and not bool(toolchain.get("ready", False)):
        raise VerificationError("Native installer toolchain is not ready on this machine.")
    if require_signed and not ready_for_release:
        raise VerificationError("Native installer lane is not signed-and-ready on this machine.")
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    temp_root: Path | None = None
    if args.workspace is None and not args.keep_artifacts:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-native-installer-lane-main-"))
        workspace = temp_root / "workspace"
    else:
        workspace = args.workspace
    try:
        result = execute_native_installer_lane(
            workspace=workspace,
            name=args.name,
            require_toolchain=args.require_toolchain,
            require_signed=args.require_signed,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root is not None and not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

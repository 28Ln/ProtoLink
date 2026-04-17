from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from protolink.core.native_installer_cutover_evidence import load_native_installer_cutover_evidence
from protolink.core.native_installer_cutover_policy import load_native_installer_cutover_policy


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验证 ProtoLink 的 native installer lane（toolchain / scaffold / msi / signature）。")
    parser.add_argument("--workspace", type=Path, help="可选，使用指定 workspace。默认创建临时 workspace。")
    parser.add_argument("--name", default="native-lane", help="scaffold/build 名称前缀。")
    parser.add_argument("--receipt-file", type=Path, help="可选，写出 native installer lane JSON receipt。")
    parser.add_argument("--cutover-evidence-file", type=Path, help="可选，提供 native installer cutover evidence JSON。")
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


def _write_json_file(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


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


def _build_policy_status(
    *,
    policy: dict[str, object],
    stage_status: dict[str, bool],
    scaffold_build: dict[str, object],
    cutover_evidence: dict[str, object],
) -> dict[str, object]:
    payload = policy["payload"]
    verification_expectations = tuple(
        str(item).strip()
        for item in scaffold_build.get("verification_expectations", [])
        if isinstance(item, str) and str(item).strip()
    )
    required_commands = tuple(policy["required_commands"])
    missing_required_commands = [command for command in required_commands if command not in verification_expectations]

    installer_archive_file = scaffold_build.get("installer_archive_file")
    rollback_artifact_present = isinstance(installer_archive_file, str) and Path(installer_archive_file).exists()

    sections: dict[str, dict[str, object]] = {}

    signing_required = bool(payload["signing"]["required"])
    signing_blocking_items: list[str] = []
    approved_certificate_evidence_present = bool(cutover_evidence["signing"]["approved_certificate_evidence_present"])
    if signing_required:
        if not stage_status.get("signature_verified", False):
            signing_blocking_items.append("signature_not_verified")
        elif bool(payload["signing"]["approved_certificate_required"]) and not approved_certificate_evidence_present:
            signing_blocking_items.append("approved_certificate_evidence_missing")
    sections["signing"] = {
        "required": signing_required,
        "ready": not signing_blocking_items,
        "blocking_items": signing_blocking_items,
        "signature_verified": bool(stage_status.get("signature_verified", False)),
        "approved_certificate_evidence_present": approved_certificate_evidence_present,
    }

    timestamp_required = bool(payload["timestamp"]["required"])
    timestamp_blocking_items: list[str] = []
    approved_timestamp_evidence_present = bool(cutover_evidence["timestamp"]["approved_timestamp_evidence_present"])
    if timestamp_required:
        if not stage_status.get("signature_verified", False):
            timestamp_blocking_items.append("signature_not_verified")
        elif bool(payload["timestamp"]["approved_service_required"]) and not approved_timestamp_evidence_present:
            timestamp_blocking_items.append("approved_timestamp_evidence_missing")
    sections["timestamp"] = {
        "required": timestamp_required,
        "ready": not timestamp_blocking_items,
        "blocking_items": timestamp_blocking_items,
        "signature_verified": bool(stage_status.get("signature_verified", False)),
        "approved_timestamp_evidence_present": approved_timestamp_evidence_present,
    }

    approvals_blocking_items: list[str] = []
    release_owner_approval_present = bool(cutover_evidence["approvals"]["release_owner_approval_present"])
    signing_operation_approval_present = bool(cutover_evidence["approvals"]["signing_operation_approval_present"])
    if bool(payload["approvals"]["release_owner_approval_required"]) and not release_owner_approval_present:
        approvals_blocking_items.append("release_owner_approval_missing")
    if bool(payload["approvals"]["signing_operation_approval_required"]) and not signing_operation_approval_present:
        approvals_blocking_items.append("signing_operation_approval_missing")
    sections["approvals"] = {
        "required": True,
        "ready": not approvals_blocking_items,
        "blocking_items": approvals_blocking_items,
        "release_owner_approval_present": release_owner_approval_present,
        "signing_operation_approval_present": signing_operation_approval_present,
    }

    rollback_blocking_items: list[str] = []
    rollback_validation_present = bool(cutover_evidence["rollback"]["rollback_validation_evidence_present"])
    if bool(payload["rollback"]["bundled_runtime_artifact_required"]) and not rollback_artifact_present:
        rollback_blocking_items.append("bundled_runtime_artifact_missing")
    if bool(payload["rollback"]["rollback_validation_required"]) and not rollback_validation_present:
        rollback_blocking_items.append("rollback_validation_evidence_missing")
    sections["rollback"] = {
        "required": True,
        "ready": not rollback_blocking_items,
        "blocking_items": rollback_blocking_items,
        "bundled_runtime_artifact_present": rollback_artifact_present,
        "rollback_validation_evidence_present": rollback_validation_present,
    }

    clean_machine_required = bool(payload["clean_machine_validation"]["required"])
    verified_commands = tuple(str(item).strip() for item in cutover_evidence["clean_machine_validation"]["verified_commands"])
    clean_machine_validation_present = bool(cutover_evidence["clean_machine_validation"]["validation_evidence_present"])
    clean_machine_blocking_items: list[str] = []
    if clean_machine_required and missing_required_commands:
        clean_machine_blocking_items.append("required_commands_not_declared")
    missing_verified_commands = [command for command in required_commands if command not in verified_commands]
    if clean_machine_required and missing_verified_commands:
        clean_machine_blocking_items.append("required_commands_not_verified")
    if clean_machine_required and not clean_machine_validation_present:
        clean_machine_blocking_items.append("clean_machine_validation_evidence_missing")
    sections["clean_machine_validation"] = {
        "required": clean_machine_required,
        "ready": not clean_machine_blocking_items,
        "blocking_items": clean_machine_blocking_items,
        "required_commands": list(required_commands),
        "missing_required_commands": missing_required_commands,
        "missing_verified_commands": missing_verified_commands,
        "verification_expectations": list(verification_expectations),
        "validation_evidence_present": clean_machine_validation_present,
        "verified_commands": list(verified_commands),
    }

    blocking_items = [
        f"{section}.{blocking_item}"
        for section, section_status in sections.items()
        for blocking_item in section_status["blocking_items"]
    ]
    ready = all(bool(section_status["ready"]) for section_status in sections.values())

    next_action = None
    if not ready:
        if sections["signing"]["blocking_items"]:
            next_action = (
                "complete_msi_signing"
                if "signature_not_verified" in sections["signing"]["blocking_items"]
                else "record_signing_certificate_evidence"
            )
        elif sections["timestamp"]["blocking_items"]:
            next_action = "record_timestamp_evidence"
        elif sections["approvals"]["blocking_items"]:
            next_action = "record_release_approvals"
        elif sections["rollback"]["blocking_items"]:
            next_action = "record_rollback_evidence"
        elif sections["clean_machine_validation"]["blocking_items"]:
            next_action = "record_clean_machine_validation"

    return {
        "ready": ready,
        "blocking_items": blocking_items,
        "next_action": next_action,
        "sections": sections,
    }


def _build_cutover_policy(
    *,
    policy: dict[str, object],
    toolchain: dict[str, object],
    stage_status: dict[str, bool],
    policy_status: dict[str, object],
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
        "policy_file": policy["policy_name"],
        "policy_id": policy["policy_id"],
        "policy_format_version": policy["format_version"],
        "policy_checksum": policy["policy_checksum"],
        "current_canonical_release_lane": policy["current_canonical_release_lane"],
        "native_installer_lane_phase": _native_installer_lane_phase(stage_status),
        "probe_ready": probe_ready,
        "cutover_ready": bool(policy_status["ready"]),
        "blocking_items": blocking_items,
        "next_action": next_action,
        "manual_cutover_requirements": list(policy["manual_cutover_requirements"]),
        "policy_ready": bool(policy_status["ready"]),
        "policy_blocking_items": list(policy_status["blocking_items"]),
    }


def execute_native_installer_lane(
    *,
    workspace: Path | None = None,
    name: str = "native-lane",
    cutover_evidence_file: Path | None = None,
    require_toolchain: bool = False,
    require_signed: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-native-installer-lane-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()
    started_at = time.perf_counter()
    try:
        policy = load_native_installer_cutover_policy()
    except ValueError as exc:
        raise VerificationError(f"Native installer cutover policy is invalid: {exc}") from exc
    try:
        cutover_evidence = load_native_installer_cutover_evidence(cutover_evidence_file)
    except ValueError as exc:
        raise VerificationError(f"Native installer cutover evidence is invalid: {exc}") from exc

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
    policy_status = _build_policy_status(
        policy=policy,
        stage_status=stage_status,
        scaffold_build=scaffold_build,
        cutover_evidence=cutover_evidence,
    )
    cutover_policy = _build_cutover_policy(
        policy=policy,
        toolchain=toolchain,
        stage_status=stage_status,
        policy_status=policy_status,
    )

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "stage_status": stage_status,
        "cutover_evidence": cutover_evidence,
        "policy_status": policy_status,
        "cutover_policy": cutover_policy,
        "toolchain": toolchain,
        "scaffold_build": scaffold_build,
        "scaffold_verify": scaffold_verify,
        "msi_build": msi_build,
        "signature_verify": signature_verify,
        "ready_for_release": ready_for_release,
        "policy_ready": bool(policy_status["ready"]),
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
            cutover_evidence_file=args.cutover_evidence_file,
            require_toolchain=args.require_toolchain,
            require_signed=args.require_signed,
        )
        if args.receipt_file is not None:
            _write_json_file(args.receipt_file.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root is not None and not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

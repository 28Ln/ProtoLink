from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from protolink.core.native_installer_cutover_policy import load_native_installer_cutover_policy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_DIR = ROOT / "dist" / "deliverables"
DELIVERABLES_MANIFEST_FILE = "deliverables-manifest.json"
DELIVERABLES_MANIFEST_FORMAT_VERSION = "protolink-deliverables-v1"


class DeliveryVerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 ProtoLink dist/deliverables 的归档与证据文件。")
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR, help="deliverables 目录。默认 dist/deliverables。")
    parser.add_argument("--require-native-ready", action="store_true", help="若 native installer lane 不是 ready_for_release 则返回非零退出码。")
    return parser


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _run_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    import subprocess

    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise DeliveryVerificationError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DeliveryVerificationError(
            "Command did not return JSON:\n"
            f"{' '.join(command)}\n\nstdout:\n{completed.stdout}"
        ) from exc
    if not isinstance(payload, dict):
        raise DeliveryVerificationError(f"Command did not return a JSON object: {' '.join(command)}")
    return payload


def _read_json_file(path: Path, *, label: str) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        raise DeliveryVerificationError(f"{label} was not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeliveryVerificationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise DeliveryVerificationError(f"{label} must be a JSON object: {path}")
    return payload


def _require_string(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise DeliveryVerificationError(f"{label} is missing required string field '{key}'.")
    return value


def _require_dict(payload: dict[str, object], key: str, *, label: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise DeliveryVerificationError(f"{label} is missing required object field '{key}'.")
    return value


def _require_list(payload: dict[str, object], key: str, *, label: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise DeliveryVerificationError(f"{label} is missing required list field '{key}'.")
    return list(value)


def _safe_top_level_path(target_dir: Path, entry_name: str, *, label: str) -> Path:
    candidate = target_dir / entry_name
    resolved = candidate.resolve()
    if Path(entry_name).name != entry_name:
        raise DeliveryVerificationError(f"{label} must be a top-level filename, got '{entry_name}'.")
    if not resolved.is_relative_to(target_dir):
        raise DeliveryVerificationError(f"{label} escaped the deliverables directory: {resolved}")
    return resolved


def execute_verify_release_deliverables(
    *,
    target_dir: Path = DEFAULT_TARGET_DIR,
    require_native_ready: bool = False,
) -> dict[str, object]:
    target_dir = target_dir.resolve()
    manifest_file = target_dir / DELIVERABLES_MANIFEST_FILE
    manifest = _read_json_file(manifest_file, label="Deliverables manifest")

    format_version = _require_string(manifest, "format_version", label="Deliverables manifest")
    if format_version != DELIVERABLES_MANIFEST_FORMAT_VERSION:
        raise DeliveryVerificationError(
            f"Deliverables manifest format_version must be '{DELIVERABLES_MANIFEST_FORMAT_VERSION}', got '{format_version}'."
        )

    copied_artifacts = _require_dict(manifest, "copied_artifacts", label="Deliverables manifest")
    checksums = _require_dict(manifest, "checksums", label="Deliverables manifest")
    verification = _require_dict(manifest, "verification", label="Deliverables manifest")
    receipt_name = _require_string(manifest, "native_installer_lane_receipt_file", label="Deliverables manifest")
    policy_name = _require_string(manifest, "native_installer_cutover_policy_file", label="Deliverables manifest")
    policy_metadata = _require_dict(manifest, "native_installer_cutover_policy", label="Deliverables manifest")
    native_installer_lane_summary = _require_dict(
        manifest, "native_installer_lane_summary", label="Deliverables manifest"
    )
    included_entries = _require_list(manifest, "included_entries", label="Deliverables manifest")
    included_entry_names = {str(item) for item in included_entries}

    if DELIVERABLES_MANIFEST_FILE not in included_entry_names:
        raise DeliveryVerificationError("Deliverables manifest included_entries is missing 'deliverables-manifest.json'.")

    checked_artifacts: dict[str, str] = {}
    for key, value in copied_artifacts.items():
        if not isinstance(value, str) or not value:
            raise DeliveryVerificationError(f"Deliverables manifest copied_artifacts['{key}'] must be a filename.")
        artifact_path = _safe_top_level_path(target_dir, value, label=f"copied_artifacts['{key}']")
        if not artifact_path.exists() or not artifact_path.is_file():
            raise DeliveryVerificationError(f"Deliverables artifact '{artifact_path.name}' was not found.")
        expected_checksum = checksums.get(value)
        if not isinstance(expected_checksum, str) or not expected_checksum:
            raise DeliveryVerificationError(f"Deliverables manifest is missing checksum for '{value}'.")
        actual_checksum = _sha256_file(artifact_path)
        if actual_checksum != expected_checksum:
            raise DeliveryVerificationError(
                f"Deliverables artifact '{artifact_path.name}' checksum mismatch.\nexpected: {expected_checksum}\nactual:   {actual_checksum}"
            )
        if artifact_path.name not in included_entry_names:
            raise DeliveryVerificationError(
                f"Deliverables manifest included_entries is missing '{artifact_path.name}'."
            )
        checked_artifacts[key] = str(artifact_path)

    for label in ("portable", "distribution", "installer"):
        verification_payload = verification.get(label)
        if not isinstance(verification_payload, dict):
            raise DeliveryVerificationError(f"Deliverables manifest verification is missing '{label}'.")
        if verification_payload.get("checksum_matches") is not True:
            raise DeliveryVerificationError(f"Deliverables manifest verification['{label}'].checksum_matches must be true.")

    package_verification = {
        "portable": _run_json(_uv("protolink", "--verify-portable-package", str(target_dir / _require_string(copied_artifacts, "portable_archive", label="Deliverables manifest copied_artifacts")))),
        "distribution": _run_json(_uv("protolink", "--verify-distribution-package", str(target_dir / _require_string(copied_artifacts, "distribution_archive", label="Deliverables manifest copied_artifacts")))),
        "installer": _run_json(_uv("protolink", "--verify-installer-package", str(target_dir / _require_string(copied_artifacts, "installer_archive", label="Deliverables manifest copied_artifacts")))),
    }
    for label, payload in package_verification.items():
        if payload.get("checksum_matches") is not True:
            raise DeliveryVerificationError(f"Package verifier reported checksum mismatch for '{label}'.")

    receipt_file = _safe_top_level_path(target_dir, receipt_name, label="native_installer_lane_receipt_file")
    if not receipt_file.exists() or not receipt_file.is_file():
        raise DeliveryVerificationError(f"Native installer lane receipt was not found: {receipt_file}")
    receipt_checksum = checksums.get(receipt_name)
    if not isinstance(receipt_checksum, str) or not receipt_checksum:
        raise DeliveryVerificationError(f"Deliverables manifest is missing checksum for '{receipt_name}'.")
    actual_receipt_checksum = _sha256_file(receipt_file)
    if actual_receipt_checksum != receipt_checksum:
        raise DeliveryVerificationError(
            f"Native installer lane receipt checksum mismatch.\nexpected: {receipt_checksum}\nactual:   {actual_receipt_checksum}"
        )
    if receipt_name not in included_entry_names:
        raise DeliveryVerificationError(f"Deliverables manifest included_entries is missing '{receipt_name}'.")
    policy_file = _safe_top_level_path(target_dir, policy_name, label="native_installer_cutover_policy_file")
    if not policy_file.exists() or not policy_file.is_file():
        raise DeliveryVerificationError(f"Native installer cutover policy file was not found: {policy_file}")
    policy_checksum = checksums.get(policy_name)
    if not isinstance(policy_checksum, str) or not policy_checksum:
        raise DeliveryVerificationError(f"Deliverables manifest is missing checksum for '{policy_name}'.")
    actual_policy_checksum = _sha256_file(policy_file)
    if actual_policy_checksum != policy_checksum:
        raise DeliveryVerificationError(
            f"Native installer cutover policy checksum mismatch.\nexpected: {policy_checksum}\nactual:   {actual_policy_checksum}"
        )
    if policy_name not in included_entry_names:
        raise DeliveryVerificationError(f"Deliverables manifest included_entries is missing '{policy_name}'.")
    try:
        archived_policy = load_native_installer_cutover_policy(policy_file)
    except ValueError as exc:
        raise DeliveryVerificationError(f"Archived native installer cutover policy is invalid: {exc}") from exc
    for manifest_key, policy_key in (
        ("policy_id", "policy_id"),
        ("policy_format_version", "format_version"),
        ("policy_checksum", "policy_checksum"),
    ):
        if policy_metadata.get(manifest_key) != archived_policy[policy_key]:
            raise DeliveryVerificationError(
                f"Deliverables manifest native installer cutover policy {manifest_key} does not match the archived policy."
            )

    receipt = _read_json_file(receipt_file, label="Native installer lane receipt")
    stage_status = _require_dict(receipt, "stage_status", label="Native installer lane receipt")
    cutover_policy = _require_dict(receipt, "cutover_policy", label="Native installer lane receipt")
    receipt_phase = _require_string(cutover_policy, "native_installer_lane_phase", label="Native installer lane receipt")
    receipt_blocking_items = cutover_policy.get("blocking_items")
    if not isinstance(receipt_blocking_items, list):
        raise DeliveryVerificationError("Native installer lane receipt cutover_policy.blocking_items must be a list.")

    summary_phase = _require_string(native_installer_lane_summary, "phase", label="Deliverables manifest native installer lane summary")
    if summary_phase != receipt_phase:
        raise DeliveryVerificationError(
            f"Deliverables manifest native installer lane phase mismatch.\nmanifest: {summary_phase}\nreceipt:  {receipt_phase}"
        )

    summary_blocking_items = native_installer_lane_summary.get("blocking_items")
    if not isinstance(summary_blocking_items, list):
        raise DeliveryVerificationError("Deliverables manifest native installer lane summary.blocking_items must be a list.")
    if summary_blocking_items != receipt_blocking_items:
        raise DeliveryVerificationError("Deliverables manifest native installer lane summary.blocking_items does not match the receipt.")

    for summary_key, receipt_key in (
        ("lifecycle_contract_ready", "lifecycle_contract_ready"),
        ("toolchain_ready", "toolchain_ready"),
    ):
        summary_value = native_installer_lane_summary.get(summary_key)
        receipt_value = stage_status.get(receipt_key)
        if not isinstance(summary_value, bool) or not isinstance(receipt_value, bool):
            raise DeliveryVerificationError(
                f"Deliverables manifest / native installer lane receipt must provide boolean '{summary_key}'."
            )
        if summary_value != receipt_value:
            raise DeliveryVerificationError(
                f"Deliverables manifest native installer lane summary.{summary_key} does not match the receipt."
            )

    summary_ready = native_installer_lane_summary.get("ready_for_release")
    receipt_ready = receipt.get("ready_for_release")
    if not isinstance(summary_ready, bool) or not isinstance(receipt_ready, bool):
        raise DeliveryVerificationError("Deliverables manifest and native installer lane receipt must provide boolean ready_for_release.")
    if summary_ready != receipt_ready:
        raise DeliveryVerificationError("Deliverables manifest native installer lane summary.ready_for_release does not match the receipt.")
    if require_native_ready and not receipt_ready:
        raise DeliveryVerificationError("Native installer lane is not ready_for_release for these deliverables.")
    for receipt_key, policy_key in (
        ("policy_id", "policy_id"),
        ("policy_format_version", "format_version"),
        ("policy_checksum", "policy_checksum"),
    ):
        if cutover_policy.get(receipt_key) != archived_policy[policy_key]:
            raise DeliveryVerificationError(
                f"Native installer lane receipt {receipt_key} does not match the archived cutover policy."
            )

    install_smoke = manifest.get("install_smoke")
    install_smoke_present = install_smoke is not None
    if install_smoke_present and not isinstance(install_smoke, dict):
        raise DeliveryVerificationError("Deliverables manifest install_smoke must be null or an object.")

    return {
        "ready": True,
        "blocking_items": [],
        "target_dir": str(target_dir),
        "manifest_file": str(manifest_file),
        "checked_artifacts": checked_artifacts,
        "receipt_file": str(receipt_file),
        "policy_file": str(policy_file),
        "native_installer_lane_phase": receipt_phase,
        "install_smoke_present": install_smoke_present,
        "checks": {
            "artifact_checksums": {key: {"file": value, "ok": True} for key, value in checked_artifacts.items()},
            "package_verification": package_verification,
            "native_installer_lane": {
                "phase": receipt_phase,
                "blocking_items": receipt_blocking_items,
                "lifecycle_contract_ready": stage_status.get("lifecycle_contract_ready"),
                "toolchain_ready": stage_status.get("toolchain_ready"),
                "ready_for_release": receipt_ready,
            },
        },
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute_verify_release_deliverables(
            target_dir=args.target_dir,
            require_native_ready=args.require_native_ready,
        )
        exit_code = 0
    except DeliveryVerificationError as exc:
        result = {
            "ready": False,
            "blocking_items": [str(exc)],
            "target_dir": str(args.target_dir.resolve()),
        }
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

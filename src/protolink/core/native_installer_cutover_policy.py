from __future__ import annotations

import hashlib
import json
from pathlib import Path


NATIVE_INSTALLER_CUTOVER_POLICY_FILE = "NATIVE_INSTALLER_CUTOVER_POLICY.json"
NATIVE_INSTALLER_CUTOVER_POLICY_FORMAT_VERSION = "protolink-native-installer-cutover-policy-v1"
NATIVE_INSTALLER_CUTOVER_POLICY_ID = "native-installer-cutover-policy"
NATIVE_INSTALLER_CUTOVER_MANUAL_REQUIREMENTS = (
    "approved_code_signing_certificate",
    "approved_rfc3161_timestamp_service",
    "documented_release_approval",
    "bundled_runtime_rollback_artifact_retained",
)


def default_native_installer_cutover_policy_file(*, repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / "docs" / NATIVE_INSTALLER_CUTOVER_POLICY_FILE


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_nonempty_string(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is missing required string field '{key}'.")
    return value.strip()


def _require_bool(payload: dict[str, object], key: str, *, label: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label} is missing required boolean field '{key}'.")
    return value


def _require_object(payload: dict[str, object], key: str, *, label: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{label} is missing required object field '{key}'.")
    return value


def _require_string_list(payload: dict[str, object], key: str, *, label: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} is missing required list field '{key}'.")
    normalized = tuple(str(item).strip() for item in value if isinstance(item, str) and str(item).strip())
    if len(normalized) != len(value):
        raise ValueError(f"{label} has invalid string entries in '{key}'.")
    return normalized


def load_native_installer_cutover_policy(
    policy_file: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    file = (policy_file or default_native_installer_cutover_policy_file(repo_root=repo_root)).resolve()
    if not file.exists() or not file.is_file():
        raise ValueError(f"Native installer cutover policy file was not found: {file}")

    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Native installer cutover policy file is not valid UTF-8: {file}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Native installer cutover policy file is not valid JSON: {file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Native installer cutover policy must be a JSON object.")

    policy_id = _require_nonempty_string(payload, "policy_id", label="Native installer cutover policy")
    if policy_id != NATIVE_INSTALLER_CUTOVER_POLICY_ID:
        raise ValueError(
            f"Native installer cutover policy policy_id must be '{NATIVE_INSTALLER_CUTOVER_POLICY_ID}', got '{policy_id}'."
        )
    format_version = _require_nonempty_string(payload, "format_version", label="Native installer cutover policy")
    if format_version != NATIVE_INSTALLER_CUTOVER_POLICY_FORMAT_VERSION:
        raise ValueError(
            f"Native installer cutover policy format_version must be '{NATIVE_INSTALLER_CUTOVER_POLICY_FORMAT_VERSION}', got '{format_version}'."
        )

    current_canonical_release_lane = _require_nonempty_string(
        payload, "current_canonical_release_lane", label="Native installer cutover policy"
    )
    manual_cutover_requirements = _require_string_list(
        payload, "manual_cutover_requirements", label="Native installer cutover policy"
    )
    if manual_cutover_requirements != NATIVE_INSTALLER_CUTOVER_MANUAL_REQUIREMENTS:
        raise ValueError(
            "Native installer cutover policy manual_cutover_requirements does not match the canonical requirement list."
        )

    signing = _require_object(payload, "signing", label="Native installer cutover policy")
    if _require_bool(signing, "required", label="Native installer cutover policy signing") is not True:
        raise ValueError("Native installer cutover policy signing.required must be true.")
    if _require_nonempty_string(signing, "method", label="Native installer cutover policy signing") != "windows-authenticode":
        raise ValueError("Native installer cutover policy signing.method must be 'windows-authenticode'.")
    if _require_bool(signing, "approved_certificate_required", label="Native installer cutover policy signing") is not True:
        raise ValueError("Native installer cutover policy signing.approved_certificate_required must be true.")

    timestamp = _require_object(payload, "timestamp", label="Native installer cutover policy")
    if _require_bool(timestamp, "required", label="Native installer cutover policy timestamp") is not True:
        raise ValueError("Native installer cutover policy timestamp.required must be true.")
    if _require_nonempty_string(timestamp, "service_type", label="Native installer cutover policy timestamp") != "rfc3161":
        raise ValueError("Native installer cutover policy timestamp.service_type must be 'rfc3161'.")
    if _require_bool(timestamp, "approved_service_required", label="Native installer cutover policy timestamp") is not True:
        raise ValueError("Native installer cutover policy timestamp.approved_service_required must be true.")

    approvals = _require_object(payload, "approvals", label="Native installer cutover policy")
    if _require_bool(approvals, "release_owner_approval_required", label="Native installer cutover policy approvals") is not True:
        raise ValueError("Native installer cutover policy approvals.release_owner_approval_required must be true.")
    if _require_bool(approvals, "signing_operation_approval_required", label="Native installer cutover policy approvals") is not True:
        raise ValueError("Native installer cutover policy approvals.signing_operation_approval_required must be true.")

    rollback = _require_object(payload, "rollback", label="Native installer cutover policy")
    if _require_bool(rollback, "bundled_runtime_artifact_required", label="Native installer cutover policy rollback") is not True:
        raise ValueError("Native installer cutover policy rollback.bundled_runtime_artifact_required must be true.")
    if _require_bool(rollback, "rollback_validation_required", label="Native installer cutover policy rollback") is not True:
        raise ValueError("Native installer cutover policy rollback.rollback_validation_required must be true.")

    clean_machine_validation = _require_object(
        payload, "clean_machine_validation", label="Native installer cutover policy"
    )
    if _require_bool(clean_machine_validation, "required", label="Native installer cutover policy clean_machine_validation") is not True:
        raise ValueError("Native installer cutover policy clean_machine_validation.required must be true.")
    required_commands = _require_string_list(
        clean_machine_validation,
        "required_commands",
        label="Native installer cutover policy clean_machine_validation",
    )

    return {
        "policy_file": str(file),
        "policy_name": file.name,
        "policy_id": policy_id,
        "format_version": format_version,
        "policy_checksum": _sha256_file(file),
        "current_canonical_release_lane": current_canonical_release_lane,
        "manual_cutover_requirements": manual_cutover_requirements,
        "required_commands": required_commands,
        "payload": payload,
    }

from __future__ import annotations

import hashlib
import json
from pathlib import Path


NATIVE_INSTALLER_CUTOVER_EVIDENCE_FILE = "native-installer-cutover-evidence.json"
NATIVE_INSTALLER_CUTOVER_EVIDENCE_FORMAT_VERSION = "protolink-native-installer-cutover-evidence-v1"
NATIVE_INSTALLER_CUTOVER_EVIDENCE_ID = "native-installer-cutover-evidence"


def default_native_installer_cutover_evidence_file(*, repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / "dist" / NATIVE_INSTALLER_CUTOVER_EVIDENCE_FILE


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional evidence reference fields must be strings when present.")
    normalized = value.strip()
    return normalized or None


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
    if not isinstance(value, list):
        raise ValueError(f"{label} is missing required list field '{key}'.")
    normalized = tuple(str(item).strip() for item in value if isinstance(item, str) and str(item).strip())
    if len(normalized) != len(value):
        raise ValueError(f"{label} has invalid string entries in '{key}'.")
    return normalized


def default_native_installer_cutover_evidence() -> dict[str, object]:
    return {
        "source_present": False,
        "source_file": None,
        "source_name": None,
        "source_checksum": None,
        "evidence_id": NATIVE_INSTALLER_CUTOVER_EVIDENCE_ID,
        "format_version": NATIVE_INSTALLER_CUTOVER_EVIDENCE_FORMAT_VERSION,
        "signing": {
            "approved_certificate_evidence_present": False,
            "certificate_reference": None,
        },
        "timestamp": {
            "approved_timestamp_evidence_present": False,
            "timestamp_reference": None,
            "timestamp_service": None,
        },
        "approvals": {
            "release_owner_approval_present": False,
            "release_owner_reference": None,
            "signing_operation_approval_present": False,
            "signing_operation_reference": None,
        },
        "rollback": {
            "rollback_validation_evidence_present": False,
            "rollback_validation_reference": None,
        },
        "clean_machine_validation": {
            "validation_evidence_present": False,
            "verified_commands": [],
            "validation_reference": None,
        },
    }


def load_native_installer_cutover_evidence(
    evidence_file: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    file = (evidence_file or default_native_installer_cutover_evidence_file(repo_root=repo_root)).resolve()
    if not file.exists():
        if evidence_file is not None:
            raise ValueError(f"Native installer cutover evidence file was not found: {file}")
        return default_native_installer_cutover_evidence()
    if not file.is_file():
        raise ValueError(f"Native installer cutover evidence path is not a file: {file}")

    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Native installer cutover evidence file is not valid UTF-8: {file}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Native installer cutover evidence file is not valid JSON: {file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Native installer cutover evidence must be a JSON object.")

    evidence_id = str(payload.get("evidence_id", "")).strip()
    if evidence_id != NATIVE_INSTALLER_CUTOVER_EVIDENCE_ID:
        raise ValueError(
            f"Native installer cutover evidence evidence_id must be '{NATIVE_INSTALLER_CUTOVER_EVIDENCE_ID}', got '{evidence_id}'."
        )
    format_version = str(payload.get("format_version", "")).strip()
    if format_version != NATIVE_INSTALLER_CUTOVER_EVIDENCE_FORMAT_VERSION:
        raise ValueError(
            f"Native installer cutover evidence format_version must be '{NATIVE_INSTALLER_CUTOVER_EVIDENCE_FORMAT_VERSION}', got '{format_version}'."
        )

    signing = _require_object(payload, "signing", label="Native installer cutover evidence")
    timestamp = _require_object(payload, "timestamp", label="Native installer cutover evidence")
    approvals = _require_object(payload, "approvals", label="Native installer cutover evidence")
    rollback = _require_object(payload, "rollback", label="Native installer cutover evidence")
    clean_machine_validation = _require_object(
        payload, "clean_machine_validation", label="Native installer cutover evidence"
    )

    normalized = default_native_installer_cutover_evidence()
    normalized.update(
        {
            "source_present": True,
            "source_file": str(file),
            "source_name": file.name,
            "source_checksum": _sha256_file(file),
            "signing": {
                "approved_certificate_evidence_present": _require_bool(
                    signing, "approved_certificate_evidence_present", label="Native installer cutover evidence signing"
                ),
                "certificate_reference": _normalize_optional_string(signing.get("certificate_reference")),
            },
            "timestamp": {
                "approved_timestamp_evidence_present": _require_bool(
                    timestamp, "approved_timestamp_evidence_present", label="Native installer cutover evidence timestamp"
                ),
                "timestamp_reference": _normalize_optional_string(timestamp.get("timestamp_reference")),
                "timestamp_service": _normalize_optional_string(timestamp.get("timestamp_service")),
            },
            "approvals": {
                "release_owner_approval_present": _require_bool(
                    approvals, "release_owner_approval_present", label="Native installer cutover evidence approvals"
                ),
                "release_owner_reference": _normalize_optional_string(approvals.get("release_owner_reference")),
                "signing_operation_approval_present": _require_bool(
                    approvals, "signing_operation_approval_present", label="Native installer cutover evidence approvals"
                ),
                "signing_operation_reference": _normalize_optional_string(approvals.get("signing_operation_reference")),
            },
            "rollback": {
                "rollback_validation_evidence_present": _require_bool(
                    rollback, "rollback_validation_evidence_present", label="Native installer cutover evidence rollback"
                ),
                "rollback_validation_reference": _normalize_optional_string(rollback.get("rollback_validation_reference")),
            },
            "clean_machine_validation": {
                "validation_evidence_present": _require_bool(
                    clean_machine_validation,
                    "validation_evidence_present",
                    label="Native installer cutover evidence clean_machine_validation",
                ),
                "verified_commands": list(
                    _require_string_list(
                        clean_machine_validation,
                        "verified_commands",
                        label="Native installer cutover evidence clean_machine_validation",
                    )
                ),
                "validation_reference": _normalize_optional_string(clean_machine_validation.get("validation_reference")),
            },
        }
    )
    return normalized

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from protolink.core.native_installer_cutover_evidence import (
    NATIVE_INSTALLER_CUTOVER_EVIDENCE_FILE,
    default_native_installer_cutover_evidence,
)
from protolink.core.native_installer_cutover_policy import (
    default_native_installer_cutover_policy_file,
    load_native_installer_cutover_policy,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_DIR = ROOT / "dist" / "deliverables"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
DELIVERABLES_MANIFEST_FILE = "deliverables-manifest.json"
DELIVERABLES_MANIFEST_FORMAT_VERSION = "protolink-deliverables-v1"
NATIVE_INSTALLER_LANE_RECEIPT_FILE = "native-installer-lane-receipt.json"


class DeliveryBuildError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建 ProtoLink 可交付归档并完成基础校验。")
    parser.add_argument("--name", default="release-0.2.5", help="构建名后缀。默认 release-0.2.5。")
    parser.add_argument("--workspace", type=Path, help="可选，指定构建 workspace。默认创建临时 workspace。")
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR, help="产物输出目录。默认 dist/deliverables。")
    parser.add_argument("--cutover-evidence-file", type=Path, help="可选，提供 native installer cutover evidence JSON。")
    parser.add_argument("--skip-install-smoke", action="store_true", help="跳过安装链路自检。")
    parser.add_argument("--keep-workspace", action="store_true", help="保留自动创建的临时 workspace。")
    return parser


def _run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def _run_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    completed = _run(command, cwd=cwd)
    if completed.returncode != 0:
        raise DeliveryBuildError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DeliveryBuildError(
            "Command did not return JSON:\n"
            f"{' '.join(command)}\n\nstdout:\n{completed.stdout}"
        ) from exc


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if match is None:
        raise DeliveryBuildError("Could not determine project version from pyproject.toml.")
    return match.group(1)


def _copy_artifact(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_install_smoke(installer_archive: Path, *, target_dir: Path) -> dict[str, object]:
    staging_dir = target_dir / "_staging"
    install_dir = target_dir / "_installed"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    if install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)

    install_payload = _run_json(
        _uv("protolink", "--install-installer-package", str(installer_archive), str(staging_dir), str(install_dir))
    )
    launch_script = install_dir / "Launch-ProtoLink.ps1"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & '{launch_script}' --headless-summary",
    ]
    completed = _run(command, cwd=ROOT)
    if completed.returncode != 0:
        raise DeliveryBuildError(
            "Installed launch smoke failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    return {
        "install_payload": install_payload,
        "launch_script": str(launch_script),
        "headless_summary": completed.stdout.strip().splitlines(),
    }


def _write_json_file(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _run_native_installer_lane_receipt(
    *,
    workspace: Path,
    name: str,
    receipt_file: Path,
    cutover_evidence_file: Path | None = None,
) -> dict[str, object]:
    script_file = ROOT / "scripts" / "verify_native_installer_lane.py"
    command = [
        sys.executable,
        str(script_file),
        "--workspace",
        str(workspace),
        "--name",
        f"{name}-receipt",
        "--receipt-file",
        str(receipt_file),
    ]
    if cutover_evidence_file is not None:
        command.extend(["--cutover-evidence-file", str(cutover_evidence_file)])
    return _run_json(command)


def _build_deliverables_manifest(
    *,
    version: str,
    name: str,
    workspace: Path,
    target_dir: Path,
    copied_artifacts: dict[str, str],
    verification: dict[str, object],
    install_smoke: dict[str, object] | None,
    native_installer_lane_receipt_file: Path,
    native_installer_lane_receipt: dict[str, object],
    native_installer_cutover_policy_file: Path,
    native_installer_cutover_policy: dict[str, object],
    native_installer_cutover_evidence_file: Path,
    native_installer_cutover_evidence: dict[str, object],
) -> dict[str, object]:
    artifact_paths = {key: Path(value) for key, value in copied_artifacts.items()}
    checksums = {
        **{path.name: _sha256_file(path) for path in artifact_paths.values()},
        native_installer_lane_receipt_file.name: _sha256_file(native_installer_lane_receipt_file),
        native_installer_cutover_policy_file.name: _sha256_file(native_installer_cutover_policy_file),
        native_installer_cutover_evidence_file.name: _sha256_file(native_installer_cutover_evidence_file),
    }
    included_entries = sorted(
        [
            *(path.name for path in artifact_paths.values()),
            native_installer_lane_receipt_file.name,
            native_installer_cutover_policy_file.name,
            native_installer_cutover_evidence_file.name,
            DELIVERABLES_MANIFEST_FILE,
        ]
    )
    lane_phase = None
    blocking_items: list[object] = []
    cutover_policy = native_installer_lane_receipt.get("cutover_policy", {})
    policy_status = native_installer_lane_receipt.get("policy_status", {})
    if isinstance(cutover_policy, dict):
        lane_phase = cutover_policy.get("native_installer_lane_phase")
        raw_blocking_items = cutover_policy.get("blocking_items", [])
        if isinstance(raw_blocking_items, list):
            blocking_items = list(raw_blocking_items)

    return {
        "format_version": DELIVERABLES_MANIFEST_FORMAT_VERSION,
        "version": version,
        "build_name": name,
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "copied_artifacts": {key: Path(value).name for key, value in copied_artifacts.items()},
        "checksums": checksums,
        "verification": verification,
        "install_smoke": install_smoke,
        "native_installer_lane_receipt_file": native_installer_lane_receipt_file.name,
        "native_installer_cutover_policy_file": native_installer_cutover_policy_file.name,
        "native_installer_cutover_policy": {
            "policy_id": native_installer_cutover_policy["policy_id"],
            "policy_format_version": native_installer_cutover_policy["format_version"],
            "policy_checksum": native_installer_cutover_policy["policy_checksum"],
        },
        "native_installer_cutover_evidence_file": native_installer_cutover_evidence_file.name,
        "native_installer_cutover_evidence": {
            "source_present": native_installer_cutover_evidence["source_present"],
            "source_name": native_installer_cutover_evidence["source_name"],
            "source_checksum": native_installer_cutover_evidence["source_checksum"],
            "evidence_id": native_installer_cutover_evidence["evidence_id"],
            "format_version": native_installer_cutover_evidence["format_version"],
        },
        "native_installer_lane_summary": {
            "phase": lane_phase,
            "blocking_items": blocking_items,
            "lifecycle_contract_ready": native_installer_lane_receipt.get("stage_status", {}).get("lifecycle_contract_ready")
            if isinstance(native_installer_lane_receipt.get("stage_status", {}), dict)
            else None,
            "toolchain_ready": native_installer_lane_receipt.get("stage_status", {}).get("toolchain_ready")
            if isinstance(native_installer_lane_receipt.get("stage_status", {}), dict)
            else None,
            "ready_for_release": native_installer_lane_receipt.get("ready_for_release"),
            "policy_ready": policy_status.get("ready") if isinstance(policy_status, dict) else None,
        },
        "native_installer_policy_status": policy_status,
        "included_entries": included_entries,
        "target_dir": str(target_dir),
    }


def execute_release_deliverables(
    *,
    name: str,
    workspace: Path | None = None,
    target_dir: Path = DEFAULT_TARGET_DIR,
    cutover_evidence_file: Path | None = None,
    skip_install_smoke: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-release-deliverables-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()
    target_dir = target_dir.resolve()
    version = _project_version()

    build_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--build-installer-package", name))

    release_archive = target_dir / f"protolink-{version}-release-bundle.zip"
    portable_archive = target_dir / f"protolink-{version}-portable-package.zip"
    distribution_archive = target_dir / f"protolink-{version}-distribution-package.zip"
    installer_archive = target_dir / f"protolink-{version}-installer-package.zip"

    copied_artifacts = {
        "release_archive": _copy_artifact(Path(str(build_payload["release_archive_file"])), release_archive),
        "portable_archive": _copy_artifact(Path(str(build_payload["portable_archive_file"])), portable_archive),
        "distribution_archive": _copy_artifact(Path(str(build_payload["distribution_archive_file"])), distribution_archive),
        "installer_archive": _copy_artifact(Path(str(build_payload["installer_archive_file"])), installer_archive),
    }

    verification = {
        "portable": _run_json(_uv("protolink", "--verify-portable-package", str(portable_archive))),
        "distribution": _run_json(_uv("protolink", "--verify-distribution-package", str(distribution_archive))),
        "installer": _run_json(_uv("protolink", "--verify-installer-package", str(installer_archive))),
    }

    install_smoke = None
    if not skip_install_smoke:
        install_smoke = _run_install_smoke(installer_archive, target_dir=target_dir)

    native_installer_lane_receipt_file = target_dir / NATIVE_INSTALLER_LANE_RECEIPT_FILE
    native_installer_lane_receipt = _run_native_installer_lane_receipt(
        workspace=workspace,
        name=name,
        receipt_file=native_installer_lane_receipt_file,
        cutover_evidence_file=cutover_evidence_file,
    )
    try:
        native_installer_cutover_policy = load_native_installer_cutover_policy()
    except ValueError as exc:
        raise DeliveryBuildError(f"Native installer cutover policy is invalid: {exc}") from exc
    native_installer_cutover_policy_file = target_dir / default_native_installer_cutover_policy_file().name
    _copy_artifact(Path(str(native_installer_cutover_policy["policy_file"])), native_installer_cutover_policy_file)
    native_installer_cutover_evidence = native_installer_lane_receipt.get("cutover_evidence")
    if not isinstance(native_installer_cutover_evidence, dict):
        native_installer_cutover_evidence = default_native_installer_cutover_evidence()
    native_installer_cutover_evidence_file = target_dir / NATIVE_INSTALLER_CUTOVER_EVIDENCE_FILE
    _write_json_file(native_installer_cutover_evidence_file, native_installer_cutover_evidence)
    receipt_cutover_policy = native_installer_lane_receipt.get("cutover_policy", {})
    if not isinstance(receipt_cutover_policy, dict):
        raise DeliveryBuildError("Native installer lane receipt is missing cutover_policy.")
    for receipt_key, policy_key in (
        ("policy_id", "policy_id"),
        ("policy_format_version", "format_version"),
        ("policy_checksum", "policy_checksum"),
    ):
        if receipt_cutover_policy.get(receipt_key) != native_installer_cutover_policy[policy_key]:
            raise DeliveryBuildError(
                f"Native installer lane receipt {receipt_key} does not match the current cutover policy."
            )
    deliverables_manifest = _build_deliverables_manifest(
        version=version,
        name=name,
        workspace=workspace,
        target_dir=target_dir,
        copied_artifacts=copied_artifacts,
        verification=verification,
        install_smoke=install_smoke,
        native_installer_lane_receipt_file=native_installer_lane_receipt_file,
        native_installer_lane_receipt=native_installer_lane_receipt,
        native_installer_cutover_policy_file=native_installer_cutover_policy_file,
        native_installer_cutover_policy=native_installer_cutover_policy,
        native_installer_cutover_evidence_file=native_installer_cutover_evidence_file,
        native_installer_cutover_evidence=native_installer_cutover_evidence,
    )
    deliverables_manifest_file = target_dir / DELIVERABLES_MANIFEST_FILE
    _write_json_file(deliverables_manifest_file, deliverables_manifest)

    return {
        "version": version,
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "copied_artifacts": copied_artifacts,
        "verification": verification,
        "install_smoke": install_smoke,
        "native_installer_lane_receipt_file": str(native_installer_lane_receipt_file),
        "native_installer_lane_receipt": native_installer_lane_receipt,
        "native_installer_cutover_policy_file": str(native_installer_cutover_policy_file),
        "native_installer_cutover_policy": native_installer_cutover_policy,
        "native_installer_cutover_evidence_file": str(native_installer_cutover_evidence_file),
        "native_installer_cutover_evidence": native_installer_cutover_evidence,
        "deliverables_manifest_file": str(deliverables_manifest_file),
        "deliverables_manifest": deliverables_manifest,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    temp_root_for_cleanup: Path | None = None
    workspace = args.workspace
    if workspace is None and not args.keep_workspace:
        temp_root_for_cleanup = Path(tempfile.mkdtemp(prefix="protolink-release-deliverables-main-"))
        workspace = temp_root_for_cleanup / "workspace"
    try:
        result = execute_release_deliverables(
            name=args.name,
            workspace=workspace,
            target_dir=args.target_dir,
            cutover_evidence_file=args.cutover_evidence_file,
            skip_install_smoke=args.skip_install_smoke,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root_for_cleanup is not None and not args.keep_workspace:
            shutil.rmtree(temp_root_for_cleanup, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

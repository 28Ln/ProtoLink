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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify ProtoLink clean release-staging install-and-run flow.")
    parser.add_argument("--name", default="release-staging", help="Artifact name prefix.")
    parser.add_argument("--keep-artifacts", action="store_true", help="Keep temporary staging/install/workspace directories.")
    return parser


def _run_command(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="protolink-release-staging-"))
    workspace = temp_root / "workspace"
    staging_dir = temp_root / "installer-staging"
    install_dir = temp_root / "installer-install"

    try:
        generate_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--generate-smoke-artifacts"))
        build_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--build-installer-package", args.name))

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

        runtime_python = install_dir / "runtime" / "python.exe"
        site_packages = install_dir / "sp"
        if not runtime_python.exists():
            raise SystemExit(f"Bundled runtime executable was not installed: {runtime_python}")
        if not site_packages.exists():
            raise SystemExit(f"Bundled site-packages directory was not installed: {site_packages}")

        runtime_env = os.environ.copy()
        runtime_env["PYTHONPATH"] = str(site_packages)
        installed_summary = _run_command(
            [str(runtime_python), "-m", "protolink", "--headless-summary"],
            env=runtime_env,
        ).stdout
        if "ProtoLink" not in installed_summary:
            raise SystemExit("Installed bundled runtime did not produce the expected headless summary output.")

        uninstall_payload = _run_json(_uv("protolink", "--uninstall-portable-package", str(install_dir)))
        if not uninstall_payload.get("removed_receipt"):
            raise SystemExit("Portable uninstall did not remove the install receipt.")

        result = {
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
            "installed_headless_summary": installed_summary.strip(),
            "uninstall_portable_package": {
                "target_dir": uninstall_payload["target_dir"],
                "removed_receipt": uninstall_payload["removed_receipt"],
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

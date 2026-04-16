from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZipFile

from protolink.core.errors import ProtoLinkUserError
from protolink.core.import_export import build_artifact_timestamp, sanitize_artifact_name
from protolink.core.workspace import WorkspaceLayout


@dataclass(frozen=True, slots=True)
class PortablePackagePlan:
    package_dir: Path
    archive_file: Path
    package_name: str
    release_archive_file: Path


@dataclass(frozen=True, slots=True)
class PortableInstallResult:
    archive_file: Path
    target_dir: Path
    extracted_entries: tuple[str, ...]
    receipt_file: Path


@dataclass(frozen=True, slots=True)
class PortablePackageVerificationResult:
    archive_file: Path
    portable_manifest_file: str
    release_archive_file: str
    checksum_matches: bool
    install_scripts_present: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortableUninstallResult:
    target_dir: Path
    removed_entries: tuple[str, ...]
    removed_receipt: bool


@dataclass(frozen=True, slots=True)
class DistributionPackagePlan:
    package_dir: Path
    archive_file: Path
    manifest_file: Path
    package_name: str
    portable_archive_file: Path
    release_archive_file: Path


@dataclass(frozen=True, slots=True)
class DistributionInstallResult:
    archive_file: Path
    staging_dir: Path
    install_dir: Path
    distribution_manifest_file: Path
    portable_install: PortableInstallResult


@dataclass(frozen=True, slots=True)
class DistributionPackageVerificationResult:
    archive_file: Path
    distribution_manifest_file: str
    portable_archive_file: str
    release_archive_file: str
    checksum_matches: bool


@dataclass(frozen=True, slots=True)
class InstallerStagingPlan:
    package_dir: Path
    archive_file: Path
    manifest_file: Path
    package_name: str
    distribution_archive_file: Path


@dataclass(frozen=True, slots=True)
class InstallerStagingInstallResult:
    archive_file: Path
    staging_dir: Path
    install_dir: Path
    installer_manifest_file: Path
    distribution_install: DistributionInstallResult


@dataclass(frozen=True, slots=True)
class InstallerStagingVerificationResult:
    archive_file: Path
    installer_manifest_file: str
    distribution_archive_file: str
    checksum_matches: bool
    install_scripts_present: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InstallerPackagePlan:
    package_dir: Path
    archive_file: Path
    manifest_file: Path
    package_name: str
    installer_staging_archive_file: Path


@dataclass(frozen=True, slots=True)
class InstallerPackageInstallResult:
    archive_file: Path
    staging_dir: Path
    install_dir: Path
    installer_package_manifest_file: Path
    installer_staging_install: InstallerStagingInstallResult


@dataclass(frozen=True, slots=True)
class InstallerPackageVerificationResult:
    archive_file: Path
    installer_package_manifest_file: str
    installer_staging_archive_file: str
    checksum_matches: bool
    install_scripts_present: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeInstallerScaffoldPlan:
    package_dir: Path
    manifest_file: Path
    package_name: str
    installer_package_archive_file: Path
    wix_source_file: Path
    wix_include_file: Path
    installer_package_file: Path


@dataclass(frozen=True, slots=True)
class NativeInstallerScaffoldVerificationResult:
    scaffold_dir: Path
    manifest_file: Path
    wix_source_file: str
    wix_include_file: str
    installer_package_file: str
    checksum_matches: bool
    target_arch: str
    lifecycle_contract_ready: bool
    checked_contract_fields: tuple[str, ...]
    integrity_checked_entries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeInstallerToolStatus:
    tool_key: str
    display_name: str
    executable_name: str
    available: bool
    resolved_path: str | None
    detection_source: str
    probe_command: tuple[str, ...]
    probe_output: str | None
    error: str | None
    install_hint: str
    recommended_command: str


@dataclass(frozen=True, slots=True)
class NativeInstallerToolchainVerificationResult:
    target_platform: str
    current_platform: str
    ready: bool
    available_tools: tuple[str, ...]
    missing_tools: tuple[str, ...]
    tools: tuple[NativeInstallerToolStatus, ...]
    recommended_commands: dict[str, str]


@dataclass(frozen=True, slots=True)
class NativeInstallerBuildResult:
    scaffold_dir: Path
    output_file: Path
    wix_executable: str
    command: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class NativeInstallerSignatureVerificationResult:
    installer_file: Path
    signtool_executable: str
    command: tuple[str, ...]
    verified: bool
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class _NativeInstallerToolSpec:
    tool_key: str
    display_name: str
    env_var: str
    executable_names: tuple[str, ...]
    probe_command: tuple[str, ...]
    acceptable_exit_codes: tuple[int, ...]
    install_hint: str
    recommended_command_key: str


PORTABLE_MANIFEST_FILE = "portable-manifest.json"
PORTABLE_PACKAGE_FORMAT_VERSION = "protolink-portable-package-v1"
DISTRIBUTION_PACKAGE_FORMAT_VERSION = "protolink-distribution-package-v1"
INSTALLER_STAGING_FORMAT_VERSION = "protolink-installer-staging-v1"
INSTALLER_PACKAGE_FORMAT_VERSION = "protolink-installer-package-v1"
NATIVE_INSTALLER_SCAFFOLD_FORMAT_VERSION = "protolink-native-installer-scaffold-v1"
NATIVE_INSTALLER_MANIFEST_FILE = "manifest.json"
NATIVE_INSTALLER_WIX_SOURCE_FILE = "ProtoLink.wxs"
NATIVE_INSTALLER_WIX_INCLUDE_FILE = "ProtoLink.Generated.wxi"
NATIVE_INSTALLER_TARGET_ARCH = "x64"
NATIVE_INSTALLER_INSTALL_SCOPE = "perMachine"
NATIVE_INSTALLER_INSTALL_DIR_NAME = "ProtoLink"
NATIVE_INSTALLER_PAYLOAD_DIR_NAME = "payload"
NATIVE_INSTALLER_PRODUCT_CODE_POLICY = "wix-auto-generated-at-build"
NATIVE_INSTALLER_UPGRADE_STRATEGY = "major-upgrade"
NATIVE_INSTALLER_DOWNGRADE_ERROR_MESSAGE = "A newer version of ProtoLink is already installed."
BUNDLED_RUNTIME_DELIVERY_MODE = "bundled_python_runtime"
_NONESSENTIAL_RUNTIME_METADATA_FILES = frozenset({"RECORD", "INSTALLER", "REQUESTED", "direct_url.json"})
_NONESSENTIAL_RUNTIME_PACKAGES = frozenset({"pytest", "_pytest", "iniconfig", "pip", "wheel"})
_NONESSENTIAL_RUNTIME_PACKAGE_PREFIXES = tuple(f"{package}-" for package in sorted(_NONESSENTIAL_RUNTIME_PACKAGES))
_NATIVE_INSTALLER_TOOL_SPECS = (
    _NativeInstallerToolSpec(
        tool_key="wix",
        display_name="WiX Toolset v4 CLI",
        env_var="PROTOLINK_WIX",
        executable_names=("wix.exe", "wix"),
        probe_command=("--version",),
        acceptable_exit_codes=(0,),
        install_hint="Install WiX Toolset v4 and ensure `wix.exe` is on PATH or set PROTOLINK_WIX.",
        recommended_command_key="build_msi",
    ),
    _NativeInstallerToolSpec(
        tool_key="signtool",
        display_name="Windows SignTool",
        env_var="PROTOLINK_SIGNTOOL",
        executable_names=("signtool.exe", "signtool"),
        probe_command=("/?",),
        acceptable_exit_codes=(0, 1),
        install_hint="Install the Windows SDK signing tools and ensure `signtool.exe` is on PATH or set PROTOLINK_SIGNTOOL.",
        recommended_command_key="sign_msi",
    ),
)


def _build_bundled_runtime_requirements() -> dict[str, object]:
    return {
        "delivery_mode": BUNDLED_RUNTIME_DELIVERY_MODE,
        "python_requirement": None,
        "runtime_prerequisites": [],
    }


def _default_runtime_root() -> Path:
    override = os.environ.get("PROTOLINK_BUNDLED_RUNTIME_ROOT")
    return Path(override) if override else Path(sys.base_prefix)


def _default_runtime_site_packages() -> Path:
    override = os.environ.get("PROTOLINK_BUNDLED_SITE_PACKAGES")
    return Path(override) if override else Path(sysconfig.get_path("purelib"))


def _package_staging_dir(exports_dir: Path, package_kind: str, package_name: str) -> Path:
    package_digest = hashlib.sha256(package_name.encode("utf-8")).hexdigest()[:10]
    return exports_dir / ".pkg" / f"{package_kind}-{package_digest}"


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree(
    source: Path,
    destination: Path,
    *,
    ignore_site_packages: bool = False,
    ignore_python_path_links: bool = False,
    ignore_test_artifacts: bool = False,
    ignore_dev_packages: bool = False,
    ignore_runtime_metadata: bool = False,
) -> None:
    if not source.exists():
        return

    def _ignore(_directory: str, names: list[str]) -> set[str]:
        directory_name = Path(_directory).name
        ignored = {"__pycache__"}
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        if ignore_site_packages and "site-packages" in names:
            ignored.add("site-packages")
        if ignore_python_path_links:
            ignored.update(name for name in names if name.endswith((".pth", ".egg-link")))
        if ignore_test_artifacts:
            ignored.update(name for name in names if name in {"test", "tests"})
        if ignore_dev_packages:
            ignored.update(
                name
                for name in names
                if name in _NONESSENTIAL_RUNTIME_PACKAGES
                or (name.startswith(_NONESSENTIAL_RUNTIME_PACKAGE_PREFIXES) and name.endswith(".dist-info"))
            )
        if ignore_runtime_metadata and directory_name.endswith((".dist-info", ".egg-info")):
            ignored.update(name for name in names if name in _NONESSENTIAL_RUNTIME_METADATA_FILES)
        return ignored

    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=_ignore,
    )


def _materialize_bundled_runtime(
    package_dir: Path,
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
    site_packages_root: Path | None = None,
) -> list[str]:
    runtime_root = (runtime_root or _default_runtime_root()).resolve()
    site_packages_root = (site_packages_root or _default_runtime_site_packages()).resolve()
    if not runtime_root.exists():
        raise ProtoLinkUserError(
            f"Bundled runtime root '{runtime_root}' was not found.",
            action="build portable package",
            recovery="Ensure Python is installed in the current build environment and retry.",
        )
    if not site_packages_root.exists():
        raise ProtoLinkUserError(
            f"Bundled runtime site-packages directory '{site_packages_root}' was not found.",
            action="build portable package",
            recovery="Install runtime dependencies in the current build environment and retry.",
        )

    runtime_dest = package_dir / "runtime"
    copied: list[str] = []

    for file_name in ("python.exe", "pythonw.exe", "python3.dll", "python311.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        source = runtime_root / file_name
        if source.exists():
            _copy_file(source, runtime_dest / file_name)
            copied.append(str((runtime_dest / file_name).relative_to(package_dir)))

    for directory_name in ("DLLs", "Lib"):
        source = runtime_root / directory_name
        if source.exists():
            _copy_tree(
                source,
                runtime_dest / directory_name,
                ignore_site_packages=(directory_name == "Lib"),
                ignore_test_artifacts=(directory_name == "Lib"),
            )
            copied.append(str((runtime_dest / directory_name).relative_to(package_dir)))

    runtime_site_packages_dest = package_dir / "sp"
    _copy_tree(
        site_packages_root,
        runtime_site_packages_dest,
        ignore_python_path_links=True,
        ignore_test_artifacts=True,
        ignore_dev_packages=True,
        ignore_runtime_metadata=True,
    )
    copied.append(str(runtime_site_packages_dest.relative_to(package_dir)))

    app_source_root = repo_root / "src" / "protolink"
    if app_source_root.exists():
        _copy_tree(app_source_root, runtime_site_packages_dest / "protolink")
        copied.append(str((runtime_site_packages_dest / "protolink").relative_to(package_dir)))

    return copied


def build_portable_package_plan(
    repo_root: Path,
    workspace: WorkspaceLayout,
    name: str,
    release_archive_file: Path,
    *,
    packaged_at: datetime | None = None,
) -> PortablePackagePlan:
    packaged_at = packaged_at or datetime.now(UTC)
    package_name = f"{build_artifact_timestamp(packaged_at)}-portable-{sanitize_artifact_name(name)}"
    package_dir = _package_staging_dir(workspace.exports, "portable", package_name)
    archive_file = workspace.exports / f"{package_name}.zip"
    return PortablePackagePlan(
        package_dir=package_dir,
        archive_file=archive_file,
        package_name=package_name,
        release_archive_file=release_archive_file,
    )


def materialize_portable_package(
    plan: PortablePackagePlan,
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
    site_packages_root: Path | None = None,
) -> dict[str, object]:
    if not plan.release_archive_file.exists():
        raise ProtoLinkUserError(
            f"Release archive '{plan.release_archive_file}' was not found.",
            action="build portable package",
            recovery="Run release packaging first and retry.",
        )
    plan.package_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []

    def copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(plan.package_dir)))

    for relative in (
        Path("README.md"),
        Path("docs/SMOKE_CHECKLIST.md"),
        Path("docs/RELEASE_CHECKLIST.md"),
    ):
        source = repo_root / relative
        if source.exists():
            copy_file(source, plan.package_dir / relative)

    release_archive_destination = plan.package_dir / plan.release_archive_file.name
    copy_file(plan.release_archive_file, release_archive_destination)

    copied.extend(
        _materialize_bundled_runtime(
            plan.package_dir,
            repo_root,
            runtime_root=runtime_root,
            site_packages_root=site_packages_root,
        )
    )

    install_script = plan.package_dir / "INSTALL.ps1"
    install_script.write_text(
        "\n".join(
            (
                "$ErrorActionPreference = 'Stop'",
                '$runtime = Join-Path $PSScriptRoot "runtime\\python.exe"',
                'if (-not (Test-Path -LiteralPath $runtime)) { throw "Bundled runtime is missing." }',
                '$env:PYTHONPATH = Join-Path $PSScriptRoot "sp"',
                '$env:PROTOLINK_BASE_DIR = $PSScriptRoot',
                '& $runtime -m protolink --headless-summary',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("INSTALL.ps1")

    launch_ps1 = plan.package_dir / "Launch-ProtoLink.ps1"
    launch_ps1.write_text(
        "\n".join(
            (
                "param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ProtoLinkArgs = @())",
                "$runtimeName = if ($ProtoLinkArgs.Count -gt 0) { 'python.exe' } else { 'pythonw.exe' }",
                '$runtime = Join-Path $PSScriptRoot ("runtime\\" + $runtimeName)',
                'if (-not (Test-Path -LiteralPath $runtime)) { throw "Bundled runtime is missing." }',
                '$env:PYTHONPATH = Join-Path $PSScriptRoot "sp"',
                '$env:PROTOLINK_BASE_DIR = $PSScriptRoot',
                '& $runtime -m protolink @ProtoLinkArgs',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Launch-ProtoLink.ps1")

    launch_bat = plan.package_dir / "Launch-ProtoLink.bat"
    launch_bat.write_text(
        "\n".join(
            (
                "@echo off",
                "setlocal",
                'set "RUNTIME=%~dp0runtime\\pythonw.exe"',
                'if not "%~1"=="" set "RUNTIME=%~dp0runtime\\python.exe"',
                'set "PYTHONPATH=%~dp0sp"',
                'set "PROTOLINK_BASE_DIR=%~dp0"',
                'if not exist "%RUNTIME%" ( echo Bundled runtime is missing. & exit /b 1 )',
                '"%RUNTIME%" -m protolink %*',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Launch-ProtoLink.bat")

    manifest_file = plan.package_dir / PORTABLE_MANIFEST_FILE
    manifest = _build_portable_package_manifest(plan, copied, manifest_file)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    copied.append(PORTABLE_MANIFEST_FILE)

    if plan.archive_file.exists():
        plan.archive_file.unlink()
    with ZipFile(plan.archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for path in plan.package_dir.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                archive.write(path, arcname=path.relative_to(plan.package_dir))

    return manifest


def install_portable_package(archive_file: Path, target_dir: Path) -> PortableInstallResult:
    action = "install portable package"
    recovery = "Rebuild the portable package and retry."
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Portable package '{archive_file}' was not found.",
            action=action,
            recovery="Build the portable package first and retry.",
        )
    verification = verify_portable_package(archive_file)
    if not verification.checksum_matches:
        raise ProtoLinkUserError(
            f"Portable package checksum validation failed for '{archive_file.name}'.",
            action=action,
            recovery=recovery,
        )
    extracted = _safe_extract_archive(
        archive_file,
        target_dir,
        action=action,
        recovery=recovery,
    )
    receipt_file = target_dir / "install-receipt.json"
    receipt_file.write_text(
        json.dumps(
            {
                "format_version": "protolink-install-receipt-v1",
                "archive_file": archive_file.name,
                "extracted_entries": list(extracted),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return PortableInstallResult(
        archive_file=archive_file,
        target_dir=target_dir,
        extracted_entries=tuple(extracted),
        receipt_file=receipt_file,
    )


def uninstall_portable_package(target_dir: Path) -> PortableUninstallResult:
    action = "uninstall portable package"
    recovery = "Reinstall the portable package or repair the install receipt and retry."
    receipt_file = target_dir / "install-receipt.json"
    if not receipt_file.exists():
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_file}' was not found.",
            action=action,
            recovery="Install the portable package first or verify the target directory.",
        )
    try:
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_file}' is invalid: {exc}",
            action=action,
            recovery=recovery,
        ) from exc
    if not isinstance(receipt, dict):
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_file}' must contain a JSON object.",
            action=action,
            recovery=recovery,
        )
    entries_raw = receipt.get("extracted_entries", [])
    if not isinstance(entries_raw, list):
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_file}' is missing a valid extracted_entries list.",
            action=action,
            recovery=recovery,
        )
    target_root = target_dir.resolve()
    validated_entries = [
        (
            str(item),
            _safe_receipt_member_path(
                target_root,
                str(item),
                receipt_name=receipt_file.name,
                action=action,
                recovery=recovery,
            ),
        )
        for item in entries_raw
    ]
    removed: list[str] = []
    for relative, candidate in validated_entries:
        if candidate.exists() and candidate.is_file():
            candidate.unlink()
            removed.append(relative)

    for path in sorted(target_dir.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

    removed_receipt = False
    if receipt_file.exists():
        receipt_file.unlink()
        removed_receipt = True
    return PortableUninstallResult(
        target_dir=target_dir,
        removed_entries=tuple(removed),
        removed_receipt=removed_receipt,
    )


def verify_portable_package(archive_file: Path) -> PortablePackageVerificationResult:
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Portable package '{archive_file}' was not found.",
            action="verify portable package",
            recovery="Build the portable package first and retry.",
        )
    with ZipFile(archive_file, "r") as archive:
        names = {name for name in archive.namelist() if name}
        if PORTABLE_MANIFEST_FILE not in names:
            raise ProtoLinkUserError(
                f"Portable package archive is missing '{PORTABLE_MANIFEST_FILE}'.",
                action="verify portable package",
                recovery="Rebuild the portable package and retry.",
            )
        manifest = _read_archive_manifest(
            archive,
            PORTABLE_MANIFEST_FILE,
            manifest_label="Portable package manifest",
            action="verify portable package",
            recovery="Rebuild the portable package and retry.",
        )
        _require_manifest_format_version(
            manifest,
            PORTABLE_PACKAGE_FORMAT_VERSION,
            manifest_label="Portable package manifest",
            action="verify portable package",
            recovery="Rebuild the portable package and retry.",
        )
        release_archive_name = _require_manifest_string(
            manifest,
            "release_archive_file",
            manifest_label="Portable package manifest",
            action="verify portable package",
            recovery="Rebuild the portable package and retry.",
        )
        if not release_archive_name or release_archive_name not in names:
            raise ProtoLinkUserError(
                "Portable package archive is missing the release archive referenced by its manifest.",
                action="verify portable package",
                recovery="Rebuild the portable package and retry.",
            )
        checksums = _require_manifest_checksums(
            manifest,
            manifest_label="Portable package manifest",
            action="verify portable package",
            recovery="Rebuild the portable package and retry.",
        )

        payload_entries = {
            name
            for name in names
            if not name.endswith("/") and name != PORTABLE_MANIFEST_FILE
        }
        checksum_matches = payload_entries == set(checksums)
        if checksum_matches:
            for name, expected_checksum in checksums.items():
                if name not in names:
                    checksum_matches = False
                    break
                actual_checksum = hashlib.sha256(archive.read(name)).hexdigest()
                if actual_checksum != expected_checksum:
                    checksum_matches = False
                    break

        install_scripts = tuple(name for name in ("INSTALL.ps1",) if name in names)
        return PortablePackageVerificationResult(
            archive_file=archive_file,
            portable_manifest_file=PORTABLE_MANIFEST_FILE,
            release_archive_file=release_archive_name,
            checksum_matches=checksum_matches,
            install_scripts_present=install_scripts,
        )


def build_distribution_package_plan(
    workspace: WorkspaceLayout,
    name: str,
    portable_archive_file: Path,
    release_archive_file: Path,
    *,
    packaged_at: datetime | None = None,
) -> DistributionPackagePlan:
    packaged_at = packaged_at or datetime.now(UTC)
    package_name = f"{build_artifact_timestamp(packaged_at)}-distribution-{sanitize_artifact_name(name)}"
    package_dir = _package_staging_dir(workspace.exports, "distribution", package_name)
    archive_file = workspace.exports / f"{package_name}.zip"
    manifest_file = package_dir / "distribution-manifest.json"
    return DistributionPackagePlan(
        package_dir=package_dir,
        archive_file=archive_file,
        manifest_file=manifest_file,
        package_name=package_name,
        portable_archive_file=portable_archive_file,
        release_archive_file=release_archive_file,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_checksum_map(raw_checksums: object) -> dict[str, str]:
    if not isinstance(raw_checksums, dict):
        return {}
    return {
        str(name): str(checksum).strip()
        for name, checksum in raw_checksums.items()
        if str(name).strip()
    }


def _require_manifest_object(raw_manifest: object, *, manifest_label: str, action: str, recovery: str) -> dict[str, object]:
    if isinstance(raw_manifest, dict):
        return raw_manifest
    raise ProtoLinkUserError(
        f"{manifest_label} must be a JSON object.",
        action=action,
        recovery=recovery,
    )


def _read_manifest_text(raw_text: str, *, manifest_label: str, action: str, recovery: str) -> dict[str, object]:
    try:
        return _require_manifest_object(
            json.loads(raw_text),
            manifest_label=manifest_label,
            action=action,
            recovery=recovery,
        )
    except json.JSONDecodeError as exc:
        raise ProtoLinkUserError(
            f"{manifest_label} is not valid JSON.",
            action=action,
            recovery=recovery,
        ) from exc


def _read_archive_manifest(
    archive: ZipFile,
    manifest_name: str,
    *,
    manifest_label: str,
    action: str,
    recovery: str,
) -> dict[str, object]:
    try:
        raw_text = archive.read(manifest_name).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtoLinkUserError(
            f"{manifest_label} is not valid UTF-8.",
            action=action,
            recovery=recovery,
        ) from exc
    return _read_manifest_text(raw_text, manifest_label=manifest_label, action=action, recovery=recovery)


def _read_file_manifest(path: Path, *, manifest_label: str, action: str, recovery: str) -> dict[str, object]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ProtoLinkUserError(
            f"{manifest_label} is not valid UTF-8.",
            action=action,
            recovery=recovery,
        ) from exc
    return _read_manifest_text(raw_text, manifest_label=manifest_label, action=action, recovery=recovery)


def _require_manifest_format_version(
    manifest: dict[str, object],
    expected_version: str,
    *,
    manifest_label: str,
    action: str,
    recovery: str,
) -> None:
    actual_version = manifest.get("format_version")
    if not isinstance(actual_version, str) or actual_version.strip() != expected_version:
        raise ProtoLinkUserError(
            f"{manifest_label} has unsupported format_version '{actual_version}'.",
            action=action,
            recovery=recovery,
        )


def _require_manifest_string(
    manifest: dict[str, object],
    key: str,
    *,
    manifest_label: str,
    action: str,
    recovery: str,
) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProtoLinkUserError(
            f"{manifest_label} is missing string field '{key}'.",
            action=action,
            recovery=recovery,
        )
    return value.strip()


def _require_manifest_checksums(
    manifest: dict[str, object],
    *,
    manifest_label: str,
    action: str,
    recovery: str,
) -> dict[str, str]:
    raw_checksums = manifest.get("checksums")
    if not isinstance(raw_checksums, dict):
        raise ProtoLinkUserError(
            f"{manifest_label} is missing object field 'checksums'.",
            action=action,
            recovery=recovery,
        )
    checksums = _normalize_checksum_map(raw_checksums)
    if not checksums or len(checksums) != len(raw_checksums):
        raise ProtoLinkUserError(
            f"{manifest_label} has invalid checksum entries.",
            action=action,
            recovery=recovery,
        )
    return checksums


def _require_archive_file(path: Path, *, action: str, artifact_label: str, recovery: str) -> None:
    if path.exists() and path.is_file():
        return
    raise ProtoLinkUserError(
        f"{artifact_label} '{path.name}' was not found after extraction.",
        action=action,
        recovery=recovery,
    )


def _require_expected_checksum(
    path: Path,
    expected_checksum: str,
    *,
    action: str,
    artifact_label: str,
    recovery: str,
) -> None:
    if not expected_checksum:
        raise ProtoLinkUserError(
            f"{artifact_label} is missing a checksum for '{path.name}'.",
            action=action,
            recovery=recovery,
        )
    actual_checksum = _sha256_file(path)
    if actual_checksum == expected_checksum:
        return
    raise ProtoLinkUserError(
        f"{artifact_label} checksum mismatch for '{path.name}'.",
        action=action,
        recovery=recovery,
    )


def _safe_extract_archive(
    archive_file: Path,
    destination_dir: Path,
    *,
    action: str,
    recovery: str,
) -> tuple[str, ...]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_root = destination_dir.resolve()
    extracted_entries: list[str] = []
    with ZipFile(archive_file, "r") as archive:
        for info in archive.infolist():
            member_name = info.filename.replace("\\", "/")
            if not member_name.strip():
                continue
            if _zip_info_is_symlink(info):
                raise ProtoLinkUserError(
                    f"Archive '{archive_file.name}' contains an unsupported symlink entry '{member_name}'.",
                    action=action,
                    recovery=recovery,
                )
            destination_path = _safe_archive_member_path(
                destination_root,
                member_name,
                archive_name=archive_file.name,
                action=action,
                recovery=recovery,
            )
            if info.is_dir():
                destination_path.mkdir(parents=True, exist_ok=True)
                extracted_entries.append(info.filename)
                continue
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, destination_path.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            extracted_entries.append(info.filename)
    return tuple(extracted_entries)


def _safe_archive_member_path(
    destination_root: Path,
    member_name: str,
    *,
    archive_name: str,
    action: str,
    recovery: str,
) -> Path:
    normalized_member = PurePosixPath(member_name)
    if normalized_member.is_absolute():
        raise ProtoLinkUserError(
            f"Archive '{archive_name}' contains an invalid absolute path entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )
    if normalized_member.parts and normalized_member.parts[0].endswith(":"):
        raise ProtoLinkUserError(
            f"Archive '{archive_name}' contains an invalid drive-qualified path entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )
    if any(part == ".." for part in normalized_member.parts):
        raise ProtoLinkUserError(
            f"Archive '{archive_name}' contains an unsafe path traversal entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )

    destination_path = (destination_root / Path(*normalized_member.parts)).resolve()
    try:
        destination_path.relative_to(destination_root)
    except ValueError as exc:
        raise ProtoLinkUserError(
            f"Archive '{archive_name}' contains an entry outside the target directory: '{member_name}'.",
            action=action,
            recovery=recovery,
        ) from exc
    return destination_path


def _safe_receipt_member_path(
    destination_root: Path,
    member_name: str,
    *,
    receipt_name: str,
    action: str,
    recovery: str,
) -> Path:
    normalized_member = PurePosixPath(member_name.replace("\\", "/"))
    if not normalized_member.parts:
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_name}' contains an empty extracted entry.",
            action=action,
            recovery=recovery,
        )
    if normalized_member.is_absolute():
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_name}' contains an invalid absolute path entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )
    if normalized_member.parts and normalized_member.parts[0].endswith(":"):
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_name}' contains an invalid drive-qualified path entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )
    if any(part == ".." for part in normalized_member.parts):
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_name}' contains an unsafe path traversal entry '{member_name}'.",
            action=action,
            recovery=recovery,
        )

    destination_path = (destination_root / Path(*normalized_member.parts)).resolve()
    try:
        destination_path.relative_to(destination_root)
    except ValueError as exc:
        raise ProtoLinkUserError(
            f"Install receipt '{receipt_name}' contains an entry outside the install directory: '{member_name}'.",
            action=action,
            recovery=recovery,
        ) from exc
    return destination_path


def _zip_info_is_symlink(info) -> bool:
    unix_mode = info.external_attr >> 16
    return (unix_mode & 0o170000) == 0o120000


def _build_portable_package_manifest(
    plan: PortablePackagePlan,
    included_entries: list[str],
    manifest_file: Path,
) -> dict[str, object]:
    checksums: dict[str, str] = {}
    for path in sorted(plan.package_dir.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path == manifest_file:
            continue
        checksums[str(path.relative_to(plan.package_dir)).replace("\\", "/")] = _sha256_file(path)
    return {
        "format_version": PORTABLE_PACKAGE_FORMAT_VERSION,
        "package_name": plan.package_name,
        "release_archive_file": plan.release_archive_file.name,
        "archive_file": plan.archive_file.name,
        "install_scripts": ["INSTALL.ps1"],
        **_build_bundled_runtime_requirements(),
        "checksums": checksums,
        "included_entries": list(included_entries),
    }


def materialize_distribution_package(plan: DistributionPackagePlan, repo_root: Path) -> dict[str, object]:
    for required in (plan.portable_archive_file, plan.release_archive_file):
        if not required.exists():
            raise ProtoLinkUserError(
                f"Distribution source '{required}' was not found.",
                action="build distribution package",
                recovery="Build the release and portable package artifacts first and retry.",
            )

    plan.package_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    def copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(plan.package_dir)))

    for relative in (
        Path("README.md"),
        Path("docs/RELEASE_CHECKLIST.md"),
        Path("docs/SMOKE_CHECKLIST.md"),
    ):
        source = repo_root / relative
        if source.exists():
            copy_file(source, plan.package_dir / relative)

    portable_dest = plan.package_dir / plan.portable_archive_file.name
    release_dest = plan.package_dir / plan.release_archive_file.name
    copy_file(plan.portable_archive_file, portable_dest)
    copy_file(plan.release_archive_file, release_dest)

    manifest: dict[str, object] = {
        "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
        "package_name": plan.package_name,
        "portable_archive_file": portable_dest.name,
        "release_archive_file": release_dest.name,
        "checksums": {
            portable_dest.name: _sha256_file(portable_dest),
            release_dest.name: _sha256_file(release_dest),
        },
        "install_command": f".\\Install-Distribution.ps1 <target-dir>",
        "included_entries": copied,
    }
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    copied.append("distribution-manifest.json")

    if plan.archive_file.exists():
        plan.archive_file.unlink()
    with ZipFile(plan.archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for path in plan.package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(plan.package_dir))
    return manifest


def install_distribution_package(archive_file: Path, staging_dir: Path, install_dir: Path) -> DistributionInstallResult:
    action = "install distribution package"
    recovery = "Rebuild the distribution package and retry."
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Distribution package '{archive_file}' was not found.",
            action=action,
            recovery="Build the distribution package first and retry.",
        )
    _safe_extract_archive(
        archive_file,
        staging_dir,
        action=action,
        recovery=recovery,
    )

    manifest_file = staging_dir / "distribution-manifest.json"
    if not manifest_file.exists():
        raise ProtoLinkUserError(
            f"Distribution manifest '{manifest_file}' was not found after extraction.",
            action=action,
            recovery=recovery,
        )
    manifest = _read_file_manifest(
        manifest_file,
        manifest_label="Distribution manifest",
        action=action,
        recovery=recovery,
    )
    _require_manifest_format_version(
        manifest,
        DISTRIBUTION_PACKAGE_FORMAT_VERSION,
        manifest_label="Distribution manifest",
        action=action,
        recovery=recovery,
    )
    portable_name = _require_manifest_string(
        manifest,
        "portable_archive_file",
        manifest_label="Distribution manifest",
        action=action,
        recovery=recovery,
    )
    release_name = _require_manifest_string(
        manifest,
        "release_archive_file",
        manifest_label="Distribution manifest",
        action=action,
        recovery=recovery,
    )
    checksums = _require_manifest_checksums(
        manifest,
        manifest_label="Distribution manifest",
        action=action,
        recovery=recovery,
    )
    portable_archive = staging_dir / portable_name
    release_archive = staging_dir / release_name
    _require_archive_file(
        portable_archive,
        action=action,
        artifact_label="Distribution archive",
        recovery=recovery,
    )
    _require_archive_file(
        release_archive,
        action=action,
        artifact_label="Distribution archive",
        recovery=recovery,
    )
    _require_expected_checksum(
        portable_archive,
        checksums.get(portable_name, ""),
        action=action,
        artifact_label="Distribution manifest",
        recovery=recovery,
    )
    _require_expected_checksum(
        release_archive,
        checksums.get(release_name, ""),
        action=action,
        artifact_label="Distribution manifest",
        recovery=recovery,
    )
    portable_install = install_portable_package(portable_archive, install_dir)
    return DistributionInstallResult(
        archive_file=archive_file,
        staging_dir=staging_dir,
        install_dir=install_dir,
        distribution_manifest_file=manifest_file,
        portable_install=portable_install,
    )


def verify_distribution_package(archive_file: Path) -> DistributionPackageVerificationResult:
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Distribution package '{archive_file}' was not found.",
            action="verify distribution package",
            recovery="Build the distribution package first and retry.",
        )
    with ZipFile(archive_file, "r") as archive:
        names = {name for name in archive.namelist() if name}
        if "distribution-manifest.json" not in names:
            raise ProtoLinkUserError(
                "Distribution package archive is missing 'distribution-manifest.json'.",
                action="verify distribution package",
                recovery="Rebuild the distribution package and retry.",
            )
        manifest = _read_archive_manifest(
            archive,
            "distribution-manifest.json",
            manifest_label="Distribution package manifest",
            action="verify distribution package",
            recovery="Rebuild the distribution package and retry.",
        )
        _require_manifest_format_version(
            manifest,
            DISTRIBUTION_PACKAGE_FORMAT_VERSION,
            manifest_label="Distribution package manifest",
            action="verify distribution package",
            recovery="Rebuild the distribution package and retry.",
        )
        portable_name = _require_manifest_string(
            manifest,
            "portable_archive_file",
            manifest_label="Distribution package manifest",
            action="verify distribution package",
            recovery="Rebuild the distribution package and retry.",
        )
        release_name = _require_manifest_string(
            manifest,
            "release_archive_file",
            manifest_label="Distribution package manifest",
            action="verify distribution package",
            recovery="Rebuild the distribution package and retry.",
        )
        if not portable_name or portable_name not in names:
            raise ProtoLinkUserError(
                "Distribution package archive is missing the portable archive referenced by its manifest.",
                action="verify distribution package",
                recovery="Rebuild the distribution package and retry.",
            )
        if not release_name or release_name not in names:
            raise ProtoLinkUserError(
                "Distribution package archive is missing the release archive referenced by its manifest.",
                action="verify distribution package",
                recovery="Rebuild the distribution package and retry.",
            )
        checksums = _require_manifest_checksums(
            manifest,
            manifest_label="Distribution package manifest",
            action="verify distribution package",
            recovery="Rebuild the distribution package and retry.",
        )
        checksum_matches = True
        for name, expected_checksum in ((portable_name, checksums.get(portable_name, "")), (release_name, checksums.get(release_name, ""))):
            if not expected_checksum:
                checksum_matches = False
                break
            actual_checksum = hashlib.sha256(archive.read(name)).hexdigest()
            if actual_checksum != expected_checksum:
                checksum_matches = False
                break
        return DistributionPackageVerificationResult(
            archive_file=archive_file,
            distribution_manifest_file="distribution-manifest.json",
            portable_archive_file=portable_name,
            release_archive_file=release_name,
            checksum_matches=checksum_matches,
        )


def build_installer_staging_plan(
    workspace: WorkspaceLayout,
    name: str,
    distribution_archive_file: Path,
    *,
    packaged_at: datetime | None = None,
) -> InstallerStagingPlan:
    packaged_at = packaged_at or datetime.now(UTC)
    package_name = f"{build_artifact_timestamp(packaged_at)}-installer-{sanitize_artifact_name(name)}"
    package_dir = _package_staging_dir(workspace.exports, "installer", package_name)
    archive_file = workspace.exports / f"{package_name}.zip"
    manifest_file = package_dir / "installer-manifest.json"
    return InstallerStagingPlan(
        package_dir=package_dir,
        archive_file=archive_file,
        manifest_file=manifest_file,
        package_name=package_name,
        distribution_archive_file=distribution_archive_file,
    )


def materialize_installer_staging_package(plan: InstallerStagingPlan, repo_root: Path) -> dict[str, object]:
    if not plan.distribution_archive_file.exists():
        raise ProtoLinkUserError(
            f"Distribution archive '{plan.distribution_archive_file}' was not found.",
            action="build installer staging package",
            recovery="Build the distribution package first and retry.",
        )
    plan.package_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    def copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(plan.package_dir)))

    for relative in (
        Path("README.md"),
        Path("docs/RELEASE_CHECKLIST.md"),
        Path("docs/SMOKE_CHECKLIST.md"),
    ):
        source = repo_root / relative
        if source.exists():
            copy_file(source, plan.package_dir / relative)

    distribution_dest = plan.package_dir / plan.distribution_archive_file.name
    copy_file(plan.distribution_archive_file, distribution_dest)

    install_ps1 = plan.package_dir / "Install-Distribution.ps1"
    install_ps1.write_text(
        "\n".join(
            (
                "param([string]$TargetDir = '.\\installed')",
                "$ErrorActionPreference = 'Stop'",
                "$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path",
                "$distributionArchive = Join-Path $scriptRoot '" + distribution_dest.name + "'",
                "$manifestPath = Join-Path $scriptRoot 'installer-manifest.json'",
                "$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json",
                "$expected = $manifest.checksum",
                "$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $distributionArchive).Hash.ToLowerInvariant()",
                "if ($actual -ne $expected.ToLowerInvariant()) { throw 'Installer manifest checksum mismatch.' }",
                "$staging = Join-Path $scriptRoot 'distribution-staging'",
                "if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }",
                "Expand-Archive -LiteralPath $distributionArchive -DestinationPath $staging -Force",
                "$distributionManifestPath = Join-Path $staging 'distribution-manifest.json'",
                "$distributionManifest = Get-Content -LiteralPath $distributionManifestPath -Raw | ConvertFrom-Json",
                "$portableArchive = Join-Path $staging $distributionManifest.portable_archive_file",
                "$portableChecksum = $distributionManifest.checksums.$($distributionManifest.portable_archive_file)",
                "$portableActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $portableArchive).Hash.ToLowerInvariant()",
                "if ($portableActual -ne $portableChecksum.ToLowerInvariant()) { throw 'Distribution manifest portable checksum mismatch.' }",
                "Expand-Archive -LiteralPath $portableArchive -DestinationPath $TargetDir -Force",
                "$installScript = Join-Path $TargetDir 'INSTALL.ps1'",
                "if (Test-Path -LiteralPath $installScript) { & $installScript }",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Install-Distribution.ps1")

    install_bat = plan.package_dir / "Install-Distribution.bat"
    install_bat.write_text(
        "\n".join(
            (
                "@echo off",
                "set TARGETDIR=%1",
                'if "%TARGETDIR%"=="" set TARGETDIR=.\\installed',
                'powershell -ExecutionPolicy Bypass -File "%~dp0Install-Distribution.ps1" "%TARGETDIR%"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Install-Distribution.bat")

    manifest: dict[str, object] = {
        "format_version": INSTALLER_STAGING_FORMAT_VERSION,
        "package_name": plan.package_name,
        "distribution_archive_file": distribution_dest.name,
        "checksum": _sha256_file(distribution_dest),
        "install_scripts": ["Install-Distribution.ps1", "Install-Distribution.bat"],
        **_build_bundled_runtime_requirements(),
        "included_entries": copied,
    }
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    copied.append("installer-manifest.json")

    if plan.archive_file.exists():
        plan.archive_file.unlink()
    with ZipFile(plan.archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for path in plan.package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(plan.package_dir))
    return manifest


def install_installer_staging_package(archive_file: Path, staging_dir: Path, install_dir: Path) -> InstallerStagingInstallResult:
    action = "install installer staging package"
    recovery = "Rebuild the installer staging package and retry."
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Installer staging archive '{archive_file}' was not found.",
            action=action,
            recovery="Build the installer staging package first and retry.",
        )
    _safe_extract_archive(
        archive_file,
        staging_dir,
        action=action,
        recovery=recovery,
    )

    manifest_file = staging_dir / "installer-manifest.json"
    if not manifest_file.exists():
        raise ProtoLinkUserError(
            f"Installer manifest '{manifest_file}' was not found after extraction.",
            action=action,
            recovery=recovery,
        )
    manifest = _read_file_manifest(
        manifest_file,
        manifest_label="Installer manifest",
        action=action,
        recovery=recovery,
    )
    _require_manifest_format_version(
        manifest,
        INSTALLER_STAGING_FORMAT_VERSION,
        manifest_label="Installer manifest",
        action=action,
        recovery=recovery,
    )
    distribution_name = _require_manifest_string(
        manifest,
        "distribution_archive_file",
        manifest_label="Installer manifest",
        action=action,
        recovery=recovery,
    )
    expected_checksum = _require_manifest_string(
        manifest,
        "checksum",
        manifest_label="Installer manifest",
        action=action,
        recovery=recovery,
    )
    distribution_archive = staging_dir / distribution_name
    _require_archive_file(
        distribution_archive,
        action=action,
        artifact_label="Installer staging archive",
        recovery=recovery,
    )
    _require_expected_checksum(
        distribution_archive,
        expected_checksum,
        action=action,
        artifact_label="Installer manifest",
        recovery=recovery,
    )
    distribution_staging = staging_dir / "distribution"
    distribution_install = install_distribution_package(distribution_archive, distribution_staging, install_dir)
    return InstallerStagingInstallResult(
        archive_file=archive_file,
        staging_dir=staging_dir,
        install_dir=install_dir,
        installer_manifest_file=manifest_file,
        distribution_install=distribution_install,
    )


def verify_installer_staging_package(archive_file: Path) -> InstallerStagingVerificationResult:
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Installer staging archive '{archive_file}' was not found.",
            action="verify installer staging package",
            recovery="Build the installer staging package first and retry.",
        )
    with ZipFile(archive_file, "r") as archive:
        names = set(archive.namelist())
        if "installer-manifest.json" not in names:
            raise ProtoLinkUserError(
                "Installer staging archive is missing 'installer-manifest.json'.",
                action="verify installer staging package",
                recovery="Rebuild the installer staging package and retry.",
            )
        manifest = _read_archive_manifest(
            archive,
            "installer-manifest.json",
            manifest_label="Installer staging manifest",
            action="verify installer staging package",
            recovery="Rebuild the installer staging package and retry.",
        )
        _require_manifest_format_version(
            manifest,
            INSTALLER_STAGING_FORMAT_VERSION,
            manifest_label="Installer staging manifest",
            action="verify installer staging package",
            recovery="Rebuild the installer staging package and retry.",
        )
        distribution_name = _require_manifest_string(
            manifest,
            "distribution_archive_file",
            manifest_label="Installer staging manifest",
            action="verify installer staging package",
            recovery="Rebuild the installer staging package and retry.",
        )
        if not distribution_name or distribution_name not in names:
            raise ProtoLinkUserError(
                "Installer staging archive is missing the distribution archive referenced by its manifest.",
                action="verify installer staging package",
                recovery="Rebuild the installer staging package and retry.",
            )
        expected_checksum = _require_manifest_string(
            manifest,
            "checksum",
            manifest_label="Installer staging manifest",
            action="verify installer staging package",
            recovery="Rebuild the installer staging package and retry.",
        )
        distribution_bytes = archive.read(distribution_name)
        digest = hashlib.sha256(distribution_bytes).hexdigest()
        install_scripts = tuple(
            name for name in ("Install-Distribution.ps1", "Install-Distribution.bat") if name in names
        )
        return InstallerStagingVerificationResult(
            archive_file=archive_file,
            installer_manifest_file="installer-manifest.json",
            distribution_archive_file=distribution_name,
            checksum_matches=(expected_checksum == digest),
            install_scripts_present=install_scripts,
        )


def build_installer_package_plan(
    workspace: WorkspaceLayout,
    name: str,
    installer_staging_archive_file: Path,
    *,
    packaged_at: datetime | None = None,
) -> InstallerPackagePlan:
    packaged_at = packaged_at or datetime.now(UTC)
    package_name = f"{build_artifact_timestamp(packaged_at)}-installer-package-{sanitize_artifact_name(name)}"
    package_dir = _package_staging_dir(workspace.exports, "installer-package", package_name)
    archive_file = workspace.exports / f"{package_name}.zip"
    manifest_file = package_dir / "installer-package-manifest.json"
    return InstallerPackagePlan(
        package_dir=package_dir,
        archive_file=archive_file,
        manifest_file=manifest_file,
        package_name=package_name,
        installer_staging_archive_file=installer_staging_archive_file,
    )


def materialize_installer_package(plan: InstallerPackagePlan, repo_root: Path) -> dict[str, object]:
    if not plan.installer_staging_archive_file.exists():
        raise ProtoLinkUserError(
            f"Installer staging archive '{plan.installer_staging_archive_file}' was not found.",
            action="build installer package",
            recovery="Build the installer staging package first and retry.",
        )
    plan.package_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    def copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(plan.package_dir)))

    for relative in (
        Path("README.md"),
        Path("docs/RELEASE_CHECKLIST.md"),
        Path("docs/SMOKE_CHECKLIST.md"),
    ):
        source = repo_root / relative
        if source.exists():
            copy_file(source, plan.package_dir / relative)

    installer_staging_dest = plan.package_dir / plan.installer_staging_archive_file.name
    copy_file(plan.installer_staging_archive_file, installer_staging_dest)

    install_ps1 = plan.package_dir / "Install-ProtoLink.ps1"
    install_ps1.write_text(
        "\n".join(
            (
                "param([string]$TargetDir = '.\\installed')",
                "$ErrorActionPreference = 'Stop'",
                "$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path",
                "$archive = Join-Path $scriptRoot '" + installer_staging_dest.name + "'",
                "$manifestPath = Join-Path $scriptRoot 'installer-package-manifest.json'",
                "$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json",
                "$expected = $manifest.checksum",
                "$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()",
                "if ($actual -ne $expected.ToLowerInvariant()) { throw 'Installer package manifest checksum mismatch.' }",
                "$staging = Join-Path $scriptRoot 'installer-staging'",
                "if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }",
                "Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force",
                "$innerInstall = Join-Path $staging 'Install-Distribution.ps1'",
                "if (-not (Test-Path -LiteralPath $innerInstall)) { throw 'Installer staging install script is missing.' }",
                '& $innerInstall $TargetDir',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Install-ProtoLink.ps1")

    install_bat = plan.package_dir / "Install-ProtoLink.bat"
    install_bat.write_text(
        "\n".join(
            (
                "@echo off",
                "set TARGETDIR=%1",
                'if "%TARGETDIR%"=="" set TARGETDIR=.\\installed',
                'powershell -ExecutionPolicy Bypass -File "%~dp0Install-ProtoLink.ps1" "%TARGETDIR%"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    copied.append("Install-ProtoLink.bat")

    manifest: dict[str, object] = {
        "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
        "package_name": plan.package_name,
        "installer_staging_archive_file": installer_staging_dest.name,
        "checksum": _sha256_file(installer_staging_dest),
        "install_scripts": ["Install-ProtoLink.ps1", "Install-ProtoLink.bat"],
        **_build_bundled_runtime_requirements(),
        "included_entries": copied,
    }
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    copied.append("installer-package-manifest.json")

    if plan.archive_file.exists():
        plan.archive_file.unlink()
    with ZipFile(plan.archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for path in plan.package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(plan.package_dir))
    return manifest


def install_installer_package(archive_file: Path, staging_dir: Path, install_dir: Path) -> InstallerPackageInstallResult:
    action = "install installer package"
    recovery = "Rebuild the installer package and retry."
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Installer package '{archive_file}' was not found.",
            action=action,
            recovery="Build the installer package first and retry.",
        )
    _safe_extract_archive(
        archive_file,
        staging_dir,
        action=action,
        recovery=recovery,
    )

    manifest_file = staging_dir / "installer-package-manifest.json"
    if not manifest_file.exists():
        raise ProtoLinkUserError(
            f"Installer package manifest '{manifest_file}' was not found after extraction.",
            action=action,
            recovery=recovery,
        )
    manifest = _read_file_manifest(
        manifest_file,
        manifest_label="Installer package manifest",
        action=action,
        recovery=recovery,
    )
    _require_manifest_format_version(
        manifest,
        INSTALLER_PACKAGE_FORMAT_VERSION,
        manifest_label="Installer package manifest",
        action=action,
        recovery=recovery,
    )
    installer_staging_name = _require_manifest_string(
        manifest,
        "installer_staging_archive_file",
        manifest_label="Installer package manifest",
        action=action,
        recovery=recovery,
    )
    expected_checksum = _require_manifest_string(
        manifest,
        "checksum",
        manifest_label="Installer package manifest",
        action=action,
        recovery=recovery,
    )
    installer_staging_archive = staging_dir / installer_staging_name
    _require_archive_file(
        installer_staging_archive,
        action=action,
        artifact_label="Installer package archive",
        recovery=recovery,
    )
    _require_expected_checksum(
        installer_staging_archive,
        expected_checksum,
        action=action,
        artifact_label="Installer package manifest",
        recovery=recovery,
    )
    installer_staging_staging = staging_dir / "installer-staging"
    installer_staging_install = install_installer_staging_package(
        installer_staging_archive,
        installer_staging_staging,
        install_dir,
    )
    return InstallerPackageInstallResult(
        archive_file=archive_file,
        staging_dir=staging_dir,
        install_dir=install_dir,
        installer_package_manifest_file=manifest_file,
        installer_staging_install=installer_staging_install,
    )


def verify_installer_package(archive_file: Path) -> InstallerPackageVerificationResult:
    if not archive_file.exists() or not archive_file.is_file():
        raise ProtoLinkUserError(
            f"Installer package '{archive_file}' was not found.",
            action="verify installer package",
            recovery="Build the installer package first and retry.",
        )
    with ZipFile(archive_file, "r") as archive:
        names = set(archive.namelist())
        if "installer-package-manifest.json" not in names:
            raise ProtoLinkUserError(
                "Installer package archive is missing 'installer-package-manifest.json'.",
                action="verify installer package",
                recovery="Rebuild the installer package and retry.",
            )
        manifest = _read_archive_manifest(
            archive,
            "installer-package-manifest.json",
            manifest_label="Installer package manifest",
            action="verify installer package",
            recovery="Rebuild the installer package and retry.",
        )
        _require_manifest_format_version(
            manifest,
            INSTALLER_PACKAGE_FORMAT_VERSION,
            manifest_label="Installer package manifest",
            action="verify installer package",
            recovery="Rebuild the installer package and retry.",
        )
        installer_staging_name = _require_manifest_string(
            manifest,
            "installer_staging_archive_file",
            manifest_label="Installer package manifest",
            action="verify installer package",
            recovery="Rebuild the installer package and retry.",
        )
        if not installer_staging_name or installer_staging_name not in names:
            raise ProtoLinkUserError(
                "Installer package archive is missing the installer-staging archive referenced by its manifest.",
                action="verify installer package",
                recovery="Rebuild the installer package and retry.",
            )
        expected_checksum = _require_manifest_string(
            manifest,
            "checksum",
            manifest_label="Installer package manifest",
            action="verify installer package",
            recovery="Rebuild the installer package and retry.",
        )
        installer_staging_bytes = archive.read(installer_staging_name)
        digest = hashlib.sha256(installer_staging_bytes).hexdigest()
        install_scripts = tuple(
            name for name in ("Install-ProtoLink.ps1", "Install-ProtoLink.bat") if name in names
        )
        return InstallerPackageVerificationResult(
            archive_file=archive_file,
            installer_package_manifest_file="installer-package-manifest.json",
            installer_staging_archive_file=installer_staging_name,
            checksum_matches=(expected_checksum == digest),
            install_scripts_present=install_scripts,
        )


def _normalize_windows_installer_version(version: str) -> str:
    numbers = [str(int(part)) for part in re.findall(r"\d+", version)[:3]]
    while len(numbers) < 3:
        numbers.append("0")
    return ".".join(numbers or ["0", "0", "0"])


def build_native_installer_scaffold_plan(
    workspace: WorkspaceLayout,
    name: str,
    installer_package_archive_file: Path,
    *,
    packaged_at: datetime | None = None,
) -> NativeInstallerScaffoldPlan:
    packaged_at = packaged_at or datetime.now(UTC)
    package_name = f"{build_artifact_timestamp(packaged_at)}-native-installer-{sanitize_artifact_name(name)}"
    package_dir = _package_staging_dir(workspace.exports, "native-installer", package_name)
    return NativeInstallerScaffoldPlan(
        package_dir=package_dir,
        manifest_file=package_dir / NATIVE_INSTALLER_MANIFEST_FILE,
        package_name=package_name,
        installer_package_archive_file=installer_package_archive_file,
        wix_source_file=package_dir / NATIVE_INSTALLER_WIX_SOURCE_FILE,
        wix_include_file=package_dir / NATIVE_INSTALLER_WIX_INCLUDE_FILE,
        installer_package_file=package_dir / "payload" / installer_package_archive_file.name,
    )


def materialize_native_installer_scaffold(
    plan: NativeInstallerScaffoldPlan,
    repo_root: Path,
) -> dict[str, object]:
    action = "build native installer scaffold"
    recovery = "Build a valid installer package and regenerate the WiX/MSI scaffold."
    if not plan.installer_package_archive_file.exists():
        raise ProtoLinkUserError(
            f"Installer package archive '{plan.installer_package_archive_file}' was not found.",
            action=action,
            recovery="Build the installer package first and retry.",
        )

    installer_verification = verify_installer_package(plan.installer_package_archive_file)
    if not installer_verification.checksum_matches:
        raise ProtoLinkUserError(
            f"Installer package '{plan.installer_package_archive_file.name}' failed checksum verification.",
            action=action,
            recovery=recovery,
        )

    if plan.package_dir.exists():
        shutil.rmtree(plan.package_dir)
    plan.package_dir.mkdir(parents=True, exist_ok=True)
    plan.installer_package_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan.installer_package_archive_file, plan.installer_package_file)

    application_version = _read_protolink_version(repo_root)
    wix_product_version = _normalize_windows_installer_version(application_version)
    upgrade_code = str(uuid5(NAMESPACE_URL, "ProtoLink.NativeInstaller.UpgradeCode")).upper()
    installer_package_relative = str(plan.installer_package_file.relative_to(plan.package_dir)).replace("\\", "/")
    installer_package_wix_source = installer_package_relative.replace("/", "\\")
    silent_install_command = "msiexec /i ProtoLink.msi /qn /l*v install.log"
    silent_uninstall_command = "msiexec /x ProtoLink.msi /qn /l*v uninstall.log"
    headless_summary_command = "protolink --headless-summary"

    plan.wix_include_file.write_text(
        "\n".join(
            (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
                "<Include xmlns=\"http://wixtoolset.org/schemas/v4/wxs\">",
                f"  <?define ProtoLinkVersion = \"{wix_product_version}\" ?>",
                "  <?define ProtoLinkManufacturer = \"ProtoLink\" ?>",
                f"  <?define ProtoLinkUpgradeCode = \"{{{upgrade_code}}}\" ?>",
                f"  <?define ProtoLinkInstallScope = \"{NATIVE_INSTALLER_INSTALL_SCOPE}\" ?>",
                f"  <?define ProtoLinkInstallDirName = \"{NATIVE_INSTALLER_INSTALL_DIR_NAME}\" ?>",
                f"  <?define ProtoLinkPayloadDirName = \"{NATIVE_INSTALLER_PAYLOAD_DIR_NAME}\" ?>",
                f"  <?define ProtoLinkDowngradeErrorMessage = \"{NATIVE_INSTALLER_DOWNGRADE_ERROR_MESSAGE}\" ?>",
                f"  <?define ProtoLinkInstallerPackageName = \"{plan.installer_package_file.name}\" ?>",
                f"  <?define ProtoLinkInstallerPackageSource = \"{installer_package_wix_source}\" ?>",
                "</Include>",
                "",
            )
        ),
        encoding="utf-8",
    )

    plan.wix_source_file.write_text(
        "\n".join(
            (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
                "<Wix xmlns=\"http://wixtoolset.org/schemas/v4/wxs\">",
                f"  <?include {plan.wix_include_file.name}?>",
                "  <Package",
                "    Name=\"ProtoLink\"",
                "    Language=\"1033\"",
                "    Version=\"$(var.ProtoLinkVersion)\"",
                "    Manufacturer=\"$(var.ProtoLinkManufacturer)\"",
                "    UpgradeCode=\"$(var.ProtoLinkUpgradeCode)\"",
                "    InstallerVersion=\"500\"",
                "    Scope=\"$(var.ProtoLinkInstallScope)\"",
                "    Compressed=\"yes\">",
                "    <SummaryInformation Description=\"ProtoLink WiX v4 MSI scaffold\" />",
                "    <MediaTemplate EmbedCab=\"yes\" />",
                "    <MajorUpgrade DowngradeErrorMessage=\"$(var.ProtoLinkDowngradeErrorMessage)\" />",
                "    <StandardDirectory Id=\"ProgramFiles64Folder\">",
                "      <Directory Id=\"INSTALLDIR\" Name=\"$(var.ProtoLinkInstallDirName)\">",
                "        <Directory Id=\"PAYLOADDIR\" Name=\"$(var.ProtoLinkPayloadDirName)\" />",
                "      </Directory>",
                "    </StandardDirectory>",
                "    <Feature Id=\"MainFeature\" Title=\"ProtoLink\" Level=\"1\">",
                "      <ComponentGroupRef Id=\"ProtoLinkPayloadGroup\" />",
                "    </Feature>",
                "  </Package>",
                "  <Fragment>",
                "    <ComponentGroup Id=\"ProtoLinkPayloadGroup\" Directory=\"PAYLOADDIR\">",
                "      <Component Id=\"ProtoLinkInstallerPackageComponent\" Guid=\"*\">",
                "        <File Id=\"ProtoLinkInstallerPackageFile\"",
                "              KeyPath=\"yes\"",
                "              Name=\"$(var.ProtoLinkInstallerPackageName)\"",
                "              Source=\"$(var.ProtoLinkInstallerPackageSource)\" />",
                "      </Component>",
                "    </ComponentGroup>",
                "  </Fragment>",
                "</Wix>",
                "",
            )
        ),
        encoding="utf-8",
    )

    recommended_commands = _native_installer_recommended_commands()
    checksums = {
        installer_package_relative: _sha256_file(plan.installer_package_file),
        plan.wix_source_file.name: _sha256_file(plan.wix_source_file),
        plan.wix_include_file.name: _sha256_file(plan.wix_include_file),
    }
    manifest = {
        "format_version": NATIVE_INSTALLER_SCAFFOLD_FORMAT_VERSION,
        "package_name": plan.package_name,
        "application_name": "ProtoLink",
        "application_version": application_version,
        "wix_product_version": wix_product_version,
        "manufacturer": "ProtoLink",
        "target_arch": NATIVE_INSTALLER_TARGET_ARCH,
        "install_scope": NATIVE_INSTALLER_INSTALL_SCOPE,
        "install_dir_name": NATIVE_INSTALLER_INSTALL_DIR_NAME,
        "payload_dir_name": NATIVE_INSTALLER_PAYLOAD_DIR_NAME,
        "upgrade_code": f"{{{upgrade_code}}}",
        "product_code_policy": NATIVE_INSTALLER_PRODUCT_CODE_POLICY,
        "upgrade_strategy": NATIVE_INSTALLER_UPGRADE_STRATEGY,
        "downgrade_error_message": NATIVE_INSTALLER_DOWNGRADE_ERROR_MESSAGE,
        "silent_install_command": silent_install_command,
        "silent_uninstall_command": silent_uninstall_command,
        "headless_summary_command": headless_summary_command,
        "installer_package_file": installer_package_relative,
        "installer_package_source": str(plan.installer_package_archive_file.resolve()),
        "installer_package_checksum": checksums[installer_package_relative],
        "installer_package_manifest_file": installer_verification.installer_package_manifest_file,
        "wix_source_file": plan.wix_source_file.name,
        "wix_include_file": plan.wix_include_file.name,
        "checksums": checksums,
        "recommended_commands": list(recommended_commands.values()),
        "verification_expectations": [
            silent_install_command,
            headless_summary_command,
            silent_uninstall_command,
        ],
        "included_entries": [
            str(plan.installer_package_file.relative_to(plan.package_dir)).replace("\\", "/"),
            plan.wix_source_file.name,
            plan.wix_include_file.name,
        ],
    }
    plan.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _require_native_installer_scaffold_contract(
    manifest: dict[str, object],
    *,
    wix_source_text: str,
    wix_include_text: str,
    action: str,
    recovery: str,
) -> tuple[str, tuple[str, ...]]:
    application_version = _require_manifest_string(
        manifest,
        "application_version",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    wix_product_version = _require_manifest_string(
        manifest,
        "wix_product_version",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    manufacturer = _require_manifest_string(
        manifest,
        "manufacturer",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    target_arch = _require_manifest_string(
        manifest,
        "target_arch",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    install_scope = _require_manifest_string(
        manifest,
        "install_scope",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    install_dir_name = _require_manifest_string(
        manifest,
        "install_dir_name",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    payload_dir_name = _require_manifest_string(
        manifest,
        "payload_dir_name",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    upgrade_code = _require_manifest_string(
        manifest,
        "upgrade_code",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    product_code_policy = _require_manifest_string(
        manifest,
        "product_code_policy",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    upgrade_strategy = _require_manifest_string(
        manifest,
        "upgrade_strategy",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    downgrade_error_message = _require_manifest_string(
        manifest,
        "downgrade_error_message",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    silent_install_command = _require_manifest_string(
        manifest,
        "silent_install_command",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    silent_uninstall_command = _require_manifest_string(
        manifest,
        "silent_uninstall_command",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    headless_summary_command = _require_manifest_string(
        manifest,
        "headless_summary_command",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )

    verification_expectations = manifest.get("verification_expectations", [])
    if not isinstance(verification_expectations, list):
        raise ProtoLinkUserError(
            "Native installer scaffold manifest must provide a list of verification_expectations.",
            action=action,
            recovery=recovery,
        )
    expectation_set = {str(item) for item in verification_expectations}
    for command in (silent_install_command, headless_summary_command, silent_uninstall_command):
        if command not in expectation_set:
            raise ProtoLinkUserError(
                f"Native installer scaffold manifest is missing verification expectation '{command}'.",
                action=action,
                recovery=recovery,
            )

    required_include_lines = (
        f"<?define ProtoLinkVersion = \"{wix_product_version}\" ?>",
        f"<?define ProtoLinkManufacturer = \"{manufacturer}\" ?>",
        f"<?define ProtoLinkUpgradeCode = \"{upgrade_code}\" ?>",
        f"<?define ProtoLinkInstallScope = \"{install_scope}\" ?>",
        f"<?define ProtoLinkInstallDirName = \"{install_dir_name}\" ?>",
        f"<?define ProtoLinkPayloadDirName = \"{payload_dir_name}\" ?>",
        f"<?define ProtoLinkDowngradeErrorMessage = \"{downgrade_error_message}\" ?>",
    )
    for line in required_include_lines:
        if line not in wix_include_text:
            raise ProtoLinkUserError(
                f"Native installer scaffold include is missing contract line: {line}",
                action=action,
                recovery=recovery,
            )

    required_source_lines = (
        "Version=\"$(var.ProtoLinkVersion)\"",
        "Manufacturer=\"$(var.ProtoLinkManufacturer)\"",
        "UpgradeCode=\"$(var.ProtoLinkUpgradeCode)\"",
        "Scope=\"$(var.ProtoLinkInstallScope)\"",
        "Name=\"$(var.ProtoLinkInstallDirName)\"",
        "Name=\"$(var.ProtoLinkPayloadDirName)\"",
        "DowngradeErrorMessage=\"$(var.ProtoLinkDowngradeErrorMessage)\"",
    )
    for line in required_source_lines:
        if line not in wix_source_text:
            raise ProtoLinkUserError(
                f"Native installer scaffold source is missing contract line: {line}",
                action=action,
                recovery=recovery,
            )

    if target_arch != NATIVE_INSTALLER_TARGET_ARCH:
        raise ProtoLinkUserError(
            f"Native installer scaffold manifest target_arch must be '{NATIVE_INSTALLER_TARGET_ARCH}', got '{target_arch}'.",
            action=action,
            recovery=recovery,
        )
    if product_code_policy != NATIVE_INSTALLER_PRODUCT_CODE_POLICY:
        raise ProtoLinkUserError(
            f"Native installer scaffold manifest product_code_policy must be '{NATIVE_INSTALLER_PRODUCT_CODE_POLICY}', got '{product_code_policy}'.",
            action=action,
            recovery=recovery,
        )
    if upgrade_strategy != NATIVE_INSTALLER_UPGRADE_STRATEGY:
        raise ProtoLinkUserError(
            f"Native installer scaffold manifest upgrade_strategy must be '{NATIVE_INSTALLER_UPGRADE_STRATEGY}', got '{upgrade_strategy}'.",
            action=action,
            recovery=recovery,
        )
    if "ProductCode=" in wix_source_text:
        raise ProtoLinkUserError(
            "Native installer scaffold source must not pin ProductCode when product_code_policy is auto-generated.",
            action=action,
            recovery=recovery,
        )

    checked_fields = (
        "application_version",
        "wix_product_version",
        "manufacturer",
        "target_arch",
        "install_scope",
        "install_dir_name",
        "payload_dir_name",
        "upgrade_code",
        "product_code_policy",
        "upgrade_strategy",
        "downgrade_error_message",
        "silent_install_command",
        "silent_uninstall_command",
        "headless_summary_command",
        "verification_expectations",
    )
    return target_arch, checked_fields


def verify_native_installer_scaffold(scaffold_dir: Path) -> NativeInstallerScaffoldVerificationResult:
    action = "verify native installer scaffold"
    recovery = "Rebuild the native installer scaffold and retry."
    scaffold_dir = scaffold_dir.resolve()
    manifest_file = scaffold_dir / NATIVE_INSTALLER_MANIFEST_FILE
    if not manifest_file.exists():
        raise ProtoLinkUserError(
            f"Native installer scaffold manifest '{manifest_file}' was not found.",
            action=action,
            recovery=recovery,
        )
    manifest = _read_file_manifest(
        manifest_file,
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    _require_manifest_format_version(
        manifest,
        NATIVE_INSTALLER_SCAFFOLD_FORMAT_VERSION,
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    wix_source_file = _require_manifest_string(
        manifest,
        "wix_source_file",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    wix_include_file = _require_manifest_string(
        manifest,
        "wix_include_file",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    installer_package_file = _require_manifest_string(
        manifest,
        "installer_package_file",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    installer_package_checksum = _require_manifest_string(
        manifest,
        "installer_package_checksum",
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    checksums = _require_manifest_checksums(
        manifest,
        manifest_label="Native installer scaffold manifest",
        action=action,
        recovery=recovery,
    )
    included_entries_raw = manifest.get("included_entries")
    if not isinstance(included_entries_raw, list) or not included_entries_raw:
        raise ProtoLinkUserError(
            "Native installer scaffold manifest is missing list field 'included_entries'.",
            action=action,
            recovery=recovery,
        )
    included_entries = tuple(
        str(item).strip()
        for item in included_entries_raw
        if isinstance(item, str) and str(item).strip()
    )
    if len(included_entries) != len(included_entries_raw):
        raise ProtoLinkUserError(
            "Native installer scaffold manifest has invalid included_entries.",
            action=action,
            recovery=recovery,
        )
    if set(included_entries) != set(checksums):
        raise ProtoLinkUserError(
            "Native installer scaffold manifest checksums must exactly cover included_entries.",
            action=action,
            recovery=recovery,
        )

    wix_source_path = _safe_receipt_member_path(
        scaffold_dir,
        wix_source_file,
        receipt_name=manifest_file.name,
        action=action,
        recovery=recovery,
    )
    wix_include_path = _safe_receipt_member_path(
        scaffold_dir,
        wix_include_file,
        receipt_name=manifest_file.name,
        action=action,
        recovery=recovery,
    )
    installer_package_path = _safe_receipt_member_path(
        scaffold_dir,
        installer_package_file,
        receipt_name=manifest_file.name,
        action=action,
        recovery=recovery,
    )
    _require_archive_file(
        wix_source_path,
        action=action,
        artifact_label="Native installer scaffold source",
        recovery=recovery,
    )
    _require_archive_file(
        wix_include_path,
        action=action,
        artifact_label="Native installer scaffold include",
        recovery=recovery,
    )
    _require_archive_file(
        installer_package_path,
        action=action,
        artifact_label="Native installer scaffold payload",
        recovery=recovery,
    )
    _require_expected_checksum(
        installer_package_path,
        installer_package_checksum,
        action=action,
        artifact_label="Native installer scaffold manifest",
        recovery=recovery,
    )
    _require_expected_checksum(
        wix_source_path,
        checksums.get(wix_source_file, ""),
        action=action,
        artifact_label="Native installer scaffold manifest",
        recovery=recovery,
    )
    _require_expected_checksum(
        wix_include_path,
        checksums.get(wix_include_file, ""),
        action=action,
        artifact_label="Native installer scaffold manifest",
        recovery=recovery,
    )
    _require_expected_checksum(
        installer_package_path,
        checksums.get(installer_package_file, ""),
        action=action,
        artifact_label="Native installer scaffold manifest",
        recovery=recovery,
    )
    if checksums.get(installer_package_file) != installer_package_checksum:
        raise ProtoLinkUserError(
            "Native installer scaffold manifest installer_package_checksum does not match checksums entry.",
            action=action,
            recovery=recovery,
        )

    wix_source_text = wix_source_path.read_text(encoding="utf-8")
    wix_include_text = wix_include_path.read_text(encoding="utf-8")
    installer_package_basename = installer_package_path.name
    installer_package_wix_source = installer_package_file.replace("/", "\\")
    if wix_include_path.name not in wix_source_text:
        raise ProtoLinkUserError(
            f"Native installer scaffold source '{wix_source_path.name}' does not include '{wix_include_path.name}'.",
            action=action,
            recovery=recovery,
        )
    if installer_package_basename not in wix_include_text or installer_package_wix_source not in wix_include_text:
        raise ProtoLinkUserError(
            "Native installer scaffold include does not reference the copied installer package payload.",
            action=action,
            recovery=recovery,
        )
    target_arch, checked_contract_fields = _require_native_installer_scaffold_contract(
        manifest,
        wix_source_text=wix_source_text,
        wix_include_text=wix_include_text,
        action=action,
        recovery=recovery,
    )

    return NativeInstallerScaffoldVerificationResult(
        scaffold_dir=scaffold_dir,
        manifest_file=manifest_file,
        wix_source_file=wix_source_file,
        wix_include_file=wix_include_file,
        installer_package_file=installer_package_file,
        checksum_matches=True,
        target_arch=target_arch,
        lifecycle_contract_ready=True,
        checked_contract_fields=checked_contract_fields,
        integrity_checked_entries=included_entries,
    )


def _native_installer_recommended_commands() -> dict[str, str]:
    return {
        "build_msi": "wix build ProtoLink.wxs -arch x64 -o ProtoLink.msi",
        "sign_msi": "signtool sign /fd SHA256 /tr <timestamp-url> /td SHA256 ProtoLink.msi",
        "verify_signature": "signtool verify /pa /v ProtoLink.msi",
    }


def _known_native_installer_tool_candidates(tool_key: str) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if tool_key == "wix":
        home = Path.home()
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(variable)
            if root:
                candidates.append(Path(root) / "WiX Toolset v4" / "bin" / "wix.exe")
        candidates.append(home / ".dotnet" / "tools" / "wix.exe")
    elif tool_key == "signtool":
        for variable in ("ProgramFiles(x86)", "ProgramFiles"):
            root = os.environ.get(variable)
            if not root:
                continue
            windows_kits_root = Path(root) / "Windows Kits"
            for major in ("10", "11"):
                bin_dir = windows_kits_root / major / "bin"
                if not bin_dir.exists():
                    continue
                version_dirs = sorted(
                    (path for path in bin_dir.iterdir() if path.is_dir()),
                    key=lambda path: path.name,
                    reverse=True,
                )
                for version_dir in version_dirs:
                    for arch in ("x64", "x86", "arm64"):
                        candidates.append(version_dir / arch / "signtool.exe")
                for arch in ("x64", "x86", "arm64"):
                    candidates.append(bin_dir / arch / "signtool.exe")

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return tuple(unique_candidates)


def _resolve_native_installer_tool_path(spec: _NativeInstallerToolSpec) -> tuple[Path | None, str]:
    override = os.environ.get(spec.env_var)
    if override:
        override_path = Path(override)
        if override_path.exists():
            return override_path, f"env:{spec.env_var}"
        resolved_override = shutil.which(override)
        if resolved_override is not None:
            return Path(resolved_override), f"env:{spec.env_var}"
        return None, f"missing-env:{spec.env_var}"

    for executable_name in spec.executable_names:
        resolved = shutil.which(executable_name)
        if resolved is not None:
            return Path(resolved), "PATH"

    for candidate in _known_native_installer_tool_candidates(spec.tool_key):
        if candidate.exists():
            return candidate, "known-location"

    return None, "not-found"


def _probe_native_installer_tool(
    spec: _NativeInstallerToolSpec,
    *,
    recommended_commands: dict[str, str],
) -> NativeInstallerToolStatus:
    resolved_path, detection_source = _resolve_native_installer_tool_path(spec)
    if resolved_path is None:
        return NativeInstallerToolStatus(
            tool_key=spec.tool_key,
            display_name=spec.display_name,
            executable_name=spec.executable_names[0],
            available=False,
            resolved_path=None,
            detection_source=detection_source,
            probe_command=spec.probe_command,
            probe_output=None,
            error="executable not found",
            install_hint=spec.install_hint,
            recommended_command=recommended_commands[spec.recommended_command_key],
        )

    try:
        completed = subprocess.run(
            [str(resolved_path), *spec.probe_command],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return NativeInstallerToolStatus(
            tool_key=spec.tool_key,
            display_name=spec.display_name,
            executable_name=spec.executable_names[0],
            available=False,
            resolved_path=str(resolved_path),
            detection_source=detection_source,
            probe_command=spec.probe_command,
            probe_output=None,
            error=str(exc),
            install_hint=spec.install_hint,
            recommended_command=recommended_commands[spec.recommended_command_key],
        )

    probe_output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part) or None
    available = completed.returncode in spec.acceptable_exit_codes
    error = None if available else f"probe returned exit code {completed.returncode}"
    return NativeInstallerToolStatus(
        tool_key=spec.tool_key,
        display_name=spec.display_name,
        executable_name=spec.executable_names[0],
        available=available,
        resolved_path=str(resolved_path),
        detection_source=detection_source,
        probe_command=spec.probe_command,
        probe_output=probe_output,
        error=error,
        install_hint=spec.install_hint,
        recommended_command=recommended_commands[spec.recommended_command_key],
    )


def verify_native_installer_toolchain() -> NativeInstallerToolchainVerificationResult:
    recommended_commands = _native_installer_recommended_commands()
    tools = tuple(
        _probe_native_installer_tool(spec, recommended_commands=recommended_commands)
        for spec in _NATIVE_INSTALLER_TOOL_SPECS
    )
    available_tools = tuple(tool.tool_key for tool in tools if tool.available)
    missing_tools = tuple(tool.tool_key for tool in tools if not tool.available)
    return NativeInstallerToolchainVerificationResult(
        target_platform="windows",
        current_platform=sys.platform,
        ready=(not missing_tools),
        available_tools=available_tools,
        missing_tools=missing_tools,
        tools=tools,
        recommended_commands=recommended_commands,
    )


def build_native_installer_msi(
    scaffold_dir: Path,
    *,
    output_file: Path | None = None,
) -> NativeInstallerBuildResult:
    action = "build native installer msi"
    recovery = "Install WiX Toolset v4, verify the native installer scaffold, and retry."
    scaffold = verify_native_installer_scaffold(scaffold_dir)
    toolchain = verify_native_installer_toolchain()
    wix_tool = _require_available_native_installer_tool(toolchain, "wix", action=action)

    scaffold_root = scaffold.scaffold_dir.resolve()
    output_path = (output_file or (scaffold_root / "build" / "ProtoLink.msi")).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = (
        wix_tool.resolved_path,
        "build",
        scaffold.wix_source_file,
        "-arch",
        scaffold.target_arch,
        "-o",
        str(output_path),
    )
    completed = subprocess.run(
        list(command),
        cwd=scaffold_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ProtoLinkUserError(
            f"WiX build failed with exit code {completed.returncode}.",
            action=action,
            recovery=recovery,
        )
    if not output_path.exists():
        raise ProtoLinkUserError(
            f"WiX build completed without producing '{output_path.name}'.",
            action=action,
            recovery=recovery,
        )
    return NativeInstallerBuildResult(
        scaffold_dir=scaffold_root,
        output_file=output_path,
        wix_executable=str(wix_tool.resolved_path),
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def verify_native_installer_signature(installer_file: Path) -> NativeInstallerSignatureVerificationResult:
    action = "verify native installer signature"
    recovery = "Ensure signtool.exe is available and the MSI has been signed, then retry."
    installer_path = installer_file.resolve()
    if not installer_path.exists() or not installer_path.is_file():
        raise ProtoLinkUserError(
            f"Native installer '{installer_path}' was not found.",
            action=action,
            recovery="Build the native installer MSI first and retry.",
        )

    toolchain = verify_native_installer_toolchain()
    signtool = _require_available_native_installer_tool(toolchain, "signtool", action=action)
    command = (
        signtool.resolved_path,
        "verify",
        "/pa",
        "/v",
        str(installer_path),
    )
    completed = subprocess.run(
        list(command),
        cwd=installer_path.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    verified = completed.returncode == 0
    if not verified:
        raise ProtoLinkUserError(
            f"Native installer signature verification failed with exit code {completed.returncode}.",
            action=action,
            recovery=recovery,
        )
    return NativeInstallerSignatureVerificationResult(
        installer_file=installer_path,
        signtool_executable=str(signtool.resolved_path),
        command=command,
        verified=True,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _require_available_native_installer_tool(
    toolchain: NativeInstallerToolchainVerificationResult,
    tool_key: str,
    *,
    action: str,
) -> NativeInstallerToolStatus:
    tool = next((item for item in toolchain.tools if item.tool_key == tool_key), None)
    if tool is None or not tool.available or not tool.resolved_path:
        display_name = tool.display_name if tool is not None else ("WiX Toolset v4 CLI" if tool_key == "wix" else "Windows SignTool")
        install_hint = (
            tool.install_hint
            if tool is not None and tool.install_hint
            else (
                "Install WiX Toolset v4 and ensure `wix.exe` is resolvable."
                if tool_key == "wix"
                else "Install the Windows SDK signing tools and ensure `signtool.exe` is resolvable."
            )
        )
        raise ProtoLinkUserError(
            f"{display_name} is not available in the current environment.",
            action=action,
            recovery=f"{install_hint} Then retry.",
        )
    return tool


def _read_protolink_version(repo_root: Path) -> str:
    pyproject_file = repo_root / "pyproject.toml"
    try:
        text = pyproject_file.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive guard
        raise ProtoLinkUserError(
            f"Could not read '{pyproject_file}': {exc}",
            action="build native installer scaffold",
            recovery="Ensure the repository metadata is available and retry.",
        ) from exc
    match = re.search(r"^version\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.MULTILINE)
    if match is not None:
        return match.group(1)
    raise ProtoLinkUserError(
        f"Could not determine ProtoLink version from '{pyproject_file}'.",
        action="build native installer scaffold",
        recovery="Ensure pyproject.toml contains a project version and retry.",
    )

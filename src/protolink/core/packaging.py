from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import sysconfig
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
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


PORTABLE_MANIFEST_FILE = "portable-manifest.json"
PORTABLE_PACKAGE_FORMAT_VERSION = "protolink-portable-package-v1"
DISTRIBUTION_PACKAGE_FORMAT_VERSION = "protolink-distribution-package-v1"
INSTALLER_STAGING_FORMAT_VERSION = "protolink-installer-staging-v1"
INSTALLER_PACKAGE_FORMAT_VERSION = "protolink-installer-package-v1"
BUNDLED_RUNTIME_DELIVERY_MODE = "bundled_python_runtime"


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


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree(source: Path, destination: Path, *, ignore_site_packages: bool = False) -> None:
    if not source.exists():
        return

    def _ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {"__pycache__"}
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        if ignore_site_packages and "site-packages" in names:
            ignored.add("site-packages")
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
            _copy_tree(source, runtime_dest / directory_name, ignore_site_packages=(directory_name == "Lib"))
            copied.append(str((runtime_dest / directory_name).relative_to(package_dir)))

    runtime_site_packages_dest = package_dir / "sp"
    _copy_tree(site_packages_root, runtime_site_packages_dest)
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
    package_dir = workspace.exports / package_name
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
        Path("pyproject.toml"),
        Path("uv.lock"),
        Path("docs/SMOKE_CHECKLIST.md"),
        Path("docs/RELEASE_CHECKLIST.md"),
    ):
        source = repo_root / relative
        if source.exists():
            copy_file(source, plan.package_dir / relative)

    src_root = repo_root / "src" / "protolink"
    if src_root.exists():
        destination_root = plan.package_dir / "src" / "protolink"
        _copy_tree(src_root, destination_root)
        copied.append(str(destination_root.relative_to(plan.package_dir)))

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
                '$runtime = Join-Path $PSScriptRoot "runtime\\python.exe"',
                'if (-not (Test-Path -LiteralPath $runtime)) { throw "Bundled runtime is missing." }',
                '$env:PYTHONPATH = Join-Path $PSScriptRoot "sp"',
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
                '$runtime = Join-Path $PSScriptRoot "runtime\\pythonw.exe"',
                'if (-not (Test-Path -LiteralPath $runtime)) { throw "Bundled GUI runtime is missing." }',
                '$env:PYTHONPATH = Join-Path $PSScriptRoot "sp"',
                '& $runtime -m protolink',
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
                "set RUNTIME=%~dp0runtime\\pythonw.exe",
                "set PYTHONPATH=%~dp0sp",
                'if not exist "%RUNTIME%" ( echo Bundled GUI runtime is missing. & exit /b 1 )',
                '"%RUNTIME%" -m protolink',
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
    package_dir = workspace.exports / package_name
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
    package_dir = workspace.exports / package_name
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
    package_dir = workspace.exports / package_name
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

import hashlib
import json
import runpy
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.errors import ProtoLinkUserError
from protolink.core.packaging import (
    DISTRIBUTION_PACKAGE_FORMAT_VERSION,
    INSTALLER_PACKAGE_FORMAT_VERSION,
    INSTALLER_STAGING_FORMAT_VERSION,
    NATIVE_INSTALLER_SCAFFOLD_FORMAT_VERSION,
    PORTABLE_MANIFEST_FILE,
    PORTABLE_PACKAGE_FORMAT_VERSION,
    build_native_installer_scaffold_plan,
    build_installer_staging_plan,
    build_installer_package_plan,
    build_distribution_package_plan,
    build_portable_package_plan,
    install_distribution_package,
    install_installer_package,
    install_installer_staging_package,
    install_portable_package,
    materialize_installer_package,
    materialize_installer_staging_package,
    materialize_distribution_package,
    materialize_native_installer_scaffold,
    materialize_portable_package,
    uninstall_portable_package,
    verify_distribution_package,
    verify_native_installer_scaffold,
    verify_native_installer_toolchain,
    verify_portable_package,
    verify_installer_package,
    verify_installer_staging_package,
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_verify_dist_install_namespace() -> dict[str, object]:
    script_file = Path(__file__).resolve().parents[1] / "scripts" / "verify_dist_install.py"
    return runpy.run_path(str(script_file), run_name="verify_dist_install_test_module")


def _write_portable_archive(archive_file: Path) -> None:
    file_payloads = {
        "README.md": b"# ProtoLink\n",
        "INSTALL.ps1": b"echo install\n",
    }
    manifest = {
        "format_version": PORTABLE_PACKAGE_FORMAT_VERSION,
        "package_name": archive_file.stem,
        "release_archive_file": "demo-release.zip",
        "archive_file": archive_file.name,
        "install_scripts": ["INSTALL.ps1"],
        "checksums": {
            name: _sha256_bytes(payload)
            for name, payload in {
                **file_payloads,
                "demo-release.zip": b"release-bytes",
            }.items()
        },
        "included_entries": ["README.md", "INSTALL.ps1", "demo-release.zip"],
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in file_payloads.items():
            archive.writestr(name, payload)
        archive.writestr("demo-release.zip", b"release-bytes")
        archive.writestr(PORTABLE_MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))


def _write_installer_package_archive(archive_file: Path) -> None:
    installer_staging_bytes = b"installer-staging"
    manifest = {
        "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
        "installer_staging_archive_file": "installer-staging.zip",
        "checksum": _sha256_bytes(installer_staging_bytes),
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("installer-package-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("installer-staging.zip", installer_staging_bytes)
        archive.writestr("Install-ProtoLink.ps1", "echo install\n")
        archive.writestr("Install-ProtoLink.bat", "echo install\r\n")


def _create_fake_runtime_bundle(root: Path) -> tuple[Path, Path]:
    runtime_root = root / "runtime-src"
    site_packages = root / "site-packages-src"
    (runtime_root / "DLLs").mkdir(parents=True)
    (runtime_root / "Lib" / "encodings").mkdir(parents=True)
    (runtime_root / "Lib" / "test").mkdir(parents=True)
    (site_packages / "demo_pkg").mkdir(parents=True)
    (site_packages / "demo_pkg-1.0.dist-info").mkdir(parents=True)
    (site_packages / "pip").mkdir(parents=True)
    (site_packages / "pip-24.0.dist-info").mkdir(parents=True)
    (site_packages / "wheel").mkdir(parents=True)
    (site_packages / "wheel-0.45.1.dist-info").mkdir(parents=True)
    (site_packages / "pytest").mkdir(parents=True)
    (site_packages / "_pytest").mkdir(parents=True)
    (site_packages / "iniconfig").mkdir(parents=True)
    (site_packages / "tests").mkdir(parents=True)
    (site_packages / "pytest-8.4.2.dist-info").mkdir(parents=True)
    for file_name in ("python.exe", "pythonw.exe", "python3.dll", "python311.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        (runtime_root / file_name).write_bytes(b"runtime")
    (runtime_root / "DLLs" / "libcrypto-3.dll").write_bytes(b"dll")
    (runtime_root / "Lib" / "encodings" / "__init__.py").write_text("# encodings\n", encoding="utf-8")
    (runtime_root / "Lib" / "test" / "support.py").write_text("# test support\n", encoding="utf-8")
    (site_packages / "demo_pkg" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "demo_pkg-1.0.dist-info" / "METADATA").write_text("Name: demo-pkg\n", encoding="utf-8")
    (site_packages / "demo_pkg-1.0.dist-info" / "RECORD").write_text("", encoding="utf-8")
    (site_packages / "demo_pkg-1.0.dist-info" / "INSTALLER").write_text("uv\n", encoding="utf-8")
    (site_packages / "demo_pkg-1.0.dist-info" / "REQUESTED").write_text("", encoding="utf-8")
    (site_packages / "demo_pkg-1.0.dist-info" / "direct_url.json").write_text("{}", encoding="utf-8")
    (site_packages / "pip" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "pip-24.0.dist-info" / "METADATA").write_text("Name: pip\n", encoding="utf-8")
    (site_packages / "wheel" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "wheel-0.45.1.dist-info" / "METADATA").write_text("Name: wheel\n", encoding="utf-8")
    (site_packages / "pytest" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "_pytest" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "iniconfig" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "tests" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (site_packages / "pytest-8.4.2.dist-info" / "METADATA").write_text("Name: pytest\n", encoding="utf-8")
    (site_packages / "__editable__.protolink-0.1.0.pth").write_text("D:/Project_2026/ProtoLink/src\n", encoding="utf-8")
    (site_packages / "demo.egg-link").write_text("D:/Project_2026/ProtoLink/src\n", encoding="utf-8")
    return runtime_root, site_packages


def test_package_plan_builders_use_short_staging_directories(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    release_archive = context.workspace.exports / "release.zip"
    portable_archive = context.workspace.exports / "portable.zip"
    distribution_archive = context.workspace.exports / "distribution.zip"
    installer_staging_archive = context.workspace.exports / "installer-staging.zip"
    release_archive.write_bytes(b"release")
    portable_archive.write_bytes(b"portable")
    distribution_archive.write_bytes(b"distribution")
    installer_staging_archive.write_bytes(b"installer-staging")

    portable_plan = build_portable_package_plan(
        tmp_path / "repo",
        context.workspace,
        "portable demo",
        release_archive,
        packaged_at=datetime(2026, 4, 9, 8, 0, 0, tzinfo=UTC),
    )
    distribution_plan = build_distribution_package_plan(
        context.workspace,
        "distribution demo",
        portable_archive,
        release_archive,
        packaged_at=datetime(2026, 4, 9, 9, 0, 0, tzinfo=UTC),
    )
    installer_staging_plan = build_installer_staging_plan(
        context.workspace,
        "installer demo",
        distribution_archive,
        packaged_at=datetime(2026, 4, 9, 10, 0, 0, tzinfo=UTC),
    )
    installer_package_plan = build_installer_package_plan(
        context.workspace,
        "installer package demo",
        installer_staging_archive,
        packaged_at=datetime(2026, 4, 9, 11, 0, 0, tzinfo=UTC),
    )

    for plan, expected_prefix in (
        (portable_plan, "portable-"),
        (distribution_plan, "distribution-"),
        (installer_staging_plan, "installer-"),
        (installer_package_plan, "installer-package-"),
    ):
        assert plan.package_dir.parent.name == ".pkg"
        assert plan.package_dir.name.startswith(expected_prefix)
        assert plan.package_name == plan.archive_file.stem


def test_materialize_portable_package_copies_release_archive_and_metadata(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "src" / "protolink").mkdir(parents=True)
    (repo_root / "src" / "protolink" / "__pycache__").mkdir(parents=True)
    (repo_root / "README.md").write_text("# ProtoLink\n", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text("[project]\nname='protolink'\n", encoding="utf-8")
    (repo_root / "uv.lock").write_text("lock", encoding="utf-8")
    (repo_root / "docs" / "SMOKE_CHECKLIST.md").write_text("smoke", encoding="utf-8")
    (repo_root / "docs" / "RELEASE_CHECKLIST.md").write_text("release", encoding="utf-8")
    (repo_root / "src" / "protolink" / "__init__.py").write_text("__version__='0.1.0'\n", encoding="utf-8")
    (repo_root / "src" / "protolink" / "__pycache__" / "demo.cpython-311.pyc").write_bytes(b"compiled")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    release_archive = context.workspace.exports / "demo-release.zip"
    release_archive.write_bytes(b"demo")
    runtime_root, site_packages_root = _create_fake_runtime_bundle(tmp_path)

    plan = build_portable_package_plan(
        repo_root,
        context.workspace,
        "portable demo",
        release_archive,
        packaged_at=datetime(2026, 4, 9, 8, 0, 0, tzinfo=UTC),
    )
    manifest = materialize_portable_package(
        plan,
        repo_root,
        runtime_root=runtime_root,
        site_packages_root=site_packages_root,
    )

    assert plan.archive_file.exists()
    assert manifest["format_version"] == "protolink-portable-package-v1"
    with ZipFile(plan.archive_file) as archive:
        names = set(archive.namelist())
    assert "README.md" in names
    assert "pyproject.toml" not in names
    assert "uv.lock" not in names
    assert "docs/SMOKE_CHECKLIST.md" in names
    assert "docs/RELEASE_CHECKLIST.md" in names
    assert "src/protolink/__init__.py" not in names
    assert "runtime/python.exe" in names
    assert "runtime/pythonw.exe" in names
    assert "runtime/Lib/encodings/__init__.py" in names
    assert "runtime/Lib/test/support.py" not in names
    assert "sp/demo_pkg/__init__.py" in names
    assert "sp/demo_pkg-1.0.dist-info/METADATA" in names
    assert "sp/demo_pkg-1.0.dist-info/RECORD" not in names
    assert "sp/demo_pkg-1.0.dist-info/INSTALLER" not in names
    assert "sp/demo_pkg-1.0.dist-info/REQUESTED" not in names
    assert "sp/demo_pkg-1.0.dist-info/direct_url.json" not in names
    assert "sp/protolink/__init__.py" in names
    assert "sp/pip/__init__.py" not in names
    assert "sp/pip-24.0.dist-info/METADATA" not in names
    assert "sp/wheel/__init__.py" not in names
    assert "sp/wheel-0.45.1.dist-info/METADATA" not in names
    assert "sp/pytest/__init__.py" not in names
    assert "sp/_pytest/__init__.py" not in names
    assert "sp/iniconfig/__init__.py" not in names
    assert "sp/tests/__init__.py" not in names
    assert "sp/pytest-8.4.2.dist-info/METADATA" not in names
    assert "sp/__editable__.protolink-0.1.0.pth" not in names
    assert "sp/demo.egg-link" not in names
    assert "INSTALL.ps1" in names
    assert "Launch-ProtoLink.ps1" in names
    assert "Launch-ProtoLink.bat" in names
    assert "demo-release.zip" in names
    assert PORTABLE_MANIFEST_FILE in names
    assert "src/protolink/__pycache__/demo.cpython-311.pyc" not in names
    assert "src/protolink" not in manifest["included_entries"]
    install_script = (plan.package_dir / "INSTALL.ps1").read_text(encoding="utf-8")
    launch_ps1 = (plan.package_dir / "Launch-ProtoLink.ps1").read_text(encoding="utf-8")
    launch_bat = (plan.package_dir / "Launch-ProtoLink.bat").read_text(encoding="utf-8")
    assert "PROTOLINK_BASE_DIR" in install_script
    assert "ProtoLinkArgs" in launch_ps1
    assert "python.exe" in launch_ps1
    assert "pythonw.exe" in launch_ps1
    assert "@ProtoLinkArgs" in launch_ps1
    assert "PROTOLINK_BASE_DIR" in launch_ps1
    assert 'if not "%~1"==""' in launch_bat
    assert "python.exe" in launch_bat
    assert "pythonw.exe" in launch_bat
    assert "%*" in launch_bat
    assert "PROTOLINK_BASE_DIR" in launch_bat
    assert manifest["delivery_mode"] == "bundled_python_runtime"
    assert manifest["runtime_prerequisites"] == []


def test_install_portable_package_extracts_archive(tmp_path: Path) -> None:
    archive_file = tmp_path / "portable.zip"
    _write_portable_archive(archive_file)

    target_dir = tmp_path / "installed"
    result = install_portable_package(archive_file, target_dir)

    assert result.archive_file == archive_file
    assert result.target_dir == target_dir
    assert (target_dir / "README.md").exists()
    assert (target_dir / "INSTALL.ps1").exists()
    assert result.receipt_file.exists()


def test_install_portable_package_rejects_path_traversal_archive(tmp_path: Path) -> None:
    archive_file = tmp_path / "portable.zip"
    manifest = {
        "format_version": PORTABLE_PACKAGE_FORMAT_VERSION,
        "package_name": archive_file.stem,
        "release_archive_file": "demo-release.zip",
        "archive_file": archive_file.name,
        "install_scripts": ["INSTALL.ps1"],
        "checksums": {
            "../escape.txt": _sha256_bytes(b"escape"),
            "demo-release.zip": _sha256_bytes(b"release-bytes"),
        },
        "included_entries": ["../escape.txt", "demo-release.zip"],
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../escape.txt", "escape")
        archive.writestr("demo-release.zip", b"release-bytes")
        archive.writestr(PORTABLE_MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))

    target_dir = tmp_path / "installed"
    try:
        install_portable_package(archive_file, target_dir)
    except ProtoLinkUserError as exc:
        assert "path traversal" in str(exc)
    else:
        raise AssertionError("Expected path traversal archive to be rejected.")

    assert not (tmp_path / "escape.txt").exists()


def test_uninstall_portable_package_removes_installed_files_from_receipt(tmp_path: Path) -> None:
    archive_file = tmp_path / "portable.zip"
    _write_portable_archive(archive_file)

    target_dir = tmp_path / "installed"
    install_portable_package(archive_file, target_dir)
    result = uninstall_portable_package(target_dir)

    assert result.removed_receipt is True
    assert set(result.removed_entries) == {"README.md", "INSTALL.ps1", "demo-release.zip", PORTABLE_MANIFEST_FILE}
    assert not (target_dir / "README.md").exists()
    assert not (target_dir / "INSTALL.ps1").exists()


def test_uninstall_portable_package_rejects_receipt_path_traversal(tmp_path: Path) -> None:
    target_dir = tmp_path / "installed"
    target_dir.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("do-not-delete", encoding="utf-8")
    receipt_file = target_dir / "install-receipt.json"
    receipt_file.write_text(
        json.dumps(
            {
                "format_version": "protolink-install-receipt-v1",
                "archive_file": "portable.zip",
                "extracted_entries": ["..\\victim.txt"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        uninstall_portable_package(target_dir)
    except ProtoLinkUserError as exc:
        assert "path traversal" in str(exc)
    else:
        raise AssertionError("Expected tampered install receipt to be rejected.")

    assert victim.exists()
    assert receipt_file.exists()


def test_materialize_distribution_package_creates_manifest_and_archive(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "README.md").write_text("# ProtoLink\n", encoding="utf-8")
    (repo_root / "docs" / "SMOKE_CHECKLIST.md").write_text("smoke", encoding="utf-8")
    (repo_root / "docs" / "RELEASE_CHECKLIST.md").write_text("release", encoding="utf-8")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    release_archive = context.workspace.exports / "demo-release.zip"
    portable_archive = context.workspace.exports / "demo-portable.zip"
    release_archive.write_bytes(b"release")
    portable_archive.write_bytes(b"portable")

    plan = build_distribution_package_plan(
        context.workspace,
        "distribution demo",
        portable_archive,
        release_archive,
        packaged_at=datetime(2026, 4, 9, 9, 0, 0, tzinfo=UTC),
    )
    manifest = materialize_distribution_package(plan, repo_root)

    assert plan.manifest_file.exists()
    assert plan.archive_file.exists()
    assert manifest["format_version"] == "protolink-distribution-package-v1"
    assert manifest["portable_archive_file"] == "demo-portable.zip"
    assert manifest["release_archive_file"] == "demo-release.zip"


def test_install_distribution_package_extracts_and_installs_portable_archive(tmp_path: Path) -> None:
    staging_source = tmp_path / "dist-src"
    staging_source.mkdir(parents=True)
    portable_archive = staging_source / "portable.zip"
    release_archive = staging_source / "release.zip"
    release_bytes = b"release-archive"
    _write_portable_archive(portable_archive)
    release_archive.write_bytes(release_bytes)
    portable_checksum = _sha256_bytes(portable_archive.read_bytes())
    manifest_file = staging_source / "distribution-manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": portable_archive.name,
                "release_archive_file": release_archive.name,
                "checksums": {
                    portable_archive.name: portable_checksum,
                    release_archive.name: _sha256_bytes(release_bytes),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    distribution_archive = tmp_path / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in staging_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staging"
    install_dir = tmp_path / "installed"
    result = install_distribution_package(distribution_archive, staging_dir, install_dir)

    assert result.archive_file == distribution_archive
    assert result.distribution_manifest_file.exists()
    assert (install_dir / "README.md").exists()
    assert (install_dir / "INSTALL.ps1").exists()
    assert result.portable_install.receipt_file.exists()


def test_install_distribution_package_rejects_checksum_mismatch(tmp_path: Path) -> None:
    staging_source = tmp_path / "dist-src"
    staging_source.mkdir(parents=True)
    portable_archive = staging_source / "portable.zip"
    release_archive = staging_source / "release.zip"
    portable_archive.write_bytes(b"portable-archive")
    release_archive.write_bytes(b"release-archive")
    (staging_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": portable_archive.name,
                "release_archive_file": release_archive.name,
                "checksums": {
                    portable_archive.name: _sha256_bytes(b"tampered"),
                    release_archive.name: _sha256_bytes(b"release-archive"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    distribution_archive = tmp_path / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in staging_source.iterdir():
            archive.write(path, arcname=path.name)

    try:
        install_distribution_package(distribution_archive, tmp_path / "staging", tmp_path / "installed")
    except Exception as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("Expected checksum validation to reject the distribution archive.")


def test_install_distribution_package_rejects_outer_archive_path_traversal(tmp_path: Path) -> None:
    distribution_archive = tmp_path / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../escape.txt", "escape")
        archive.writestr(
            "distribution-manifest.json",
            json.dumps(
                {
                    "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                    "portable_archive_file": "portable.zip",
                    "release_archive_file": "release.zip",
                    "checksums": {
                        "portable.zip": _sha256_bytes(b"portable"),
                        "release.zip": _sha256_bytes(b"release"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    try:
        install_distribution_package(distribution_archive, tmp_path / "staging", tmp_path / "installed")
    except ProtoLinkUserError as exc:
        assert "path traversal" in str(exc)
    else:
        raise AssertionError("Expected unsafe outer distribution archive to be rejected.")

    assert not (tmp_path / "escape.txt").exists()


def test_verify_distribution_package_checks_manifest_and_checksums(tmp_path: Path) -> None:
    archive_file = tmp_path / "distribution.zip"
    portable_bytes = b"portable-archive"
    release_bytes = b"release-archive"
    checksum_map = {
        "portable.zip": _sha256_bytes(portable_bytes),
        "release.zip": _sha256_bytes(release_bytes),
    }
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "distribution-manifest.json",
            json.dumps(
                {
                    "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                    "portable_archive_file": "portable.zip",
                    "release_archive_file": "release.zip",
                    "checksums": checksum_map,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("portable.zip", portable_bytes)
        archive.writestr("release.zip", release_bytes)

    result = verify_distribution_package(archive_file)

    assert result.checksum_matches is True
    assert result.distribution_manifest_file == "distribution-manifest.json"
    assert result.portable_archive_file == "portable.zip"
    assert result.release_archive_file == "release.zip"


def test_materialize_installer_staging_package_creates_manifest_and_archive(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "README.md").write_text("# ProtoLink\n", encoding="utf-8")
    (repo_root / "docs" / "SMOKE_CHECKLIST.md").write_text("smoke", encoding="utf-8")
    (repo_root / "docs" / "RELEASE_CHECKLIST.md").write_text("release", encoding="utf-8")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    distribution_archive = context.workspace.exports / "distribution.zip"
    distribution_archive.write_bytes(b"distribution")

    plan = build_installer_staging_plan(
        context.workspace,
        "installer demo",
        distribution_archive,
        packaged_at=datetime(2026, 4, 9, 10, 0, 0, tzinfo=UTC),
    )
    manifest = materialize_installer_staging_package(plan, repo_root)

    assert plan.manifest_file.exists()
    assert plan.archive_file.exists()
    assert manifest["format_version"] == "protolink-installer-staging-v1"
    assert manifest["distribution_archive_file"] == "distribution.zip"


def test_materialize_installer_package_creates_manifest_and_archive(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "README.md").write_text("# ProtoLink\n", encoding="utf-8")
    (repo_root / "docs" / "SMOKE_CHECKLIST.md").write_text("smoke", encoding="utf-8")
    (repo_root / "docs" / "RELEASE_CHECKLIST.md").write_text("release", encoding="utf-8")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    installer_staging_archive = context.workspace.exports / "installer-staging.zip"
    installer_staging_archive.write_bytes(b"installer-staging")

    plan = build_installer_package_plan(
        context.workspace,
        "installer package demo",
        installer_staging_archive,
        packaged_at=datetime(2026, 4, 9, 11, 0, 0, tzinfo=UTC),
    )
    manifest = materialize_installer_package(plan, repo_root)

    assert plan.manifest_file.exists()
    assert plan.archive_file.exists()
    assert manifest["format_version"] == "protolink-installer-package-v1"
    assert manifest["installer_staging_archive_file"] == "installer-staging.zip"


def test_install_installer_package_extracts_staging_distribution_and_portable(tmp_path: Path) -> None:
    installer_source = tmp_path / "installer-package-src"
    installer_source.mkdir(parents=True)

    portable_archive = installer_source / "portable.zip"
    _write_portable_archive(portable_archive)
    portable_checksum = _sha256_bytes(portable_archive.read_bytes())

    distribution_source = tmp_path / "distribution-src"
    distribution_source.mkdir(parents=True)
    release_archive = distribution_source / "release.zip"
    release_bytes = b"release-archive"
    release_archive.write_bytes(release_bytes)
    (distribution_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": portable_checksum,
                    "release.zip": _sha256_bytes(release_bytes),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(portable_archive, distribution_source / "portable.zip")
    distribution_archive = installer_source / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in distribution_source.iterdir():
            archive.write(path, arcname=path.name)
    distribution_bytes = distribution_archive.read_bytes()

    installer_staging_source = tmp_path / "installer-staging-src"
    installer_staging_source.mkdir(parents=True)
    (installer_staging_source / "installer-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                "distribution_archive_file": "distribution.zip",
                "checksum": _sha256_bytes(distribution_bytes),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(distribution_archive, installer_staging_source / "distribution.zip")
    installer_staging_archive = installer_source / "installer-staging.zip"
    with ZipFile(installer_staging_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_staging_source.iterdir():
            archive.write(path, arcname=path.name)
    installer_staging_bytes = installer_staging_archive.read_bytes()

    (installer_source / "installer-package-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                "installer_staging_archive_file": "installer-staging.zip",
                "checksum": _sha256_bytes(installer_staging_bytes),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    installer_archive = tmp_path / "installer-package.zip"
    with ZipFile(installer_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in installer_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    result = install_installer_package(installer_archive, staging_dir, install_dir)

    assert result.installer_package_manifest_file.exists()
    assert (install_dir / "README.md").exists()
    assert (install_dir / "INSTALL.ps1").exists()


def test_install_installer_staging_package_extracts_distribution_and_portable(tmp_path: Path) -> None:
    staging_source = tmp_path / "installer-src"
    staging_source.mkdir(parents=True)

    portable_archive = staging_source / "portable.zip"
    _write_portable_archive(portable_archive)
    portable_checksum = _sha256_bytes(portable_archive.read_bytes())

    distribution_source = tmp_path / "distribution-src"
    distribution_source.mkdir(parents=True)
    release_archive = distribution_source / "release.zip"
    release_bytes = b"release-archive"
    release_archive.write_bytes(release_bytes)
    (distribution_source / "distribution-manifest.json").write_text(
        json.dumps(
            {
                "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                "portable_archive_file": "portable.zip",
                "release_archive_file": "release.zip",
                "checksums": {
                    "portable.zip": portable_checksum,
                    "release.zip": _sha256_bytes(release_bytes),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(portable_archive, distribution_source / "portable.zip")
    distribution_archive = staging_source / "distribution.zip"
    with ZipFile(distribution_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in distribution_source.iterdir():
            archive.write(path, arcname=path.name)
    distribution_bytes = distribution_archive.read_bytes()

    (staging_source / "installer-manifest.json").write_text(
        json.dumps(
            {
                "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                "distribution_archive_file": "distribution.zip",
                "checksum": _sha256_bytes(distribution_bytes),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    installer_archive = tmp_path / "installer.zip"
    with ZipFile(installer_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in staging_source.iterdir():
            archive.write(path, arcname=path.name)

    staging_dir = tmp_path / "staged"
    install_dir = tmp_path / "installed"
    result = install_installer_staging_package(installer_archive, staging_dir, install_dir)

    assert result.installer_manifest_file.exists()
    assert (install_dir / "README.md").exists()
    assert (install_dir / "INSTALL.ps1").exists()
    assert result.distribution_install.portable_install.receipt_file.exists()


def test_verify_installer_staging_package_checks_checksum_and_scripts(tmp_path: Path) -> None:
    archive_file = tmp_path / "installer.zip"
    distribution_bytes = b"distribution"
    checksum = __import__("hashlib").sha256(distribution_bytes).hexdigest()
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-manifest.json",
            json.dumps(
                {
                    "format_version": INSTALLER_STAGING_FORMAT_VERSION,
                    "distribution_archive_file": "distribution.zip",
                    "checksum": checksum,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("distribution.zip", distribution_bytes)
        archive.writestr("Install-Distribution.ps1", "echo install\n")
        archive.writestr("Install-Distribution.bat", "echo install\r\n")

    result = verify_installer_staging_package(archive_file)

    assert result.checksum_matches is True
    assert set(result.install_scripts_present) == {"Install-Distribution.ps1", "Install-Distribution.bat"}


def test_verify_installer_package_checks_checksum_and_scripts(tmp_path: Path) -> None:
    archive_file = tmp_path / "installer-package.zip"
    installer_staging_bytes = b"installer-staging"
    checksum = __import__("hashlib").sha256(installer_staging_bytes).hexdigest()
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-package-manifest.json",
            json.dumps(
                {
                    "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                    "installer_staging_archive_file": "installer-staging.zip",
                    "checksum": checksum,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("installer-staging.zip", installer_staging_bytes)
        archive.writestr("Install-ProtoLink.ps1", "echo install\n")
        archive.writestr("Install-ProtoLink.bat", "echo install\r\n")

    result = verify_installer_package(archive_file)

    assert result.checksum_matches is True
    assert set(result.install_scripts_present) == {"Install-ProtoLink.ps1", "Install-ProtoLink.bat"}


def test_verify_portable_package_checks_manifest_and_checksums(tmp_path: Path) -> None:
    archive_file = tmp_path / "portable.zip"
    _write_portable_archive(archive_file)

    result = verify_portable_package(archive_file)

    assert result.checksum_matches is True
    assert result.portable_manifest_file == PORTABLE_MANIFEST_FILE
    assert result.release_archive_file == "demo-release.zip"
    assert set(result.install_scripts_present) == {"INSTALL.ps1"}


def test_verify_portable_package_rejects_invalid_manifest_format_version(tmp_path: Path) -> None:
    archive_file = tmp_path / "portable.zip"
    release_bytes = b"release"
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            PORTABLE_MANIFEST_FILE,
            json.dumps(
                {
                    "format_version": "legacy-portable-v0",
                    "release_archive_file": "release.zip",
                    "checksums": {"release.zip": _sha256_bytes(release_bytes)},
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("release.zip", release_bytes)

    try:
        verify_portable_package(archive_file)
    except ProtoLinkUserError as exc:
        assert "format_version" in str(exc)
    else:
        raise AssertionError("Expected invalid portable manifest format_version to be rejected.")


def test_verify_distribution_package_rejects_invalid_manifest_field_types(tmp_path: Path) -> None:
    archive_file = tmp_path / "distribution.zip"
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "distribution-manifest.json",
            json.dumps(
                {
                    "format_version": DISTRIBUTION_PACKAGE_FORMAT_VERSION,
                    "portable_archive_file": ["portable.zip"],
                    "release_archive_file": "release.zip",
                    "checksums": {"release.zip": _sha256_bytes(b"release")},
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    try:
        verify_distribution_package(archive_file)
    except ProtoLinkUserError as exc:
        assert "portable_archive_file" in str(exc)
    else:
        raise AssertionError("Expected invalid distribution manifest field type to be rejected.")


def test_verify_installer_staging_package_rejects_missing_format_version(tmp_path: Path) -> None:
    archive_file = tmp_path / "installer.zip"
    distribution_bytes = b"distribution"
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-manifest.json",
            json.dumps(
                {
                    "distribution_archive_file": "distribution.zip",
                    "checksum": _sha256_bytes(distribution_bytes),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("distribution.zip", distribution_bytes)

    try:
        verify_installer_staging_package(archive_file)
    except ProtoLinkUserError as exc:
        assert "format_version" in str(exc)
    else:
        raise AssertionError("Expected missing installer-staging format_version to be rejected.")


def test_verify_installer_package_rejects_non_string_checksum(tmp_path: Path) -> None:
    archive_file = tmp_path / "installer-package.zip"
    installer_staging_bytes = b"installer-staging"
    with ZipFile(archive_file, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "installer-package-manifest.json",
            json.dumps(
                {
                    "format_version": INSTALLER_PACKAGE_FORMAT_VERSION,
                    "installer_staging_archive_file": "installer-staging.zip",
                    "checksum": ["not-a-string"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("installer-staging.zip", installer_staging_bytes)

    try:
        verify_installer_package(archive_file)
    except ProtoLinkUserError as exc:
        assert "checksum" in str(exc)
    else:
        raise AssertionError("Expected invalid installer package checksum type to be rejected.")


def test_verify_dist_install_selects_latest_complete_version_when_dist_contains_multiple_versions(
    tmp_path: Path,
) -> None:
    namespace = _load_verify_dist_install_namespace()
    select_artifact_pair = namespace["_select_artifact_pair"]

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    for name in (
        "protolink-0.1.0-py3-none-any.whl",
        "protolink-0.1.0.tar.gz",
        "protolink-0.2.0-py3-none-any.whl",
        "protolink-0.2.0.tar.gz",
    ):
        (dist_dir / name).write_bytes(name.encode("utf-8"))

    selection = select_artifact_pair(dist_dir)

    assert selection.version == "0.2.0"
    assert selection.wheel_file.name == "protolink-0.2.0-py3-none-any.whl"
    assert selection.sdist_file.name == "protolink-0.2.0.tar.gz"
    assert selection.wheel_versions == ("0.1.0", "0.2.0")
    assert selection.sdist_versions == ("0.1.0", "0.2.0")


def test_verify_dist_install_can_pin_an_explicit_artifact_version(tmp_path: Path) -> None:
    namespace = _load_verify_dist_install_namespace()
    select_artifact_pair = namespace["_select_artifact_pair"]

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    for name in (
        "protolink-0.1.0-py3-none-any.whl",
        "protolink-0.1.0.tar.gz",
        "protolink-0.2.0-py3-none-any.whl",
        "protolink-0.2.0.tar.gz",
    ):
        (dist_dir / name).write_bytes(name.encode("utf-8"))

    selection = select_artifact_pair(dist_dir, requested_version="0.1.0")

    assert selection.version == "0.1.0"
    assert selection.wheel_file.name == "protolink-0.1.0-py3-none-any.whl"
    assert selection.sdist_file.name == "protolink-0.1.0.tar.gz"


def test_verify_dist_install_rejects_mismatched_latest_artifacts_with_guidance(tmp_path: Path) -> None:
    namespace = _load_verify_dist_install_namespace()
    select_artifact_pair = namespace["_select_artifact_pair"]
    verification_error = namespace["VerificationError"]

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    for name in (
        "protolink-0.2.0-py3-none-any.whl",
        "protolink-0.2.0.tar.gz",
        "protolink-0.3.0-py3-none-any.whl",
    ):
        (dist_dir / name).write_bytes(name.encode("utf-8"))

    try:
        select_artifact_pair(dist_dir)
    except verification_error as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected mismatched latest dist artifacts to be rejected.")

    assert "mismatched latest ProtoLink artifacts" in message
    assert "latest wheel version: 0.3.0" in message
    assert "latest sdist version: 0.2.0" in message
    assert "--artifact-version 0.2.0" in message


def test_materialize_native_installer_scaffold_creates_wix_sources_and_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "protolink").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='protolink'\nversion='9.9.9'\n", encoding="utf-8")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    installer_archive = context.workspace.exports / "installer-package.zip"
    _write_installer_package_archive(installer_archive)

    plan = build_native_installer_scaffold_plan(
        context.workspace,
        "native installer demo",
        installer_archive,
        packaged_at=datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC),
    )
    manifest = materialize_native_installer_scaffold(plan, repo_root)

    assert plan.manifest_file.exists()
    assert plan.wix_source_file.exists()
    assert plan.wix_include_file.exists()
    assert plan.installer_package_file.exists()
    assert manifest["format_version"] == NATIVE_INSTALLER_SCAFFOLD_FORMAT_VERSION
    assert manifest["application_version"] == "9.9.9"
    assert manifest["wix_product_version"] == "9.9.9"
    assert manifest["installer_package_file"] == "payload/installer-package.zip"
    assert manifest["wix_source_file"] == "ProtoLink.wxs"
    assert manifest["wix_include_file"] == "ProtoLink.Generated.wxi"
    assert "wix build ProtoLink.wxs -arch x64 -o ProtoLink.msi" in manifest["recommended_commands"]
    assert "ProtoLink.Generated.wxi" in plan.wix_source_file.read_text(encoding="utf-8")
    include_text = plan.wix_include_file.read_text(encoding="utf-8")
    assert "payload\\installer-package.zip" in include_text
    assert "installer-package.zip" in include_text


def test_verify_native_installer_scaffold_checks_required_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "protolink").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='protolink'\nversion='1.2.3'\n", encoding="utf-8")

    context = bootstrap_app_context(tmp_path / "workspace-root", persist_settings=False)
    installer_archive = context.workspace.exports / "installer-package.zip"
    _write_installer_package_archive(installer_archive)
    plan = build_native_installer_scaffold_plan(context.workspace, "native installer demo", installer_archive)
    materialize_native_installer_scaffold(plan, repo_root)

    result = verify_native_installer_scaffold(plan.package_dir)

    assert result.scaffold_dir == plan.package_dir.resolve()
    assert result.manifest_file == plan.manifest_file
    assert result.wix_source_file == "ProtoLink.wxs"
    assert result.wix_include_file == "ProtoLink.Generated.wxi"
    assert result.installer_package_file == "payload/installer-package.zip"
    assert result.checksum_matches is True


def test_verify_native_installer_toolchain_reports_missing_tools(monkeypatch) -> None:
    monkeypatch.delenv("PROTOLINK_WIX", raising=False)
    monkeypatch.delenv("PROTOLINK_SIGNTOOL", raising=False)
    monkeypatch.setattr("protolink.core.packaging.shutil.which", lambda name: None)
    monkeypatch.setattr("protolink.core.packaging._known_native_installer_tool_candidates", lambda tool_key: ())

    result = verify_native_installer_toolchain()
    tools = {tool.tool_key: tool for tool in result.tools}

    assert result.ready is False
    assert result.available_tools == ()
    assert result.missing_tools == ("wix", "signtool")
    assert tools["wix"].available is False
    assert tools["wix"].error == "executable not found"
    assert tools["wix"].recommended_command == result.recommended_commands["build_msi"]
    assert tools["signtool"].available is False
    assert tools["signtool"].install_hint.startswith("Install the Windows SDK signing tools")


def test_verify_native_installer_toolchain_reports_available_tools(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PROTOLINK_WIX", raising=False)
    monkeypatch.delenv("PROTOLINK_SIGNTOOL", raising=False)
    wix_executable = tmp_path / "wix.exe"
    signtool_executable = tmp_path / "signtool.exe"
    wix_executable.write_text("stub", encoding="utf-8")
    signtool_executable.write_text("stub", encoding="utf-8")

    executable_map = {
        "wix.exe": str(wix_executable),
        "wix": str(wix_executable),
        "signtool.exe": str(signtool_executable),
        "signtool": str(signtool_executable),
    }
    monkeypatch.setattr("protolink.core.packaging.shutil.which", lambda name: executable_map.get(name))
    monkeypatch.setattr("protolink.core.packaging._known_native_installer_tool_candidates", lambda tool_key: ())

    def _fake_run(command, capture_output, text, timeout, check):
        executable_name = Path(command[0]).name.lower()
        if executable_name == "wix.exe":
            return subprocess.CompletedProcess(command, 0, stdout="4.0.5\n", stderr="")
        if executable_name == "signtool.exe":
            return subprocess.CompletedProcess(command, 0, stdout="Microsoft (R) SignTool\n", stderr="")
        raise AssertionError(f"unexpected probe command: {command}")

    monkeypatch.setattr("protolink.core.packaging.subprocess.run", _fake_run)

    result = verify_native_installer_toolchain()
    tools = {tool.tool_key: tool for tool in result.tools}

    assert result.ready is True
    assert result.available_tools == ("wix", "signtool")
    assert result.missing_tools == ()
    assert tools["wix"].resolved_path == str(wix_executable)
    assert tools["wix"].probe_output == "4.0.5"
    assert tools["wix"].detection_source == "PATH"
    assert tools["signtool"].resolved_path == str(signtool_executable)
    assert tools["signtool"].probe_command == ("/?",)
    assert tools["signtool"].probe_output == "Microsoft (R) SignTool"


def test_verify_native_installer_toolchain_reports_detected_binaries(monkeypatch) -> None:
    def fake_which(name: str) -> str | None:
        mapping = {
            "wix": r"C:\Tools\wix.exe",
            "wix.exe": r"C:\Tools\wix.exe",
            "signtool": r"C:\SDK\signtool.exe",
            "signtool.exe": r"C:\SDK\signtool.exe",
        }
        return mapping.get(name)

    monkeypatch.setattr("protolink.core.packaging.shutil.which", fake_which)
    monkeypatch.setattr("protolink.core.packaging._known_native_installer_tool_candidates", lambda tool_key: ())

    def _fake_run(command, capture_output, text, timeout, check):
        executable_name = Path(command[0]).name.lower()
        if executable_name == "wix.exe":
            return subprocess.CompletedProcess(command, 0, stdout="4.0.5\n", stderr="")
        if executable_name == "signtool.exe":
            return subprocess.CompletedProcess(command, 0, stdout="Microsoft (R) SignTool\n", stderr="")
        raise AssertionError(f"unexpected probe command: {command}")

    monkeypatch.setattr("protolink.core.packaging.subprocess.run", _fake_run)

    result = verify_native_installer_toolchain()

    assert result.ready is True
    assert result.target_platform == "windows"
    assert set(result.available_tools) == {"wix", "signtool"}
    assert result.missing_tools == ()
    tool_map = {tool.tool_key: tool for tool in result.tools}
    assert tool_map["wix"].resolved_path == r"C:\Tools\wix.exe"
    assert tool_map["signtool"].resolved_path == r"C:\SDK\signtool.exe"
    assert "wix build" in result.recommended_commands["build_msi"]

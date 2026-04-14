from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST_DIR = ROOT / "dist"
PROTOLINK_BASE_DIR_ENV = "PROTOLINK_BASE_DIR"
PROJECT_DISTRIBUTION = "protolink"
WHEEL_SUFFIX = ".whl"
SDIST_SUFFIX = ".tar.gz"

try:
    from packaging.version import InvalidVersion, Version
except Exception:  # pragma: no cover - fallback only used when packaging is unavailable.
    InvalidVersion = ValueError
    Version = None


class VerificationError(RuntimeError):
    """Raised when dist installation verification fails."""


@dataclass(frozen=True)
class ArtifactCandidate:
    version: str
    path: Path
    modified_at: float


@dataclass(frozen=True)
class ArtifactSelection:
    version: str
    wheel_file: Path
    sdist_file: Path
    wheel_versions: tuple[str, ...]
    sdist_versions: tuple[str, ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 ProtoLink 的 wheel 和 sdist 能否从 dist/ 全新安装，并在隔离环境中运行无界面摘要。"
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="包含已构建分发产物的目录，默认为 ./dist。",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="保留临时虚拟环境和工作目录。",
    )
    parser.add_argument(
        "--artifact-version",
        help="显式指定要验证的产物版本；默认自动选择 dist/ 中最新且 wheel/sdist 成对存在的版本。",
    )
    return parser


def _print_step(kind: str, message: str) -> None:
    print(f"[{kind}] {message}", file=sys.stderr, flush=True)


def _sanitized_environment(*, isolated_base_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "__PYVENV_LAUNCHER__",
        PROTOLINK_BASE_DIR_ENV,
    ):
        env.pop(variable, None)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    if isolated_base_dir is not None:
        env[PROTOLINK_BASE_DIR_ENV] = str(isolated_base_dir)
    return env


def _run_command(
    command: list[str],
    *,
    label: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"{label} failed.\n"
            f"cwd: {cwd}\n"
            f"command: {' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
    )
    return completed


def _version_sort_key(version_text: str) -> tuple[object, ...]:
    if Version is not None:
        try:
            return (0, Version(version_text))
        except InvalidVersion:
            pass
    parts: list[tuple[int, object]] = []
    for token in re.split(r"(\d+)", version_text):
        if not token:
            continue
        parts.append((0, int(token)) if token.isdigit() else (1, token.lower()))
    return (1, tuple(parts), version_text.lower())


def _parse_artifact_candidate(path: Path, *, kind: str) -> ArtifactCandidate | None:
    name = path.name
    prefix = f"{PROJECT_DISTRIBUTION}-"
    if not name.startswith(prefix):
        return None

    if kind == "wheel":
        if not name.endswith(WHEEL_SUFFIX):
            return None
        parts = name[: -len(WHEEL_SUFFIX)].split("-")
        if len(parts) < 5:
            return None
        version = parts[1].strip()
    elif kind == "sdist":
        if not name.endswith(SDIST_SUFFIX):
            return None
        version = name[len(prefix) : -len(SDIST_SUFFIX)].strip()
    else:  # pragma: no cover - internal misuse guard.
        raise VerificationError(f"Unsupported artifact kind: {kind}")

    if not version:
        return None
    return ArtifactCandidate(version=version, path=path.resolve(), modified_at=path.stat().st_mtime)


def _discover_artifacts(dist_dir: Path, *, kind: str) -> dict[str, list[ArtifactCandidate]]:
    pattern = f"*{WHEEL_SUFFIX}" if kind == "wheel" else f"*{SDIST_SUFFIX}"
    discovered: dict[str, list[ArtifactCandidate]] = {}
    for path in dist_dir.glob(pattern):
        if not path.is_file():
            continue
        candidate = _parse_artifact_candidate(path, kind=kind)
        if candidate is None:
            continue
        discovered.setdefault(candidate.version, []).append(candidate)

    if not discovered:
        raise VerificationError(
            f"No ProtoLink {kind} artifact matched '{PROJECT_DISTRIBUTION}-*{pattern[1:]}' under {dist_dir}. "
            "Run `uv build` first."
        )
    return discovered


def _select_candidate(candidates_by_version: dict[str, list[ArtifactCandidate]], version: str, label: str) -> Path:
    candidates = sorted(
        candidates_by_version[version],
        key=lambda candidate: (candidate.modified_at, str(candidate.path).lower()),
    )
    selected = candidates[-1]
    if len(candidates) > 1:
        ignored = ", ".join(candidate.path.name for candidate in candidates[:-1])
        _print_step(
            "DIST",
            f"{label} version {version} has {len(candidates)} candidates; using newest {selected.path.name}, ignored: {ignored}",
        )
    return selected.path


def _format_versions(versions: tuple[str, ...]) -> str:
    return ", ".join(versions) if versions else "(none)"


def _select_artifact_pair(dist_dir: Path, *, requested_version: str | None = None) -> ArtifactSelection:
    wheel_candidates = _discover_artifacts(dist_dir, kind="wheel")
    sdist_candidates = _discover_artifacts(dist_dir, kind="sdist")
    wheel_versions = tuple(sorted(wheel_candidates, key=_version_sort_key))
    sdist_versions = tuple(sorted(sdist_candidates, key=_version_sort_key))
    common_versions = tuple(sorted(set(wheel_versions).intersection(sdist_versions), key=_version_sort_key))

    if requested_version is not None:
        requested_version = requested_version.strip()
        if not requested_version:
            raise VerificationError("Requested artifact version cannot be empty.")
        if requested_version not in wheel_candidates or requested_version not in sdist_candidates:
            raise VerificationError(
                "Requested artifact version is not a complete wheel/sdist pair.\n"
                f"requested_version: {requested_version}\n"
                f"available wheel versions: {_format_versions(wheel_versions)}\n"
                f"available sdist versions: {_format_versions(sdist_versions)}\n"
                "Either pass a complete version or clean dist/ and rebuild."
            )
        selected_version = requested_version
        _print_step("DIST", f"using requested ProtoLink dist version {selected_version}")
    else:
        if not common_versions:
            raise VerificationError(
                "dist/ does not contain a complete ProtoLink wheel/sdist pair.\n"
                f"available wheel versions: {_format_versions(wheel_versions)}\n"
                f"available sdist versions: {_format_versions(sdist_versions)}\n"
                "Clean dist/ and rerun `uv build`, or pass --artifact-version once a complete pair exists."
            )

        latest_wheel_version = wheel_versions[-1]
        latest_sdist_version = sdist_versions[-1]
        if latest_wheel_version != latest_sdist_version:
            suggested_common = common_versions[-1]
            raise VerificationError(
                "dist/ contains mismatched latest ProtoLink artifacts.\n"
                f"latest wheel version: {latest_wheel_version}\n"
                f"latest sdist version: {latest_sdist_version}\n"
                f"available wheel versions: {_format_versions(wheel_versions)}\n"
                f"available sdist versions: {_format_versions(sdist_versions)}\n"
                f"Use --artifact-version {suggested_common} to verify the latest complete pair, "
                "or clean dist/ and rebuild to keep only one release line."
            )

        selected_version = latest_wheel_version
        older_complete_versions = [version for version in common_versions if version != selected_version]
        if older_complete_versions:
            _print_step(
                "DIST",
                f"using latest ProtoLink dist version {selected_version}; ignored older complete versions: "
                f"{', '.join(older_complete_versions)}",
            )

    return ArtifactSelection(
        version=selected_version,
        wheel_file=_select_candidate(wheel_candidates, selected_version, "wheel"),
        sdist_file=_select_candidate(sdist_candidates, selected_version, "sdist"),
        wheel_versions=wheel_versions,
        sdist_versions=sdist_versions,
    )


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _find_console_script(venv_dir: Path) -> Path:
    script_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    candidates = [
        script_dir / "protolink",
        script_dir / "protolink.exe",
        script_dir / "protolink.cmd",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise VerificationError(f"ProtoLink console entry point was not installed under {script_dir}.")


def _probe_installed_module(python_executable: Path, *, cwd: Path, env: dict[str, str], venv_dir: Path) -> str:
    probe = _run_command(
        [
            str(python_executable),
            "-c",
            (
                "import json; "
                "from pathlib import Path; "
                "import protolink; "
                "print(json.dumps({'module_file': str(Path(protolink.__file__).resolve())}))"
            ),
        ],
        label="module origin probe",
        cwd=cwd,
        env=env,
    )
    try:
        payload = json.loads(probe.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Installed module probe did not return JSON.\n\nstdout:\n{probe.stdout}") from exc

    module_file = Path(str(payload["module_file"])).resolve()
    if not module_file.is_relative_to(venv_dir.resolve()):
        raise VerificationError(
            "Installed module origin escaped the fresh virtualenv.\n"
            f"module_file: {module_file}\n"
            f"venv_dir: {venv_dir.resolve()}"
        )
    return str(module_file)


def _parse_headless_summary(kind: str, output: str, isolated_base_dir: Path) -> dict[str, object]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or lines[0] != "ProtoLink":
        raise VerificationError(
            f"[{kind}] Unexpected headless summary output.\n"
            f"Expected first line to be `ProtoLink`.\n\n"
            f"stdout:\n{output}"
        )

    fields: dict[str, str] = {}
    for line in lines[1:]:
        separator = "："
        if separator in line:
            key, value = line.split(separator, 1)
            fields[key.strip()] = value.strip()
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()

    required_fields = ("工作区", "设置", "已注册传输", "模块数")
    missing_fields = [field for field in required_fields if field not in fields]
    if missing_fields:
        raise VerificationError(
            f"[{kind}] Headless summary is missing expected fields: {', '.join(missing_fields)}.\n\nstdout:\n{output}"
        )

    workspace = Path(fields["工作区"]).resolve()
    settings = Path(fields["设置"]).resolve()
    settings_root = settings.parent
    isolated_root = isolated_base_dir.resolve()

    if not workspace.exists():
        raise VerificationError(f"[{kind}] Headless summary reported a workspace that does not exist: {workspace}")
    if not settings_root.exists():
        raise VerificationError(
            f"[{kind}] Headless summary reported a settings root that does not exist: {settings_root}"
        )
    if not workspace.is_relative_to(isolated_root):
        raise VerificationError(
            f"[{kind}] Workspace escaped the isolated install root.\n"
            f"workspace: {workspace}\n"
            f"isolated_root: {isolated_root}"
        )
    if not settings.is_relative_to(isolated_root):
        raise VerificationError(
            f"[{kind}] Settings file escaped the isolated install root.\n"
            f"settings: {settings}\n"
            f"isolated_root: {isolated_root}"
        )

    return {
        "workspace": str(workspace),
        "settings": str(settings),
        "settings_root": str(settings_root),
        "settings_file_exists": settings.exists(),
        "summary_lines": lines,
    }


def _verify_artifact(kind: str, artifact_file: Path, temp_root: Path) -> dict[str, object]:
    label = kind.upper()
    venv_dir = temp_root / f"{kind}-venv"
    work_dir = temp_root / f"{kind}-run"
    isolated_base_dir = work_dir / "app-home"

    _print_step(label, f"creating fresh virtualenv at {venv_dir}")
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)

    python_executable = _venv_python(venv_dir)
    if not python_executable.exists():
        raise VerificationError(f"[{label}] Virtualenv Python executable was not created: {python_executable}")

    work_dir.mkdir(parents=True, exist_ok=True)
    isolated_base_dir.mkdir(parents=True, exist_ok=True)

    install_env = _sanitized_environment()

    _print_step(label, f"installing {artifact_file.name}")
    _run_command(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--default-timeout",
            "300",
            "--retries",
            "5",
            "--no-cache-dir",
            str(artifact_file),
        ],
        label=f"[{label}] pip install",
        cwd=temp_root,
        env=install_env,
    )

    console_script = _find_console_script(venv_dir)
    runtime_env = _sanitized_environment(isolated_base_dir=isolated_base_dir)
    module_file = _probe_installed_module(
        python_executable,
        cwd=work_dir,
        env=runtime_env,
        venv_dir=venv_dir,
    )
    _print_step(label, f"running {python_executable.name} -m protolink --headless-summary")

    summary_completed = _run_command(
        [str(python_executable), "-m", "protolink", "--headless-summary"],
        label=f"[{label}] python -m protolink --headless-summary",
        cwd=work_dir,
        env=runtime_env,
    )
    summary_details = _parse_headless_summary(label, summary_completed.stdout, isolated_base_dir)
    _print_step(
        label,
        (
            "verified fresh install at "
            f"{module_file}, workspace {summary_details['workspace']}, "
            f"settings {summary_details['settings']}"
        ),
    )

    return {
        "artifact_file": str(artifact_file),
        "venv_dir": str(venv_dir),
        "work_dir": str(work_dir),
        "isolated_base_dir": str(isolated_base_dir),
        "python_executable": str(python_executable),
        "console_script": str(console_script),
        "module_file": module_file,
        **summary_details,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dist_dir = args.dist_dir.resolve()
    temp_root = Path(tempfile.mkdtemp(prefix="protolink-dist-install-"))
    cleanup_temp_root = not args.keep_artifacts

    try:
        if not dist_dir.exists():
            raise VerificationError(f"Distribution directory does not exist: {dist_dir}")

        artifact_selection = _select_artifact_pair(
            dist_dir,
            requested_version=args.artifact_version,
        )

        result = {
            "dist_dir": str(dist_dir),
            "artifact_selection": {
                "selected_version": artifact_selection.version,
                "wheel_file": str(artifact_selection.wheel_file),
                "sdist_file": str(artifact_selection.sdist_file),
                "wheel_versions": list(artifact_selection.wheel_versions),
                "sdist_versions": list(artifact_selection.sdist_versions),
            },
            "wheel": _verify_artifact("wheel", artifact_selection.wheel_file, temp_root),
            "sdist": _verify_artifact("sdist", artifact_selection.sdist_file, temp_root),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except VerificationError as exc:
        cleanup_temp_root = False
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if cleanup_temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)
        else:
            print(f"Temporary artifacts kept at: {temp_root}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

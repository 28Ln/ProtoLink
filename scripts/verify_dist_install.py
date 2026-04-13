from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST_DIR = ROOT / "dist"
PROTOLINK_BASE_DIR_ENV = "PROTOLINK_BASE_DIR"


class VerificationError(RuntimeError):
    """Raised when dist installation verification fails."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify ProtoLink wheel and sdist can fresh-install from dist/ and run the console entry point."
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="Directory containing built distribution artifacts. Defaults to ./dist.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep the temporary virtual environments and working directories.",
    )
    return parser


def _print_step(kind: str, message: str) -> None:
    print(f"[{kind}] {message}", file=sys.stderr)


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


def _discover_single_artifact(dist_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(path.resolve() for path in dist_dir.glob(pattern) if path.is_file())
    if not matches:
        raise VerificationError(f"No {label} artifact matched '{pattern}' under {dist_dir}. Run `uv build` first.")
    if len(matches) > 1:
        raise VerificationError(
            f"Expected exactly one {label} artifact under {dist_dir}, found {len(matches)}:\n"
            + "\n".join(str(path) for path in matches)
        )
    return matches[0]


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
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        fields[key] = value

    required_fields = ("Workspace", "Settings", "Registered transports", "Modules")
    missing_fields = [field for field in required_fields if field not in fields]
    if missing_fields:
        raise VerificationError(
            f"[{kind}] Headless summary is missing expected fields: {', '.join(missing_fields)}.\n\nstdout:\n{output}"
        )

    workspace = Path(fields["Workspace"]).resolve()
    settings = Path(fields["Settings"]).resolve()
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

    _print_step(label, f"installing {artifact_file.name}")
    _run_command(
        [str(python_executable), "-m", "pip", "install", "--no-cache-dir", str(artifact_file)],
        label=f"[{label}] pip install",
        cwd=ROOT,
    )

    console_script = _find_console_script(venv_dir)
    _print_step(label, f"running {console_script.name} --headless-summary")

    runtime_env = os.environ.copy()
    runtime_env.pop("PYTHONPATH", None)
    runtime_env.pop("PYTHONHOME", None)
    runtime_env[PROTOLINK_BASE_DIR_ENV] = str(isolated_base_dir)

    summary_completed = _run_command(
        [str(console_script), "--headless-summary"],
        label=f"[{label}] protolink --headless-summary",
        cwd=work_dir,
        env=runtime_env,
    )
    summary_details = _parse_headless_summary(label, summary_completed.stdout, isolated_base_dir)
    _print_step(
        label,
        f"verified workspace {summary_details['workspace']} and settings {summary_details['settings']}",
    )

    return {
        "artifact_file": str(artifact_file),
        "venv_dir": str(venv_dir),
        "work_dir": str(work_dir),
        "isolated_base_dir": str(isolated_base_dir),
        "python_executable": str(python_executable),
        "console_script": str(console_script),
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

        wheel_file = _discover_single_artifact(dist_dir, "*.whl", "wheel")
        sdist_file = _discover_single_artifact(dist_dir, "*.tar.gz", "sdist")

        result = {
            "dist_dir": str(dist_dir),
            "wheel": _verify_artifact("wheel", wheel_file, temp_root),
            "sdist": _verify_artifact("sdist", sdist_file, temp_root),
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

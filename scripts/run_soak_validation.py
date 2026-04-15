from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SMOKE_OUTPUT = "smoke-check-ok"
REQUIRED_HEADLESS_SUMMARY_MARKERS = (
    "ProtoLink",
    "工作区：",
    "已注册传输：",
    "模块数：",
)


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 ProtoLink 的本地长稳/soak 验证循环。")
    parser.add_argument("--workspace", type=Path, help="可选，使用指定 workspace。默认创建临时 workspace。")
    parser.add_argument("--cycles", type=int, default=3, help="循环次数，默认 3。")
    parser.add_argument("--sleep-ms", type=int, default=0, help="循环间隔，默认 0 ms。")
    parser.add_argument("--require-all-ready", action="store_true", help="若任一循环未达到 ready 状态则返回非零退出码。")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留临时目录。")
    return parser


def _run_command(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def _run_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    completed = _run_command(command, cwd=cwd)
    if completed.returncode != 0:
        raise VerificationError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(
            "Command did not return JSON:\n"
            f"{' '.join(command)}\n\nstdout:\n{completed.stdout}"
        ) from exc


def _run_text(command: list[str], *, cwd: Path = ROOT) -> str:
    completed = _run_command(command, cwd=cwd)
    if completed.returncode != 0:
        raise VerificationError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def _evaluate_headless_summary(headless_summary: str) -> dict[str, bool]:
    lines = [line.strip() for line in headless_summary.strip().splitlines() if line.strip()]
    return {
        marker: any(marker in line for line in lines)
        for marker in REQUIRED_HEADLESS_SUMMARY_MARKERS
    }


def execute_soak_validation(
    *,
    workspace: Path | None = None,
    cycles: int = 3,
    sleep_ms: int = 0,
    require_all_ready: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-soak-validation-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()

    if cycles <= 0:
        raise VerificationError("cycles must be greater than zero")

    cycle_results: list[dict[str, object]] = []
    suite_started_at = time.perf_counter()
    for index in range(1, cycles + 1):
        cycle_started_at = time.perf_counter()
        generate_payload = _run_json(_uv("protolink", "--workspace", str(workspace), "--generate-smoke-artifacts"))
        headless_summary = _run_text(_uv("protolink", "--workspace", str(workspace), "--headless-summary"))
        headless_summary_lines = headless_summary.strip().splitlines()
        headless_markers = _evaluate_headless_summary(headless_summary)
        smoke_output = _run_text(_uv("protolink", "--workspace", str(workspace), "--smoke-check")).strip()
        smoke_ok = smoke_output == EXPECTED_SMOKE_OUTPUT
        preflight = _run_json(_uv("protolink", "--workspace", str(workspace), "--release-preflight"))
        preflight_ready = bool(preflight.get("ready", False))
        cycle_ready = smoke_ok and preflight_ready and all(headless_markers.values())
        cycle_results.append(
            {
                "cycle": index,
                "generate_smoke_artifacts": generate_payload,
                "headless_summary": headless_summary_lines,
                "headless_summary_markers": headless_markers,
                "smoke_output": smoke_output,
                "smoke_ok": smoke_ok,
                "preflight": preflight,
                "preflight_ready": preflight_ready,
                "cycle_ready": cycle_ready,
                "duration_ms": round((time.perf_counter() - cycle_started_at) * 1000, 3),
            }
        )
        if sleep_ms > 0 and index < cycles:
            time.sleep(sleep_ms / 1000)

    ready_cycles = sum(1 for item in cycle_results if bool(item["cycle_ready"]))
    failing_cycles = []
    for item in cycle_results:
        reasons: list[str] = []
        if not item["smoke_ok"]:
            reasons.append(f"smoke_output != {EXPECTED_SMOKE_OUTPUT}")
        if not item["preflight_ready"]:
            reasons.append("release_preflight not ready")
        missing_markers = [
            marker
            for marker, present in item["headless_summary_markers"].items()
            if not present
        ]
        if missing_markers:
            reasons.append(f"missing headless markers: {', '.join(missing_markers)}")
        if reasons:
            failing_cycles.append({"cycle": item["cycle"], "reasons": reasons})
    result = {
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "cycles": cycles,
        "sleep_ms": sleep_ms,
        "ready_cycles": ready_cycles,
        "all_cycles_ready": ready_cycles == cycles,
        "failing_cycles": failing_cycles,
        "total_duration_ms": round((time.perf_counter() - suite_started_at) * 1000, 3),
        "cycle_results": cycle_results,
    }
    if require_all_ready and not result["all_cycles_ready"]:
        raise VerificationError(f"Soak validation found {len(failing_cycles)} failing cycle(s).")
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    temp_root: Path | None = None
    if args.workspace is None and not args.keep_artifacts:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-soak-validation-main-"))
        workspace = temp_root / "workspace"
    else:
        workspace = args.workspace
    try:
        result = execute_soak_validation(
            workspace=workspace,
            cycles=args.cycles,
            sleep_ms=args.sleep_ms,
            require_all_ready=args.require_all_ready,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root is not None and not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

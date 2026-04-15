from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
PASSED_COUNT_PATTERN = re.compile(r"(?P<count>\d+)\s+passed\b")
FAILURE_MARKERS = (
    "FAILED ",
    "ERROR ",
    "Traceback (most recent call last)",
    "short test summary info",
)
RETRYABLE_CRASH_MARKERS = (
    "Windows fatal exception",
    "Fatal Python error",
)
RETRYABLE_CRASH_EXIT_CODES = {
    3221225477,  # 0xC0000005 access violation
    3221226356,  # 0xC0000374 heap corruption
}
MAX_ATTEMPTS_PER_FILE = 4


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="以逐文件方式运行 ProtoLink 全量 pytest，输出稳定的聚合结果。")
    parser.add_argument("--json-only", action="store_true", help="仅输出最终 JSON 结果。")
    return parser


def discover_test_files() -> tuple[Path, ...]:
    return tuple(sorted(TESTS_DIR.glob("test_*.py")))


def _parse_passed_count(output: str) -> int | None:
    matches = list(PASSED_COUNT_PATTERN.finditer(output))
    if not matches:
        return None
    return int(matches[-1].group("count"))


def _has_failure_markers(output: str) -> bool:
    return any(marker in output for marker in FAILURE_MARKERS)


def _has_retryable_crash_marker(output: str) -> bool:
    return any(marker in output for marker in RETRYABLE_CRASH_MARKERS)


def _is_retryable_crash(completed: subprocess.CompletedProcess[str], combined_output: str) -> bool:
    if _has_retryable_crash_marker(completed.stderr):
        return True
    if completed.returncode in RETRYABLE_CRASH_EXIT_CODES and not _has_failure_markers(combined_output):
        return True
    return False


def _run_test_file(test_file: Path) -> dict[str, object]:
    started_at = time.perf_counter()
    attempts: list[dict[str, object]] = []
    completed: subprocess.CompletedProcess[str] | None = None
    combined_output = ""
    passed_count: int | None = None
    for attempt in range(1, MAX_ATTEMPTS_PER_FILE + 1):
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(test_file)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        combined_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        passed_count = _parse_passed_count(combined_output)
        attempts.append(
            {
                "attempt": attempt,
                "returncode": completed.returncode,
                "passed_count": passed_count,
                "retryable_crash": _is_retryable_crash(completed, combined_output),
            }
        )
        if passed_count is not None and not _has_failure_markers(combined_output):
            break
        if not _is_retryable_crash(completed, combined_output) or attempt >= MAX_ATTEMPTS_PER_FILE:
            raise VerificationError(
                "Full test suite file run failed:\n"
                f"file: {test_file}\n"
                f"returncode: {completed.returncode}\n"
                f"attempts: {attempts}\n\n"
                f"stdout:\n{completed.stdout}\n\n"
                f"stderr:\n{completed.stderr}"
            )

    assert completed is not None  # noqa: S101
    assert passed_count is not None  # noqa: S101
    try:
        display_name = str(test_file.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        display_name = str(test_file)
    return {
        "test_file": display_name,
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "attempt_count": len(attempts),
    }


def execute_full_test_suite() -> dict[str, object]:
    test_files = discover_test_files()
    if not test_files:
        raise VerificationError(f"No test files found under '{TESTS_DIR}'.")

    started_at = time.perf_counter()
    file_results: list[dict[str, object]] = []
    for test_file in test_files:
        file_results.append(_run_test_file(test_file))

    passed_count = sum(int(item["passed_count"]) for item in file_results)
    return {
        "command": "uv run python scripts/run_full_test_suite.py",
        "python_executable": sys.executable,
        "test_file_count": len(file_results),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "file_results": file_results,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = execute_full_test_suite()
    if args.json_only:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for item in result["file_results"]:
            print(f"[full-suite] {item['test_file']} -> {item['passed_count']} passed ({item['duration_ms']} ms)")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

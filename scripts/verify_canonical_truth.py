from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SUITE_COMMAND = "uv run python scripts/run_full_test_suite.py"
TARGET_FILES = {
    "INDEX": ROOT / "docs" / "INDEX.md",
    "README": ROOT / "README.md",
    "TASKS": ROOT / "TASKS.md",
    "PROJECT_BRIEF": ROOT / "docs" / "PROJECT_BRIEF.md",
    "ARCHITECTURE": ROOT / "docs" / "ARCHITECTURE.md",
    "EXTENSION_CONTRACT": ROOT / "docs" / "EXTENSION_CONTRACT.md",
    "CURRENT_STATE": ROOT / "docs" / "CURRENT_STATE.md",
    "PROJECT_STATUS": ROOT / "docs" / "PROJECT_STATUS.md",
    "MAINLINE_STATUS": ROOT / "docs" / "MAINLINE_STATUS.md",
    "ENGINEERING_TASKLIST": ROOT / "docs" / "ENGINEERING_TASKLIST.md",
    "HANDOFF": ROOT / "docs" / "HANDOFF.md",
    "NATIVE_INSTALLER_PLAN": ROOT / "docs" / "NATIVE_INSTALLER_PLAN.md",
    "RISK_REGISTER": ROOT / "docs" / "RISK_REGISTER.md",
    "VALIDATION": ROOT / "docs" / "VALIDATION.md",
    "RELEASE_CHECKLIST": ROOT / "docs" / "RELEASE_CHECKLIST.md",
    "TASK_ARCHIVE": ROOT / "docs" / "TASK_ARCHIVE.md",
}


def _read(name: str) -> str:
    return TARGET_FILES[name].read_text(encoding="utf-8")


def _require_contains(label: str, text: str, needle: str) -> None:
    if needle not in text:
        raise SystemExit(f"{label} is missing expected text: {needle}")


def _require_regex(label: str, text: str, pattern: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        raise SystemExit(f"{label} is missing expected pattern: {pattern}")


def _require_absent(path: Path) -> None:
    if path.exists():
        raise SystemExit(f"Retired file should not exist: {path.relative_to(ROOT)}")


def _native_installer_related_flags(cli_source: str) -> list[str]:
    flags = {
        match
        for match in re.findall(r"--[a-z0-9][a-z0-9-]*", cli_source)
        if any(keyword in match for keyword in ("installer", "native", "wix"))
        and any(kind in match for kind in ("scaffold", "toolchain", "signature"))
    }
    return sorted(flags)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ProtoLink canonical truth is synchronized.")
    parser.add_argument("--expected-mainline", required=True)
    parser.add_argument("--expected-pytest-count", required=True, type=int)
    args = parser.parse_args()

    index = _read("INDEX")
    readme = _read("README")
    tasks = _read("TASKS")
    _read("PROJECT_BRIEF")
    _read("ARCHITECTURE")
    _read("EXTENSION_CONTRACT")
    current_state = _read("CURRENT_STATE")
    project_status = _read("PROJECT_STATUS")
    mainline_status = _read("MAINLINE_STATUS")
    tasklist = _read("ENGINEERING_TASKLIST")
    handoff = _read("HANDOFF")
    native_installer_plan = _read("NATIVE_INSTALLER_PLAN")
    risk_register = _read("RISK_REGISTER")
    validation = _read("VALIDATION")
    release_checklist = _read("RELEASE_CHECKLIST")
    task_archive = _read("TASK_ARCHIVE")
    cli_source = (ROOT / "src" / "protolink" / "app.py").read_text(encoding="utf-8")

    expected_mainline = args.expected_mainline
    expected_count = str(args.expected_pytest_count)

    _require_contains("INDEX", index, "HANDOFF.md")
    _require_contains("INDEX", index, "NATIVE_INSTALLER_PLAN.md")
    _require_contains("INDEX", index, "EXTENSION_CONTRACT.md")
    _require_contains("README", readme, f"Current canonical mainline: `{expected_mainline}`")
    _require_contains("README", readme, "`docs/HANDOFF.md`")
    _require_contains("README", readme, "`docs/ROADMAP.md`")
    _require_contains("README", readme, "Native installer scaffold")
    _require_contains("TASKS", tasks, "`docs/ENGINEERING_TASKLIST.md`")
    _require_contains("README", readme, FULL_SUITE_COMMAND)
    _require_contains("CURRENT_STATE", current_state, f"`{FULL_SUITE_COMMAND}` -> `{expected_count} passed`")
    _require_contains("PROJECT_STATUS", project_status, f"`{FULL_SUITE_COMMAND}` -> `{expected_count} passed`")
    _require_contains("VALIDATION", validation, f"`{FULL_SUITE_COMMAND}` -> {expected_count} passed")
    _require_contains("VALIDATION", validation, f"`{expected_count} passed`")
    _require_contains("VALIDATION", validation, "Native installer scaffold")
    _require_contains("MAINLINE_STATUS", mainline_status, f"- ID: `{expected_mainline}`")
    _require_contains("HANDOFF", handoff, "当前主线")
    _require_contains("NATIVE_INSTALLER_PLAN", native_installer_plan, "native installer scaffold")
    _require_contains("RELEASE_CHECKLIST", release_checklist, "native installer scaffold")
    _require_contains("RISK_REGISTER", risk_register, "风险清单")
    _require_contains("TASK_ARCHIVE", task_archive, "- `PL-012` —")
    _require_regex("ENGINEERING_TASKLIST", tasklist, rf"^### {re.escape(expected_mainline)} — ")
    _require_regex("PROJECT_STATUS", project_status, rf"^- `{re.escape(expected_mainline)}`")

    scaffold_flags = _native_installer_related_flags(cli_source)
    if scaffold_flags:
        _require_contains("VALIDATION", validation, "Native installer scaffold")
    for flag in scaffold_flags:
        _require_contains("README", readme, f"`{flag}`")
        _require_contains("NATIVE_INSTALLER_PLAN", native_installer_plan, f"`{flag}`")
        _require_contains("VALIDATION", validation, f"`{flag}`")
        _require_contains("RELEASE_CHECKLIST", release_checklist, f"`{flag}`")

    _require_absent(ROOT / "docs" / "REFERENCE_ANALYSIS.md")
    _require_absent(ROOT / "docs" / "WORKTREE_RECONCILIATION.md")
    _require_absent(ROOT / "docs" / "STATUS.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

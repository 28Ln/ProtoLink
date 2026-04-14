from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_FILES = {
    "INDEX": ROOT / "docs" / "INDEX.md",
    "README": ROOT / "README.md",
    "PROJECT_BRIEF": ROOT / "docs" / "PROJECT_BRIEF.md",
    "ARCHITECTURE": ROOT / "docs" / "ARCHITECTURE.md",
    "CURRENT_STATE": ROOT / "docs" / "CURRENT_STATE.md",
    "PROJECT_STATUS": ROOT / "docs" / "PROJECT_STATUS.md",
    "MAINLINE_STATUS": ROOT / "docs" / "MAINLINE_STATUS.md",
    "ENGINEERING_TASKLIST": ROOT / "docs" / "ENGINEERING_TASKLIST.md",
    "HANDOFF": ROOT / "docs" / "HANDOFF.md",
    "RISK_REGISTER": ROOT / "docs" / "RISK_REGISTER.md",
    "VALIDATION": ROOT / "docs" / "VALIDATION.md",
}


def _read(name: str) -> str:
    return TARGET_FILES[name].read_text(encoding="utf-8")


def _require_contains(label: str, text: str, needle: str) -> None:
    if needle not in text:
        raise SystemExit(f"{label} is missing expected text: {needle}")


def _require_regex(label: str, text: str, pattern: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        raise SystemExit(f"{label} is missing expected pattern: {pattern}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ProtoLink canonical truth is synchronized.")
    parser.add_argument("--expected-mainline", required=True)
    parser.add_argument("--expected-pytest-count", required=True, type=int)
    args = parser.parse_args()

    index = _read("INDEX")
    readme = _read("README")
    _read("PROJECT_BRIEF")
    _read("ARCHITECTURE")
    current_state = _read("CURRENT_STATE")
    project_status = _read("PROJECT_STATUS")
    mainline_status = _read("MAINLINE_STATUS")
    tasklist = _read("ENGINEERING_TASKLIST")
    handoff = _read("HANDOFF")
    risk_register = _read("RISK_REGISTER")
    validation = _read("VALIDATION")

    expected_mainline = args.expected_mainline
    expected_count = str(args.expected_pytest_count)

    _require_contains("INDEX", index, "HANDOFF.md")
    _require_contains("README", readme, f"Current canonical mainline: `{expected_mainline}`")
    _require_contains("README", readme, "`docs/HANDOFF.md`")
    _require_contains("CURRENT_STATE", current_state, f"`uv run pytest -q` -> `{expected_count} passed`")
    _require_contains("PROJECT_STATUS", project_status, f"`uv run pytest -q` -> `{expected_count} passed`")
    _require_contains("VALIDATION", validation, f"`uv run pytest -q` -> {expected_count} passed")
    _require_contains("VALIDATION", validation, f"`{expected_count} passed`")
    _require_contains("MAINLINE_STATUS", mainline_status, f"- ID: `{expected_mainline}`")
    _require_contains("HANDOFF", handoff, "当前主线")
    _require_contains("RISK_REGISTER", risk_register, "风险清单")
    _require_regex("ENGINEERING_TASKLIST", tasklist, rf"^### {re.escape(expected_mainline)} — ")
    _require_regex("PROJECT_STATUS", project_status, rf"^- `{re.escape(expected_mainline)}`")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

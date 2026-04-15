from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验证 ProtoLink 的 native installer lane（toolchain / scaffold / msi / signature）。")
    parser.add_argument("--workspace", type=Path, help="可选，使用指定 workspace。默认创建临时 workspace。")
    parser.add_argument("--name", default="native-lane", help="scaffold/build 名称前缀。")
    parser.add_argument("--require-toolchain", action="store_true", help="若 WiX 或 SignTool 缺失则返回非零退出码。")
    parser.add_argument("--require-signed", action="store_true", help="若 MSI 签名校验未通过则返回非零退出码。")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留临时目录。")
    return parser


def _run_command(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return completed


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


def _run_optional_json(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    completed = _run_command(command, cwd=cwd)
    payload: dict[str, object] | None = None
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload": payload,
    }


def _uv(*args: str) -> list[str]:
    return ["uv", "run", *args]


def execute_native_installer_lane(
    *,
    workspace: Path | None = None,
    name: str = "native-lane",
    require_toolchain: bool = False,
    require_signed: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-native-installer-lane-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()

    toolchain = _run_json(_uv("protolink", "--verify-native-installer-toolchain"))
    scaffold_build = _run_json(_uv("protolink", "--workspace", str(workspace), "--build-native-installer-scaffold", name))
    scaffold_dir = Path(str(scaffold_build["native_installer_scaffold_dir"])).resolve()
    scaffold_verify = _run_json(_uv("protolink", "--verify-native-installer-scaffold", str(scaffold_dir)))

    msi_build = None
    signature_verify = None
    msi_file: Path | None = None

    if bool(toolchain.get("tools", {}).get("wix", {}).get("available", False)):
        msi_build = _run_optional_json(_uv("protolink", "--build-native-installer-msi", str(scaffold_dir)))
        payload = msi_build.get("payload") if isinstance(msi_build, dict) else None
        if isinstance(payload, dict) and payload.get("output_file"):
            msi_file = Path(str(payload["output_file"])).resolve()

    if msi_file is not None and bool(toolchain.get("tools", {}).get("signtool", {}).get("available", False)):
        signature_verify = _run_optional_json(_uv("protolink", "--verify-native-installer-signature", str(msi_file)))

    ready_for_release = bool(toolchain.get("ready", False)) and bool(msi_build and msi_build.get("ok")) and bool(
        signature_verify and signature_verify.get("ok")
    )

    result = {
        "workspace": str(workspace),
        "temporary_root": str(temp_root) if temp_root is not None else None,
        "toolchain": toolchain,
        "scaffold_build": scaffold_build,
        "scaffold_verify": scaffold_verify,
        "msi_build": msi_build,
        "signature_verify": signature_verify,
        "ready_for_release": ready_for_release,
    }

    if require_toolchain and not bool(toolchain.get("ready", False)):
        raise VerificationError("Native installer toolchain is not ready on this machine.")
    if require_signed and not ready_for_release:
        raise VerificationError("Native installer lane is not signed-and-ready on this machine.")
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    temp_root: Path | None = None
    if args.workspace is None and not args.keep_artifacts:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-native-installer-lane-main-"))
        workspace = temp_root / "workspace"
    else:
        workspace = args.workspace
    try:
        result = execute_native_installer_lane(
            workspace=workspace,
            name=args.name,
            require_toolchain=args.require_toolchain,
            require_signed=args.require_signed,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        if temp_root is not None and not args.keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
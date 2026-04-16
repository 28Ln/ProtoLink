# ProtoLink Release Checklist

Last updated: 2026-04-16

## 用途

本文件是正式发布运行手册，只描述当前有效的发布前检查，不承载任务、状态或历史叙事。

## 前置条件

- `docs/MAINLINE_STATUS.md` 与 `docs/ENGINEERING_TASKLIST.md` 已同步
- `docs/VALIDATION.md` 与 README 中的验证命令已同步
- 工作区与设置路径明确
- 本地仓库处于可交接状态

## 最小发布前命令

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 356
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables
python scripts/verify_dist_install.py --artifact-version 0.2.5
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
python scripts/verify_native_installer_lane.py --require-toolchain
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

## 工作区与交付检查

- `uv run protolink --release-preflight` 返回 `ready: true`
- 若工作区存在 enabled Class A extensions，则 `extension_runtime_load_report.ready` 必须为 `true` 且 `extension_runtime_failed_count == 0`
- release bundle / installer package 的 manifest、payload、receipt 可验证
- 安装产物包含运行时、`sp/`、启动脚本、安装脚本
- 安装、验证、卸载链路保持闭环
- recorded service close failures 会阻断 preflight，必须先清理

## 文档与真值检查

- README、`docs/CURRENT_STATE.md`、`docs/PROJECT_STATUS.md`、`docs/VALIDATION.md` 的主线与验证数字一致
- `.github/workflows/ci.yml` 与当前验证基线一致
- 发布手册与冒烟手册只保留当前有效命令
- 当前 native installer scaffold/toolchain/build/signature 命令为：
  - `--build-native-installer-scaffold`
  - `--verify-native-installer-scaffold`
  - `--verify-native-installer-toolchain`
  - `--build-native-installer-msi`
  - `--verify-native-installer-signature`
- `uv run protolink --help` 中必须能看到这些命令
- `README.md`、`docs/NATIVE_INSTALLER_PLAN.md`、`docs/VALIDATION.md`、本文件必须包含**精确 flag 名称**
- `--load-enabled-extensions` 作为正式 CLI surface 时，README、`docs/VALIDATION.md`、`docs/EXTENSION_CONTRACT.md` 与本文件必须保持同一口径
- `scripts/verify_canonical_truth.py` 必须通过
- scaffold / toolchain / build / signature verify 仅用于推进原生安装器路线，不替代现有 release-staging / dist-install / build 门禁

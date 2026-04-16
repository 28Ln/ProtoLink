# ProtoLink Release Checklist

Last updated: 2026-04-16

## 用途

本文件是正式发布运行手册，只描述当前有效的发布前检查，不承载任务、状态或历史叙事。

## 前置条件

- `docs/MAINLINE_STATUS.md` 与 `docs/ENGINEERING_TASKLIST.md` 已同步
- `docs/VALIDATION.md` 与 README 中的验证命令已同步
- 工作区与设置路径明确
- 本地仓库处于可交接状态

## 当前 bundled-runtime 发布前命令

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 369
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables
uv run python scripts/verify_release_deliverables.py --target-dir dist\\deliverables
python scripts/verify_dist_install.py --artifact-version 0.2.5
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

## Native installer cutover additional gate

```powershell
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
python scripts/verify_native_installer_lane.py --require-toolchain
python scripts/verify_native_installer_lane.py --require-signed
```

- 本节只在评估 signed native installer cutover 时启用，不属于当前 bundled-runtime 正式发布前命令。
- `verify_native_installer_lane.py` 默认输出 probe truth；只有显式加 `--require-toolchain` 或 `--require-signed` 时，才把 native installer readiness 变成非零退出码。
- native installer scaffold 在进入 cutover 讨论前，必须先通过 lifecycle / identity contract 校验。

## 签名、审批与回退要求

- 必须使用已批准的代码签名证书对 MSI 做 Authenticode 签名。
- 必须使用已批准的 RFC3161 时间戳服务；没有时间戳的签名不允许进入 cutover 决策。
- 切换 native installer release lane 前，至少保留一份已验证的 bundled-runtime installer package 作为回退产物。
- 切换前必须记录 release owner 审批与签名操作审批；审批证据应与签名产物一同归档。
- 只有在 clean-machine install / uninstall / `protolink --headless-summary` 全部通过后，native installer 才允许进入 cutover 决策。
- `dist/deliverables` 发布归档应包含 `deliverables-manifest.json` 与 `native-installer-lane-receipt.json`，用于交付后复核。
- `dist/deliverables` 发布归档还应包含 `NATIVE_INSTALLER_CUTOVER_POLICY.json`，用于复核签名 / 时间戳 / 审批 / 回滚 policy。

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
- `--verify-native-installer-scaffold` 必须能校验 `target_arch`、`install_scope`、`install_dir_name`、`product_code_policy`、`upgrade_strategy` 与静默安装命令
- `python scripts/verify_native_installer_lane.py --receipt-file <path>` 可作为 release evidence 落盘入口
- `uv run python scripts/verify_release_deliverables.py --target-dir <dir>` 可作为 deliverables 目录复核入口
- `docs/NATIVE_INSTALLER_CUTOVER_POLICY.json` 是 native installer cutover policy 的正式机器可读真值
- `uv run protolink --help` 中必须能看到这些命令
- `README.md`、`docs/NATIVE_INSTALLER_PLAN.md`、`docs/VALIDATION.md`、本文件必须包含**精确 flag 名称**
- `--load-enabled-extensions` 作为正式 CLI surface 时，README、`docs/VALIDATION.md`、`docs/EXTENSION_CONTRACT.md` 与本文件必须保持同一口径
- `scripts/verify_canonical_truth.py` 必须通过
- scaffold / toolchain / build / signature verify 仅用于推进原生安装器路线，不替代现有 release-staging / dist-install / build 门禁
- 当前 bundled-runtime 发布不以 native installer toolchain readiness 为 blocker；native cutover 才启用 `--require-toolchain` / `--require-signed`

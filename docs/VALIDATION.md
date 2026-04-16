# ProtoLink Validation

Last updated: 2026-04-16

## 当前验证基线

- `uv run python scripts/run_full_test_suite.py` -> 361 passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 361` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/audit_gui_layout.py --output-dir dist\gui-audit\latest` -> passed
- `uv run protolink --audit-plugin-manifests` -> passed
- `uv run protolink --list-extension-descriptors` -> passed
- `uv run protolink --plan-extension-loading` -> passed
- `uv run protolink --load-enabled-extensions` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py --artifact-version 0.2.5` -> passed
- `python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready` -> passed
- `uv build` -> passed
- `uv run protolink --headless-summary` -> passed
- `uv run protolink --smoke-check` -> `smoke-check-ok`
- 当前 full-suite 快照：`361 passed`

## 本地开发验证

```powershell
uv sync --python 3.11 --extra dev
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 361
uv run python scripts/audit_gui_layout.py --output-dir dist\gui-audit\latest
uv run protolink --audit-plugin-manifests
uv run protolink --list-extension-descriptors
uv run protolink --plan-extension-loading
uv run protolink --load-enabled-extensions
```

## UI / owner-surface 相关验证

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --smoke-check
```

## 当前 bundled release 验证

```powershell
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py --artifact-version 0.2.5
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

- 当前 `0.2.5` 正式发布门禁仍是 bundled-runtime 路线；`verify_native_installer_lane.py` 默认只输出 probe truth，不把 toolchain / signed MSI 作为当前 release blocker。
- `verify_native_installer_lane.py` 默认会输出 `current_canonical_release_lane`、`native_installer_lane_phase`、`blocking_items`、`next_action`，用于解释 native installer 当前处于 probe、toolchain-ready、unsigned 或 signed-ready 的哪一阶段。
- `uv run protolink --verify-native-installer-scaffold` 现在会校验 lifecycle contract，并要求 manifest / WiX source / WiX include 在 `install_scope`、`install_dir_name`、`upgrade_strategy`、`downgrade_error_message`、静默安装命令等字段上保持一致。
- `verify_native_installer_lane.py` 现在会把 `lifecycle_contract_ready` 纳入 `stage_status`；contract 不完整时会输出 `contract-incomplete` phase 与 `repair_lifecycle_contract` next_action。
- `verify_native_installer_lane.py` 现在支持 `--receipt-file <path>`，可把 lane truth 持久化为 JSON receipt。
- `build_release_deliverables.py` 现在会在目标目录写出 `deliverables-manifest.json` 与 `native-installer-lane-receipt.json`。
- `run_soak_validation.py` 在使用 `--require-all-ready` 时会把非 ready 循环转为非零退出码，并输出 `cycle_ready`、`failing_cycles`、`total_duration_ms`。
- `run_full_test_suite.py` 以逐文件方式聚合 full-suite 真值，是当前正式的 pytest 基线入口。
- `audit-plugin-manifests` 会静态审计 `workspace/plugins/*/manifest.json`；任何 invalid manifest 都会进入 `--release-preflight` 阻断。
- `list-extension-descriptors` 只列出通过静态校验的扩展描述清单；`plan-extension-loading`、`load-enabled-extensions` 与 `release-preflight` 共同解释可装载状态、显式 Class A runtime execution 与正式交付门禁。
- `audit_gui_layout.py` 当前在目标分辨率下返回 `highest_severity=clean`，dashboard 与报文分析台的已知布局压缩警告已收敛。
- 2.0 收尾文档应与本文件保持同一真值口径，尤其是 `HANDOFF_2_0` / `PROJECT_FLOW_2_0` / `ISSUE_REGISTER_2_0`。

## Native installer cutover evaluation

```powershell
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
python scripts/verify_native_installer_lane.py --require-toolchain
python scripts/verify_native_installer_lane.py --require-signed
```

- 这些命令只用于 future signed native installer cutover 评估，不属于当前 bundled-runtime 正式发布 gate。
- `--require-toolchain` 只在评估 WiX / SignTool 已就绪时启用。
- `--require-signed` 只在 MSI 已完成签名与签名校验后启用。

## Extension boundary verification

当前 extension runtime boundary 的验证口径是：

1. `uv run protolink --audit-plugin-manifests` 能发现并校验 `workspace/plugins/*/manifest.json`
2. invalid manifest 会进入 `--release-preflight` 阻断
3. `uv run protolink --list-extension-descriptors` 只列出 valid manifest 汇总出的 descriptor registry
4. `uv run protolink --plan-extension-loading` 会输出 `eligible_for_loading` / `review_required` / `blocked_high_risk` / `blocked_registry_invalid` 等状态
5. `uv run protolink --load-enabled-extensions` 只会显式执行 enabled 且 `effective_state=eligible_for_loading` 的 Class A `register()`
6. `uv run protolink --release-preflight` 会复用同一条 Class A runtime gate，并在 `load_failed` 时写入 failure evidence
7. Class B 当前仍停留在 `review_required`，Class C 当前不进入该 runtime CLI 的执行范围

当前验证通过并不代表：

- 应用启动时会自动加载外部扩展
- Class B / Class C 已被允许运行时激活
- UI、transport、automation 或 script host 扩展注入已开放

## Native installer scaffold 真值门禁

- 当前 CLI 基线已暴露：
  - `--build-native-installer-scaffold`
  - `--verify-native-installer-scaffold`
  - `--verify-native-installer-toolchain`
  - `--build-native-installer-msi`
  - `--verify-native-installer-signature`
- 这些命令必须满足以下门禁：
  1. `uv run protolink --help` 可见
  2. `README.md` 包含精确 flag 名称
  3. `docs/NATIVE_INSTALLER_PLAN.md` 包含精确 flag 名称与用途
  4. `docs/RELEASE_CHECKLIST.md` 包含精确 flag 名称与发布前检查要求
  5. `scripts/verify_canonical_truth.py` 通过
  6. `--verify-native-installer-scaffold` 能校验 lifecycle / identity contract，而不只是 payload checksum

## 通过标准

一个可交接、可继续迭代的基线至少应满足：

1. full pytest 通过
2. targeted regressions 通过
3. canonical truth 校验通过
4. release-staging 校验通过
5. fresh-install 校验通过
6. build 产物可生成

## 注意事项

- 文档中的数字与主线 ID 必须与验证真值同步更新。
- `uv` 管理的环境是当前正式验证口径。
- 临时环境、临时 workspace 与本地审计产物不应作为正式交付真值。
- `scripts/verify_dist_install.py` 默认自动选择 dist/ 中最新且 wheel/sdist 同版本成对存在的产物；若最新 wheel 与 sdist 版本不一致，脚本会显式报错并提示使用 `--artifact-version` 或先清理旧产物。

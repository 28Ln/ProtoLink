# ProtoLink Validation

Last updated: 2026-04-16

## 当前验证基线

- `uv run python scripts/run_full_test_suite.py` -> 350 passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 350` -> passed
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
- 当前 full-suite 快照：`350 passed`

## 本地开发验证

```powershell
uv sync --python 3.11 --extra dev
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 350
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

## 交付链验证

```powershell
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py --artifact-version 0.2.5
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

- `verify_native_installer_lane.py` 默认输出 readiness probe；若要作为发布门禁，必须显式加 `--require-toolchain` 或 `--require-signed`。
- `run_soak_validation.py` 在使用 `--require-all-ready` 时会把非 ready 循环转为非零退出码，并输出 `cycle_ready`、`failing_cycles`、`total_duration_ms`。
- `run_full_test_suite.py` 以逐文件方式聚合 full-suite 真值，是当前正式的 pytest 基线入口。
- `audit-plugin-manifests` 会静态审计 `workspace/plugins/*/manifest.json`；任何 invalid manifest 都会进入 `--release-preflight` 阻断。
- `list-extension-descriptors` 只列出通过静态校验的扩展描述清单；`plan-extension-loading` 与 `load-enabled-extensions` 负责继续解释可装载状态与显式 Class A runtime execution。

## Extension boundary verification

当前 extension runtime boundary 的验证口径是：

1. `uv run protolink --audit-plugin-manifests` 能发现并校验 `workspace/plugins/*/manifest.json`
2. invalid manifest 会进入 `--release-preflight` 阻断
3. `uv run protolink --list-extension-descriptors` 只列出 valid manifest 汇总出的 descriptor registry
4. `uv run protolink --plan-extension-loading` 会输出 `eligible_for_loading` / `review_required` / `blocked_high_risk` / `blocked_registry_invalid` 等状态
5. `uv run protolink --load-enabled-extensions` 只会显式执行 enabled 且 `effective_state=eligible_for_loading` 的 Class A `register()`
6. Class B 当前仍停留在 `review_required`，Class C 当前不进入该 runtime CLI 的执行范围

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

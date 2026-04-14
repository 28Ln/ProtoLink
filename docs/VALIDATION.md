# ProtoLink Validation

Last updated: 2026-04-15

## 当前验证基线

- `uv run pytest -q` -> 280 passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 280` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py` -> passed
- `uv build` -> passed
- `uv run protolink --headless-summary` -> passed
- `uv run protolink --smoke-check` -> `smoke-check-ok`
- 当前 full-suite 快照：`280 passed`

## 本地开发验证

```powershell
uv sync --python 3.11 --extra dev
uv run pytest -q
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 280
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
python scripts/verify_dist_install.py
# 如 dist/ 下并存多个历史版本，默认会校验最新且 wheel/sdist 成对存在的版本；
# 若最新 wheel / sdist 版本不一致，则传入明确版本或先清理 dist/。
python scripts/verify_dist_install.py --artifact-version 0.2.2
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv build
```

## Native installer scaffold 真值门禁

- 当前 CLI 基线已暴露：
  - `--build-native-installer-scaffold`
  - `--verify-native-installer-scaffold`
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

# ProtoLink Validation

Last updated: 2026-04-14

## 当前验证基线

- `uv run pytest -q` -> 280 passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-013 --expected-pytest-count 280` -> passed
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
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-013 --expected-pytest-count 280
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
python scripts/verify_dist_install.py --artifact-version 0.2.1
uv build
```

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

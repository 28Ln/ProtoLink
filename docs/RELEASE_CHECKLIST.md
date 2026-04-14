# ProtoLink Release Checklist

Last updated: 2026-04-14

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
uv run pytest -q
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 280
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py
uv build
```

> 若 `dist/` 下并存多个版本产物，`scripts/verify_dist_install.py` 默认验证最新且 wheel/sdist 成对存在的版本；若最新 wheel 与 sdist 版本不一致，应先清理旧产物，或使用 `python scripts/verify_dist_install.py --artifact-version <version>` 显式校验目标版本。

## 工作区与交付检查

- `uv run protolink --release-preflight` 返回 `ready: true`
- release bundle / installer package 的 manifest、payload、receipt 可验证
- 安装产物包含运行时、`sp/`、启动脚本、安装脚本
- 安装、验证、卸载链路保持闭环
- recorded service close failures 会阻断 preflight，必须先清理

## 文档与真值检查

- README、`docs/CURRENT_STATE.md`、`docs/PROJECT_STATUS.md`、`docs/VALIDATION.md` 的主线与验证数字一致
- `.github/workflows/ci.yml` 与当前验证基线一致
- 发布手册与冒烟手册只保留当前有效命令

## 签收标准

- full pytest 通过
- targeted regressions 通过
- canonical truth 通过
- release-staging 通过
- dist fresh-install 通过
- build 成功
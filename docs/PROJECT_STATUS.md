# ProtoLink Project Status

Last updated: 2026-04-14

## 当前阶段

ProtoLink 当前处于：**正式交付基线收敛阶段**。

这意味着项目已经不是“功能能不能跑”的问题，而是要把现有成果沉淀为：

- 可交付
- 可接手
- 可持续迭代
- 可验证回归

的正式工程状态。

## 当前真实进展

- 工程代码入口、工作区、日志、配置、打包链路已统一
- 274 个 pytest 用例通过
- targeted regression 全绿
- release-staging 验证全链通过
- wheel / sdist fresh-install 验证通过
- README、状态文档、风险文档、handoff 文档已形成正式入口

## 当前验证快照

- `uv run pytest -q` -> `274 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-012 --expected-pytest-count 274` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py` -> passed

## 未完成事项

### P0
1. 文档与任务体系进一步去噪，避免临时说明重新渗入正式文档
2. 将当前基线在共享仓库 / 交接流程中固定为可复现 handoff 点

### P1
3. 继续收敛打包体积，降低 bundled-runtime 冗余负载
4. 补强 failure evidence 与异常兜底覆盖，尤其是关闭/清理路径
5. 明确脚本与扩展边界，避免被误解为不受信执行环境

### P2
6. 规划插件/扩展契约与后续协议扩展接入方式
7. 规划 native installer / signing 路线

## 当前单一主线

- `PL-012` — Delivery Baseline Consolidation

详见：`docs/MAINLINE_STATUS.md`

## 当前不建议并行推进的方向

在 `PL-012` 完成之前，不建议优先做：

- 新协议大面扩展
- 大规模 UI 重构
- 非必要平台扩展
- 非必要交付形态扩展

原因：当前收益最高的是让既有能力沉淀成正式工程资产，而不是继续堆叠新功能面。

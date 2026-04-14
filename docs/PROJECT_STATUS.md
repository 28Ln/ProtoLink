# ProtoLink Project Status

Last updated: 2026-04-14

## 当前阶段

ProtoLink 当前处于：**0.2.1 正式版本基线已冻结，进入 native installer 路线准备阶段**。

这意味着当前优先级已经不是继续扩功能面，而是围绕已冻结的正式基线继续推进：

- 原生安装器路线
- 签名交付边界
- 现有交付链稳定性
- 扩展边界

## 当前真实进展

- 工程代码入口、工作区、日志、配置、打包链路已统一
- 280 个 pytest 用例通过
- targeted regression 全绿
- release-staging 验证全链通过
- wheel / sdist fresh-install 验证通过
- README、状态文档、风险文档、handoff 文档已形成正式入口
- `PL-012` 与 `PL-013` 已关闭，当前正式主线已切换为 `PL-014`

## 当前验证快照

- `uv run pytest -q` -> `280 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 280` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py` -> passed

## 未完成事项

### P0
1. 明确 native installer / signing 的目标边界、切换条件与验证路线
2. 维持 CI、文档、交付脚本在同一真值口径上，保证 0.2.1 基线不回退

### P1
3. 明确脚本与扩展边界，避免被误解为不受信执行环境
4. 规划插件/扩展契约与协议接入方式

### P2
5. 规划 HIL / 长稳回归能力

## 当前单一主线

- `PL-014` — Native Installer and Signing Path

详见：`docs/MAINLINE_STATUS.md`

## 当前不建议并行推进的方向

在 `PL-014` 完成之前，不建议优先做：

- 新协议大面扩展
- 大规模 UI 重构
- 非必要平台扩展
- 非必要交付形态扩展

原因：当前收益最高的是把已经冻结的正式基线继续推进到更正式的安装与签名形态，而不是重新扩大维护面。
# ProtoLink Project Status

Last updated: 2026-04-15

## 当前阶段

ProtoLink 当前处于：**0.2.5 正式版本基线已冻结，进入 native installer 构建/签名与长稳验证准备阶段**。

## 当前真实进展

- 工程代码入口、工作区、日志、配置、打包链路已统一
- 298 个 pytest 用例通过
- targeted regression 全绿
- release-staging 验证全链通过
- wheel / sdist fresh-install 验证通过
- README、状态文档、风险文档、handoff 文档已形成正式入口
- `PL-012` 与 `PL-013` 已关闭，当前正式主线已切换为 `PL-014`
- `PL-014` 已具备 WiX scaffold 构建/校验、toolchain 检测、MSI build 与签名校验 CLI
- 已具备 `verify_native_installer_lane.py` 原生安装器 lane 脚本
- 已具备 `run_soak_validation.py` 本地长稳/soak 验证脚本与 strict ready gate

## 当前验证快照

- `uv run pytest -q` -> `298 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 298` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py --artifact-version 0.2.5` -> passed
- `python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready` -> passed

## 未完成事项

### P0
1. 将当前 WiX scaffold / toolchain / MSI build / signature verify 推进到受控签名的正式发布 lane
2. 维持 CI、文档、交付脚本在同一真值口径上，保证 0.2.5 基线不回退

### P1
3. 定义签名与时间戳的受控发布流程
4. 明确脚本与扩展边界，避免被误解为不受信执行环境
5. 规划插件/扩展契约与协议接入方式

### P2
6. 规划 HIL / 长稳回归能力

## 当前单一主线

- `PL-014` — Native Installer and Signing Path

详见：`docs/MAINLINE_STATUS.md`

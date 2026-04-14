# ProtoLink Current State

Last updated: 2026-04-14

## 当前真实进展

ProtoLink 已完成从“原型功能集合”到“可验证工程基线”的第一阶段收敛，当前状态如下：

### 已完成
- Windows-first 桌面工程骨架已经建立
- 统一工作区、设置、日志、导出、打包链路已经建立
- 传输能力已覆盖：Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server
- 协议工作流已覆盖：Modbus RTU / Modbus TCP 的基础调试闭环
- 自动化能力已覆盖：自动应答、规则引擎、脚本控制台、定时任务、通道桥接
- 回归体系、release-staging 验证、fresh-install 验证已经可执行

### 当前可交付能力
- `uv run protolink --headless-summary`
- `uv run protolink --smoke-check`
- `uv run protolink --release-preflight`
- `uv run protolink --build-installer-package <name>`
- `uv run protolink --verify-installer-package <archive>`
- `uv run protolink --install-installer-package <archive> <staging> <install>`
- `uv run protolink --uninstall-portable-package <install-dir>`

## 当前验证基线

- `uv run pytest -q` -> `274 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-012 --expected-pytest-count 274` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py` -> passed
- `uv build` -> passed

## 当前工程判断

ProtoLink 现在已经具备：

- 可运行
- 可回归
- 可打包
- 可安装
- 可交接

ProtoLink 当前还不具备：

- 原生签名 Windows 安装器
- 面向不受信环境的脚本沙箱
- 面向插件/协议扩展的正式 SDK 契约
- 硬件在环（HIL）级别的长期回归体系

## 当前工作重点

当前重点已经从“补单点功能”转为“正式交付基线收敛”，即：

- 固化正式文档集
- 固化任务与风险台账
- 让项目在无口头说明的情况下可接手、可继续迭代
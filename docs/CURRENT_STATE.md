# ProtoLink Current State

Last updated: 2026-04-15

## 当前真实进展

ProtoLink 已完成正式基线收敛、第一次交付瘦身、运行证据补强，并进入 native installer 路线的可执行构建阶段。

当前状态分为三层：

- 已完成：`PL-012` Delivery Baseline Consolidation
- 已完成：`PL-013` Package Slimming and Delivery Hardening
- 进行中：`PL-014` Native Installer and Signing Path

### 已完成
- Windows-first 桌面工程骨架已经建立
- 统一工作区、设置、日志、导出、打包链路已经建立
- 传输能力已覆盖：Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server
- 协议工作流已覆盖：Modbus RTU / Modbus TCP 的基础调试闭环
- 自动化能力已覆盖：自动应答、规则引擎、脚本控制台、定时任务、通道桥接
- 回归体系、release-staging 验证、fresh-install 验证已经可执行
- 正式文档、任务台账、风险台账、handoff 入口已经冻结为单一口径
- portable/distribution/installer package 已完成第一轮 package slimming
- session service 的 shutdown / close 失败已经进入统一 failure evidence，并进入 release-preflight 阻断
- `verify_dist_install.py` 已支持多版本 dist 产物选择策略
- 已新增 WiX/MSI scaffold 构建与校验命令
- 已新增 native installer toolchain 检测命令
- 已新增 MSI build 与签名校验命令

### 当前可交付能力
- `uv run protolink --headless-summary`
- `uv run protolink --smoke-check`
- `uv run protolink --release-preflight`
- `uv run protolink --build-installer-package <name>`
- `uv run protolink --verify-installer-package <archive>`
- `uv run protolink --install-installer-package <archive> <staging> <install>`
- `uv run protolink --uninstall-portable-package <install-dir>`
- `uv run protolink --build-native-installer-scaffold <name>`
- `uv run protolink --verify-native-installer-scaffold <scaffold-dir>`
- `uv run protolink --verify-native-installer-toolchain`
- `uv run protolink --build-native-installer-msi <scaffold-dir>`
- `uv run protolink --verify-native-installer-signature <msi-file>`

## 当前验证基线

- `uv run python scripts/run_full_test_suite.py` -> `312 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 312` -> passed
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py --artifact-version 0.2.5` -> passed
- `python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready` -> passed
- `uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\deliverables` -> passed
- `uv build` -> passed

## 当前 UI 工程判断

- 主窗口已从“说明区与底部 dock 挤压主工作面”的失衡结构，重构为以主工作面为中心的分栏布局
- 报文分析台已改为 tab + splitter 结构，默认 dock 高度已收敛
- Modbus RTU / Modbus TCP / 寄存器监视 / 自动化规则已完成第一轮 tab 化
- Serial / MQTT / TCP / UDP 面板已完成第二轮 tab 化与状态区换行
- Hero、左侧导航、右侧说明区与底部报文分析台已完成第三轮减重与首屏聚焦
- `dist/deliverables/` 已可稳定产出 release / portable / distribution / installer 归档并完成安装自检
- GUI 收口任务、剩余视觉问题与交付级验收标准已沉淀为 `docs/GUI_REFACTOR_TASKLIST.md`
- 仍有细粒度视觉问题待继续修整，但已不再属于“整体塌陷/乱码假象”的不可用状态

## 当前工程判断

ProtoLink 现在已经具备：
- 可运行
- 可回归
- 可打包
- 可安装
- 可交接
- 可为原生安装器路线生成与校验 WiX/MSI scaffold
- 可执行 MSI build / signature verify CLI（取决于本机 toolchain）

ProtoLink 当前还不具备：
- 原生签名 Windows 安装器正式发布线
- 面向不受信环境的脚本沙箱
- 面向插件/协议扩展的正式 SDK 契约
- 硬件在环（HIL）级别的长期回归体系

## 当前工作重点

当前重点已经从“交付基线收敛”和“第一次交付瘦身”推进到：

- 把当前 WiX scaffold / toolchain / MSI build / signature verify CLI 推进到受控发布 lane
- 把 soak 验证脚本推进到更长时间、更高负载的验证策略
- 保持 0.2.5 现有 bundled-runtime 交付链稳定可回退
- 为扩展与插件接入建立正式契约

# ProtoLink Mainline Status

Last updated: 2026-04-16

## Single active mainline

- ID: `PL-014`
- Title: Native Installer and Signing Path

## 前置结论

`PL-012` 与 `PL-013` 已完成，ProtoLink 现阶段已经具备：

- 正式交付基线
- 第一次 package slimming / delivery hardening 成果
- 关闭/清理路径的关键 failure evidence 基线
- 稳定的 release-staging / fresh-install 验证链
- WiX/MSI scaffold 构建与校验 CLI
- native installer toolchain 检测 CLI
- MSI build 与签名校验 CLI

## 目标

在不破坏 0.2.5 基线的前提下，推进原生安装器与签名路线，建立从 bundled-runtime 交付向更正式安装形态演进的工程路径。

## 为什么现在做这件事

当前已经具备：

- `364 passed`
- `release-staging passed`
- `dist fresh-install passed`
- `soak ready gate passed`

因此当前最高优先级是把已经收敛的交付基线推进到下一形态：

- 明确 native installer / signing 路线
- 明确切换条件、验证策略与回退边界
- 保证 0.2.5 现有交付链在过渡期间保持稳定

## 当前范围

`PL-014` 聚焦：

1. 定义 native installer / signing 路线的目标交付形态
2. 定义从 bundled-runtime 交付切换到更正式安装器形态的进入条件
3. 定义验证策略、签名要求、回退边界
4. 保持现有 0.2.5 交付链作为稳定回退基线
5. 将 scaffold / toolchain / MSI build / signature verify 推进到受控发布 lane

## 退出条件

`PL-014` 只在以下条件全部满足时关闭：

- native installer / signing 路线文档化完成
- 切换条件、回退条件、验证边界明确
- WiX scaffold 已进入真正的 MSI build / 签名验证路径
- 现有 bundled-runtime 交付基线继续保持稳定可验证
- 下一阶段实现任务已具备明确入口
## 后续候选主线

- `PL-015` — Extension Contract and Plugin Boundary
- `PL-016` — Hardware-in-the-Loop and Long-Run Validation

# ProtoLink Mainline Status

Last updated: 2026-04-14

## Single active mainline

- ID: `PL-012`
- Title: Delivery Baseline Consolidation

## 目标

把 ProtoLink 从“验证通过的开发态”收敛为“正式交付、正式交接、正式迭代”的工程基线。

## 为什么现在做这件事

当前已经具备：

- `274 passed`
- `release-staging passed`
- `dist fresh-install passed`

因此当前最高优先级不再是继续加功能，而是统一：

- 项目目标口径
- 架构口径
- 运行与交付口径
- 主线任务口径
- 风险与交接口径

## 当前范围

`PL-012` 聚焦：

1. 正式文档体系收敛
2. 单一主线任务与正式任务台账
3. README / 文档入口 / 交接入口整理
4. 风险台账固化
5. 交付与 handoff 套件落地

## 退出条件

`PL-012` 只在以下条件全部满足时关闭：

- README、状态、验证、风险、handoff 文档完成收敛
- 项目在无口头说明前提下可被新接手者运行与验证
- 当前主线、未完成事项、风险与交付边界都有唯一正式文档
- CI / 验证 / 文档真值保持同步

## 后续候选主线

- `PL-013` — Package Slimming and Native Installer Path
- `PL-014` — Extension Contract and Plugin Boundary
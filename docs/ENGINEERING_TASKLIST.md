# ProtoLink Engineering Tasklist

Last updated: 2026-04-14

## Canonical rules

- 本文件是唯一正式任务台账。
- 任一时刻只允许一个 `Active` 主线任务。
- `Archived` 任务不再回到 `Active`，除非出现新的事实依据。
- 临时审计结论、聊天记录、零散 TODO 不视为正式任务来源。

## Active

### PL-012 — Delivery Baseline Consolidation

- Classification: `Active`
- Objective:
  - 把现有可验证成果整理为正式工程基线，确保可交付、可接手、可继续迭代。
- Scope:
  1. 正式文档体系收敛
  2. 单一主线与正式任务台账固化
  3. README / 文档入口 / handoff 套件完善
  4. 风险台账与运行边界固化
- Exit criteria:
  - 正式文档集完成并职责清晰
  - handoff 文档可支撑新接手者独立启动与验证
  - 风险文档覆盖当前主要工程边界
  - CI / 验证 / 文档口径一致

## Next

### PL-013 — Package Slimming and Native Installer Path

- Classification: `Next`
- Objective:
  - 继续降低 bundled-runtime 冗余负载，并规划原生安装器路线。

### PL-014 — Extension Contract and Plugin Boundary

- Classification: `Next`
- Objective:
  - 为协议扩展、模块扩展、插件接入建立正式边界。

## Archived

- `PL-001` — release-gate hardening
- `PL-002` — bundled-runtime delivery
- `PL-003` — runtime/session truth unification
- `PL-004` — verification and engineering standards
- `PL-005` — clean release-staging sign-off
- `PL-006` — automation expansion and safety controls
- `PL-007` — script console owner surface
- `PL-008` — data tools owner surface
- `PL-009` — network tools owner surface
- `PL-010` — owner-surface consistency closure
- `PL-011` — repository baseline reconciliation and formal baseline freeze

历史别名与无效口径见：`docs/TASK_ARCHIVE.md`
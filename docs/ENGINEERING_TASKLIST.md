# ProtoLink Engineering Tasklist

Last updated: 2026-04-14

## Canonical rules

- 本文件是唯一正式任务台账。
- 任一时刻只允许一个 `Active` 主线任务。
- `Archived` 任务不再回到 `Active`，除非出现新的事实依据。
- 临时审计结论、聊天记录、零散 TODO 不视为正式任务来源。

## Active

### PL-014 — Native Installer and Signing Path

- Classification: `Active`
- Objective:
  - 在保持 0.2.2 基线稳定的前提下，推进原生安装器与签名交付路线。
- Scope:
  1. 定义 native installer / signing 目标形态
  2. 定义切换条件、验证策略与回退边界
  3. 保持 0.2.2 基线在过渡期间稳定可验证
- Exit criteria:
  - native installer / signing 路线形成正式计划
  - 切换条件、验证策略、回退边界文档化
  - 0.2.2 基线保持稳定

## Next

### PL-015 — Extension Contract and Plugin Boundary

- Classification: `Next`
- Objective:
  - 为协议扩展、模块扩展、插件接入建立正式边界。

### PL-016 — Hardware-in-the-Loop and Long-Run Validation

- Classification: `Next`
- Objective:
  - 为 HIL、长稳运行与长期回归建立工程化验证能力。

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
- `PL-012` — delivery baseline consolidation
- `PL-013` — package slimming and delivery hardening

历史别名与无效口径见：`docs/TASK_ARCHIVE.md`

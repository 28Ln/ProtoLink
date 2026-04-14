# ProtoLink Engineering Tasklist

Last updated: 2026-04-14

## Canonical rules

- 本文件是唯一正式任务台账。
- 任一时刻只允许一个 `Active` 主线任务。
- `Archived` 任务不再回到 `Active`，除非出现新的事实依据。
- 临时审计结论、聊天记录、零散 TODO 不视为正式任务来源。

## Active

### PL-013 — Package Slimming and Delivery Hardening

- Classification: `Active`
- Objective:
  - 在不破坏正式基线的前提下，继续降低交付冗余并补强运行证据。
- Scope:
  1. 收敛 bundled runtime 与打包 allowlist
  2. 补强关闭、清理、安装、卸载路径的 failure evidence
  3. 保持文档、CI、release-staging、dist-install 真值一致
  4. 定义 native installer / signing 的进入条件与边界
- Exit criteria:
  - 打包冗余继续下降，且正式验证链无回归
  - 关键关闭/清理/交付路径具备可复盘的 failure evidence
  - native installer 路线具备可执行的计划边界
  - 正式文档、CI、验证基线保持同步

## Next

### PL-014 — Native Installer and Signing Path

- Classification: `Next`
- Objective:
  - 在 `PL-013` 完成后推进原生安装器与签名交付路线。

### PL-015 — Extension Contract and Plugin Boundary

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
- `PL-012` — delivery baseline consolidation

历史别名与无效口径见：`docs/TASK_ARCHIVE.md`

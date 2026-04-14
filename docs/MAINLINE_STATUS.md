# ProtoLink Mainline Status

Last updated: 2026-04-14

## Single active mainline

- ID: `PL-013`
- Title: Package Slimming and Delivery Hardening

## 前置结论

`PL-012` 已完成，ProtoLink 已具备正式基线、正式文档、正式交接入口和可执行验证链。

当前进入 `PL-013`，是因为下一阶段的最高收益不再来自继续整理文档，而来自继续降低交付成本并补强运行证据。

## 目标

在不破坏当前正式基线的前提下，继续收敛交付包内容、补强运行与交付证据，并为原生安装器路线保留清晰接口。

## 为什么现在做这件事

当前已经具备：

- `280 passed`
- `release-staging passed`
- `dist fresh-install passed`

因此当前最高优先级是继续提高正式交付质量，而不是继续加功能：

- 降低 bundled runtime 冗余
- 补强关闭/清理/安装链的 failure evidence
- 让后续 native installer 路线有清晰切换条件

## 当前范围

`PL-013` 聚焦：

1. 收敛打包 allowlist，继续清理 bundled runtime 冗余负载
2. 补强关闭、清理、安装、卸载路径的异常证据
3. 保持 release-staging / dist-install / CI / 文档真值一致
4. 形成 native installer / signing 的切换条件和规划边界

## 退出条件

`PL-013` 只在以下条件全部满足时关闭：

- 交付包内容较当前基线显著收敛，且无回归
- 关键关闭/清理/交付路径具备足够的 failure evidence
- CI、文档、release-staging、dist-install 维持同一真值
- native installer / signing 路线具有明确的进入条件与边界说明

## 后续候选主线

- `PL-014` — Native Installer and Signing Path
- `PL-015` — Extension Contract and Plugin Boundary

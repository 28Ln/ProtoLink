# ProtoLink Long-Term Engineering Plan

Last updated: 2026-04-17

## 1. Purpose

本文定义 ProtoLink 从当前“可运行、可验证、可交付”的 2.0 阶段基线，向长期可维护、可扩展、可审计、可持续演进的工程平台推进的正式方向。

本文不替代当前单一主线任务台账：

- 当前 `Active` 主线仍是 `PL-014`
- 当前任务真值仍以 `docs/ENGINEERING_TASKLIST.md` 为准

本文的作用是提供：

- 长期架构方向
- truth / config / runtime / evidence 的统一原则
- 配置、日志、异常、存储、GUI 的长期模型
- 未来 3 到 6 个阶段的迁移序列

## 2. Design Priorities

长期工程化遵循以下默认优先级：

1. 主链路阻塞、不可运行、核心功能失效、数据/状态错误
2. owner 收口、架构边界、runtime truth / context truth / config truth 统一
3. 配置、日志、异常、状态语义统一，去硬编码、去漂移
4. 测试、验证、回归稳定性、长期运行稳定性
5. 文档、tasklist、handoff 的长期有效性
6. UI、一致性、性能、体验优化
7. 扩展能力和次级增强

这意味着：

- ProtoLink 的第一目标不是“堆功能”，而是把现有工作台做成可长期演进的平台
- GUI 重要，但 GUI 必须建立在稳定 truth 和稳定运行链之上
- 存储、配置、异常、验证必须先于“炫酷能力”工程化

## 3. Current Constraints

截至当前仓库真值，ProtoLink 具备：

- 单一 Windows-first 本地桌面交付模型
- 共享 bootstrap 入口：CLI / GUI 共用同一初始化链
- workspace-first 归属边界
- 结构化日志、failure evidence、deliverables evidence
- 多 transport / protocol / automation / packet tooling 基线
- release-staging / fresh-install / soak / GUI audit / deliverables verify 可执行

当前约束是：

- 仍是本地桌面单体，不是分布式系统
- 不以数据库为中心，而是以文件和证据链为中心
- 不引入云端/多端协同
- 扩展边界当前仍需保守治理

## 4. Target Architecture

### 4.1 System shape

ProtoLink 的长期目标架构是：**Windows-first modular monolith with explicit host ownership**

即：

- 仍保持单机桌面单体
- 但不再是“main window + 一堆 service 的直接拼接”
- 要演进成由统一 `WorkbenchHost` / `RuntimeHost` 持有生命周期的模块化工作台

目标分层：

1. Shell Layer
   - GUI shell
   - CLI shell
   - delivery shell
2. Host Layer
   - startup / shutdown
   - runtime supervision
   - context registry
   - truth registry
   - validation gateway
3. Feature Layer
   - transport sessions
   - protocol workbenches
   - automation runtimes
   - tools
4. Core Domain Layer
   - state models
   - documents
   - fault policy
   - logging/evidence
   - packet/transport abstractions
5. Infrastructure Layer
   - serial/tcp/udp/mqtt adapters
   - packaging/install/deliverables
   - local filesystem persistence

### 4.2 Host responsibility

长期必须引入一个统一 Host 概念，负责：

- 生命周期统一启动/关闭
- 各 worker / scheduler / async runner 的托管
- 统一 health / readiness / blocking_items
- 统一 truth query surface
- 向 GUI / CLI 暴露相同的状态语义

目标不是“把逻辑搬到 GUI 外面”这么简单，而是：

- GUI 不再直接拥有 concrete service 网络
- CLI 不再手工拼装多条 truth
- release-preflight / headless-summary / deliverables verify 统一基于 Host 暴露的 truth surface

## 5. Truth Model

ProtoLink 长期必须明确四类 truth：

### 5.1 Config Truth

描述用户或工程显式声明的持久配置：

- app settings
- workspace manifest
- transport profiles
- automation rules
- extension registry config
- native installer cutover policy

特点：

- replace-in-full JSON
- 带 `format_version`
- 带 owner / truth_boundary / updated_at
- 可迁移
- 可验证

### 5.2 Context Truth

描述当前被选中、被激活、被指向的对象：

- active workspace
- active module
- active session
- selected peer / selected preset
- current target context

特点：

- 可以持久化，也可以纯运行期
- 不是 transport raw event
- 不是 GUI 私有状态
- 由 host / context registry 统一提供

### 5.3 Runtime Truth

描述运行期客观状态：

- connection state
- runtime snapshots
- packet inspector state
- runtime counters / loaded modules / running tasks
- transport events

特点：

- 不直接作为配置保存
- append-only 事件 + derived snapshot
- GUI 只消费 projection

### 5.4 Evidence Truth

描述错误、验证、交付、风险判断所需证据：

- failure evidence
- validation receipts
- deliverables manifest
- native installer lane receipt
- cutover evidence

特点：

- append-only 或 immutable receipt
- 不能和 draft/config 混在一起
- 必须可归档、可追溯、可验证

## 6. Configuration Model

### 6.1 General rule

所有持久 JSON 文档长期要统一到一个 document contract：

- `format_version`
- `meta.owner`
- `meta.truth_boundary`
- `meta.updated_at`

并统一具备：

- UTF-8 读取
- JSON object 限制
- schema validation
- invalid backup
- failure evidence
- atomic write + replace

### 6.2 File ownership model

长期建议：

- `.protolink/app_settings.json`
  - 仅保存 app-level shell/config
- `workspace/workspace_manifest.json`
  - 仅保存 workspace 布局、版本与 migration truth
- `workspace/profiles/*.json`
  - 仅保存 transport/profile truth
- `workspace/rules/*.json`
  - 仅保存 automation/timed-task/channel-bridge 类规则 truth
- `workspace/logs/*.jsonl`
  - 仅保存 runtime / evidence
- `workspace/evidence/*.json` / `*.jsonl`
  - 仅保存验证与 failure receipts

当前最大问题之一是：

- 运行时 snapshot、draft/config、错误状态有时混在一条对象链里
- 持久化触发和 snapshot 更新耦合过深

长期要拆成：

- `FeatureConfig`
- `FeatureContext`
- `FeatureRuntimeState`
- `FeatureProjection`

## 7. Storage Model

### 7.1 Primary stance

ProtoLink 长期仍建议以 **workspace-first file-backed storage** 为主，不要过早把 SQLite/数据库设成系统真值中心。

原因：

- 当前所有验证链、交付链、handoff 链都是围绕文件和证据构建的
- 本地工业工作台更需要“可复制、可检视、可打包、可审计”的状态
- 数据库现在会增加迁移复杂度，却不能立即解决最核心的 boundary/owner 问题

### 7.2 When to introduce SQLite

SQLite 可以作为 **派生索引层 / 性能层**，但不是一开始的 canonical truth：

- 大量 packet / log / replay 数据的索引
- 快速搜索 / 聚合 / filter
- 长时运行性能优化

即：

- canonical truth 仍是 JSON / JSONL / receipt
- SQLite 是 cache/index/projection，不是唯一事实源

### 7.3 Evidence storage split

建议长期把 evidence 明确拆分：

- `workspace/logs/runtime-events.jsonl`
- `workspace/evidence/failure-evidence.jsonl`
- `workspace/evidence/validation/*.json`

不要继续让 `transport-events.jsonl` 承担所有类别的运行证据。

## 8. Exception and Fault Model

ProtoLink 长期不应该只停留在 `last_error` + string message。

必须引入统一 fault model：

- `fault_code`
- owner
- boundary
- severity
- user_message
- technical_message
- recovery
- evidence_required
- cli_exit_mapping

推荐长期模块：

- `core/fault_codes.py`
- `core/fault_policy.py`
- `core/faults.py`

目标：

- 所有 transport / config / extension / delivery / shutdown / install / preflight 错误都进入统一 fault policy
- 新错误不能再随意写字符串 category/code
- CLI / GUI / logs / evidence 对同一 fault 要共享同一语义

## 9. Logging and Evidence

### 9.1 Logging

长期日志模型要从“结构化日志可用”升级到“结构化日志有统一 owner/boundary”：

- event_id
- timestamp
- owner
- boundary
- category
- operation_id
- session_id
- level
- message
- metadata

### 9.2 Evidence

failure evidence 和 validation receipt 必须继续强化：

- failure evidence: append-only
- validation receipt: immutable JSON snapshot

deliverables 验证、native installer lane、soak、preflight 都应该统一成 validation receipt 家族，而不是每条脚本各自产 JSON shape 却没有统一 registry。

## 10. Runtime Supervision

当前各 service / async runner / worker thread 分散存在。

长期要引入统一 runtime supervision：

- host-managed async runners
- host-managed worker threads
- startup/shutdown ordering
- health / readiness / degraded states
- failure escalation policy

目标：

- 不再由每个 service 自己长出不同的 runtime ownership
- shutdown failure / close failure / drain failure 都有统一归因

## 11. GUI Direction

### 11.1 Position

GUI 在长期规划中的位置是：**projection shell**

GUI 不应负责：

- persistence
- migration
- evidence policy
- lifecycle ownership

GUI 应负责：

- shell orchestration
- feature projection
- operator focus
- context visibility
- status / action / feedback

### 11.2 GUI roadmap

GUI 长期方向分两层：

1. 先完成当前 QWidget 体系的视觉与组件系统收口
2. 再决定未来是否保留 QWidget shell，或逐步引入更强 shell/component abstraction

当前不建议直接做全量 QML 重写。

当前更合理的方向是：

- 保留 QWidget
- 引入更清晰 theme token / component system
- 让 shell 和 feature panel 的构造边界更干净
- 通过 shell API 减少 main window 对 concrete services 的直接依赖

## 12. Validation Strategy

长期验证必须继续保持分层：

1. schema / document contract tests
2. migration tests
3. fault/evidence tests
4. feature regression tests
5. preflight / staging / install / deliverables verify
6. soak / long-run validation
7. GUI audit / UI regression

不建议把所有验证压成一条脚本。
建议的是：

- 分层保留
- 输入 truth 统一
- receipt schema 统一

## 13. Recommended Migration Phases

### Phase A: Truth and Document Foundation

目标：

- document contract 统一
- atomic write 统一
- invalid-backup / failure evidence 统一

优先对象：

- app settings
- workspace manifest
- automation rules

### Phase B: Truth Registry and Fault Policy

目标：

- 引入 truth registry
- 引入 fault code / fault policy
- headless-summary / preflight 基于统一 truth 查询

### Phase C: Runtime Host and Context Registry

目标：

- host-managed lifecycle
- context registry
- session/runtime ownership 统一

### Phase D: Delivery and Validation Unification

目标：

- release-preflight / deliverables / installer / native lane receipt schema 统一
- native installer cutover evidence 正式闭环

### Phase E: GUI Shell Refactor

目标：

- shell API 化
- component system 化
- 视觉系统统一

### Phase F: Extension Governance and HIL

目标：

- extension lifecycle/governance
- HIL / long-run validation

## 14. Latest Long-Term Tasklist

1. 建立 document contract、truth registry、fault policy 三个基础设施层
2. 把 app settings / workspace manifest / automation rules 迁移到统一 document contract
3. 把 runtime events / failure evidence / validation receipts 统一为明确的 evidence family
4. 引入 host-managed runtime ownership 与 context registry
5. 让 release-preflight / headless-summary / deliverables verify 基于统一 truth registry
6. 完成 native installer cutover evidence 的 owner 流程和真实可达 `policy_ready`
7. 完成 QWidget GUI shell 的视觉系统与 component system 收口
8. 在新 fault/evidence/validation 基线之上推进 extension governance
9. 在新 truth/evidence/host 基线之上推进 HIL / long-run validation

## 15. Execution Guidance

在当前阶段，不建议直接切换 `Active` 主线。

更合理的做法是：

- 继续完成 `PL-014`
- 同时把本文作为未来 `PL-015+` 以及后续 architecture track 的正式前置参考

判断标准只有一个：

> 下一支团队接手时，是否能在不依赖口头补充的情况下理解系统如何长期演进。


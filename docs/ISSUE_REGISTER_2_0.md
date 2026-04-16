# ProtoLink 2.0 Issue Register

Last updated: 2026-04-16

## 1. Purpose

本文记录当前 2.0 阶段收尾版本中仍然存在的已知问题、风险点与后续建议。

这里的“问题”包括：

- 真正的缺陷
- 交付缺口
- 架构治理缺口
- 长稳验证缺口
- 文档漂移和仓库卫生问题

## 2. Issues

### I-001 尚未形成受控签名原生安装器正式发布线

- Level: High
- Type: Delivery / Release
- Evidence:
  - `verify_native_installer_lane.py` 当前仅为 probe
  - 本机实际结果仍为 WiX / SignTool 缺失
  - 当前正式交付线仍是 bundled-runtime installer package
- Impact:
  - 不能宣称已经具备正式 signed MSI 发布能力
  - 企业分发与信任链仍未闭环
- Validation:
  - WiX / SignTool 可用
  - MSI build / sign / verify 通过
  - 安装 / 卸载 / headless-summary 闭环通过
- Suggested next step:
  - 在 `PL-014` 内完成签名流程、时间戳流程、回滚流程与正式 release gate

### I-002 Native installer lane 仍未进入正式门禁

- Level: Medium
- Type: Verification / Delivery
- Evidence:
  - 当前 `verify_native_installer_lane.py` 是单独 probe
  - 当前正式基线仍以 release-staging / dist-install / build 为主
- Impact:
  - Native installer 路线 readiness 与正式交付门禁仍分离
- Validation:
  - 明确 probe 与 gate 的差异
  - 将 future cutover 标准沉淀成正式 release policy
- Suggested next step:
  - 在不破坏 bundled gate 的前提下，继续推进 PL-014 的 release lane 设计

### I-003 当前 packaged GUI 启动入口仍依赖脚本启动器

- Level: Medium
- Type: Delivery / UX
- Evidence:
  - 当前交付安装结果的 canonical 启动入口仍是 `Launch-ProtoLink.bat` / `Launch-ProtoLink.ps1`
  - 当前仓库基线中没有独立业务 EXE 作为正式真值
- Impact:
  - 交付体验不够直接
  - 用户容易误认为“没有真正应用入口”
- Validation:
  - 未来若引入独立 EXE，必须进入 release-staging / deliverables / docs / fresh-install 验证链
- Suggested next step:
  - 作为后续交付增强项评估，不在本次文档收尾中实现

### I-004 Class B / Class C 扩展治理未完成

- Level: Medium
- Type: Architecture / Extensibility
- Evidence:
  - 当前扩展边界只到 Class A 显式受控加载
  - Class B 仍是 `review_required`
  - Class C 仍不进入自动执行范围
- Impact:
  - 扩展路线尚未进入完整 runtime governance 阶段
- Validation:
  - lifecycle model、review workflow、边界策略明确
- Suggested next step:
  - 在 `PL-015` 中推进 lifecycle、Class B review、Class C 边界与正式 SDK 契约

### I-005 Script host 不是不受信沙箱

- Level: High
- Type: Security Boundary
- Evidence:
  - 当前仅具备受控脚本宿主，不提供系统级隔离
  - 文档已明确其非目标
- Impact:
  - 若被误用为通用脚本沙箱，会形成错误安全承诺
- Validation:
  - 文档和 handoff 必须持续明确边界
- Suggested next step:
  - 保持文档明确，不在当前版本对外夸大脚本安全能力

### I-006 HIL 与长期运行回归体系缺失

- Level: Medium
- Type: Validation / Reliability
- Evidence:
  - 当前 soak 仅到本地脚本与短周期门禁
  - 无 HIL 体系
- Impact:
  - 真实设备长稳行为与边界故障无法充分覆盖
- Validation:
  - 建立更长时长 soak、HIL 环境、设备级回归计划
- Suggested next step:
  - 在 `PL-016` 中正式推进

### I-007 Bundled runtime 体积仍偏大

- Level: Medium
- Type: Delivery
- Evidence:
  - 当前交付仍以 bundled runtime 为核心
  - 打包体积仍较大
- Impact:
  - 下载、存储、安装成本偏高
- Validation:
  - 体积对比、必要依赖裁剪、安装体验评估
- Suggested next step:
  - 继续在不破坏稳定性的前提下做第二轮瘦身

### I-008 GUI 仍有产品化收口剩余

- Level: Medium
- Type: UX / Consistency
- Evidence:
  - `GUI-101/103/104/105` 仍未关闭
  - formal audit 已 clean，但这只证明结构与布局已过线，不代表产品化收口完成
- Impact:
  - 视觉体系、文案、局部重复表达仍有提升空间
- Validation:
  - 继续按 `GUI_REFACTOR_TASKLIST.md` 的正式标准推进
- Suggested next step:
  - 作为 supporting workstream 持续推进，不改变当前主线归属

### I-009 仓库存在临时探针 / 噪音目录

- Level: Low
- Type: Repository Hygiene
- Evidence:
  - 仓库根目录与 `dist/` 下存在多组临时 probe / smoke 目录
- Impact:
  - 干扰交接、降低仓库可读性
- Validation:
  - 清理后保持 canonical deliverables / latest audit / current dist artifacts 不受影响
- Suggested next step:
  - 本次 2.0 收尾中执行清理

### I-010 文档真值漂移风险持续存在

- Level: Medium
- Type: Documentation / Process
- Evidence:
  - 当前正式文档数量多
  - 历史上已出现 pytest 计数、主线状态、交付口径漂移
- Impact:
  - 新团队接手时容易被错误真值误导
- Validation:
  - 以 `verify_canonical_truth.py` 与本次收尾文档统一为主
- Suggested next step:
  - 继续压缩重复真值来源，优先引用 canonical docs

## 3. Current Non-Issues

以下内容当前不再视为 blocker：

- GUI 布局塌陷 / 中文压缩假象
- packet console 默认压缩主工作面
- release-staging 基线不可运行
- fresh-install 基线不可运行


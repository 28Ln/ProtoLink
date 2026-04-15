# ProtoLink Extension Contract

Last updated: 2026-04-14

## 1. Purpose

本文定义 ProtoLink 的正式扩展契约，明确：

- 哪些边界允许扩展
- 插件可以声明哪些能力
- 插件如何被发现、校验、装载、启动、停止、卸载
- 插件如何接入 workspace / logs / exports / script host / UI
- 插件的安全边界、版本边界和向后兼容要求

本文是工程约束，不是概念说明。任何插件机制实现、插件接入、插件验收、插件发布都必须以本文为准。

## 2. Current state

ProtoLink 当前已经具备以下事实基础：

- 工作区内存在 `workspace/plugins/` 保留目录
- workspace 是配置、日志、脚本、抓包、导出的统一归属
- 运行日志采用 `workspace/logs/transport-events.jsonl`
- failure evidence 采用 `workspace/logs/runtime-failure-evidence.jsonl`
- 导出与交付产物必须带 manifest，并声明 `format_version`
- UI / application / core / transport 已形成分层

当前版本尚未提供“无限制第三方插件动态加载承诺”。在 `PL-015` 完成前，外部插件属于受控扩展，不是“任意 Python 包接入即受支持”的开放生态。

## 3. Design principles

### 3.1 Single source of truth
- 原始字节、结构化日志、workspace 产物是事实源。
- 插件不得绕过正式日志、导出、工作区结构建立平行事实源。

### 3.2 Stable boundary first
插件必须优先扩展以下稳定边界：
- transport boundary
- application service boundary
- import/export boundary
- module/panel boundary
- script host integration boundary

禁止直接通过 monkey patch 修改：
- 主窗口骨架
- 内建 service 私有字段
- EventBus 内部存储结构
- 运行时全局解释器行为

### 3.3 UI 不承担 I/O
插件 UI 只能消费 snapshot、service action 和受控事件，不能在 UI 线程直接执行阻塞 I/O。

### 3.4 Evidence first
插件运行失败必须留下：
- 用户可见错误
- 结构化日志
- 必要时 failure evidence

### 3.5 Workspace first
插件运行期状态、资产、脚本、导出必须归属当前 workspace，不允许默认写入仓库根目录或系统临时目录充当正式产物目录。

## 4. Extension surface classification

### Class A — Pure data / parser extensions
允许优先扩展：
- 协议解析器
- 数据转换器
- 导入导出编解码器
- 报文展示增强器

### Class B — Read-only operational extensions
允许后续评估：
- 只读诊断视图
- 报表导出
- workspace 资产分析

### Class C — Restricted runtime integrations
高风险，必须单独评审：
- transport adapter 扩展
- automation runtime hook
- script host extension
- UI owner surface injection

## 5. Plugin manifest requirements

任何未来插件都必须有显式 manifest。当前仓库已经落地的静态校验口径为：

- 路径：`workspace/plugins/<plugin-id>/manifest.json`
- `format_version`：`protolink-plugin-manifest-v1`
- `plugin_id`
- `display_name`
- `plugin_version`
- `extension_api_version`
- `capabilities`
- `entrypoint`
- `min_app_version`
- `max_app_version`（可选）

兼容说明：
- 当前静态校验暂时接受 legacy 字段 `api_version`、`min_protolink_version`、`max_protolink_version`
- legacy 字段不会触发阻断，但会进入 warning，后续应统一迁移到 canonical 字段

当前静态校验还会额外检查：
- `plugin_id` 必须与目录名一致
- 版本字符串必须为数字点分格式
- 当前 app version 必须满足 `min_app_version` / `max_app_version`
- 同一 workspace 内 `plugin_id` 不得重复

manifest 必须先通过静态校验，才允许进入后续发现/装载流程。当前版本已做到 discovery / validation / audit / descriptor listing / preflight gate，不做动态加载。

## 6. Lifecycle

未来正式插件生命周期定义为：

1. `discovered`
2. `validated`
3. `loaded`
4. `started`
5. `degraded`
6. `stopped`
7. `unloaded`
8. `disabled`
9. `failed`

要求：
- `register()` 必须幂等
- `start()` 重复调用不得重复订阅或重复起线程
- `stop()` 必须可重入
- `stop()` 超时或异常必须进入 failure evidence

## 7. Workspace / logs / exports boundary

### Workspace
插件的正式数据只能写入：
- `workspace/plugins/<plugin-id>/`
- `workspace/logs/`
- `workspace/exports/`

### Logs
插件日志必须进入统一结构化日志：
- category 前缀：`plugin.<plugin_id>.*`
- metadata 必须包含 `plugin_id`
- 关键异常必须记录 failure evidence

### Exports
插件输出正式资产时必须：
- 写入 `workspace/exports/...`
- 生成 `manifest.json`
- 声明 `format_version`
- 不得伪造 ProtoLink 内建 manifest 版本

## 8. Script host boundary

插件与脚本宿主不是同一层能力。

约束：
- 插件只能通过正式 `ScriptHostService` 发起脚本执行
- 插件不能把当前 script host 误包装为不受信执行环境
- context 必须为小体积、可序列化对象
- 单次执行必须有 timeout
- 不允许将脚本作为插件主生命周期线程模型

## 9. UI integration boundary

插件不得直接修改主窗口内部结构。

未来若开放 UI 扩展，必须通过明确的 descriptor / registration contract，例如：
- panel descriptor
- action descriptor
- read-only status surface

在没有正式 descriptor contract 前，不允许插件直接插入任意 owner surface。

## 10. Transport and automation boundary

未来扩展如果要接入 transport / automation，必须满足：
- 明确 capability declaration
- 明确 session ownership model
- 明确 shutdown / cleanup responsibility
- 明确 failure evidence recording
- 有独立回归验证

## 11. Security boundary

当前阶段的安全结论是：
- 插件应被视为受信扩展
- ProtoLink 不承诺不受信插件沙箱

因此：
- 未经审查的第三方插件不得默认启用
- 生产交付默认应关闭外部插件自动加载
- 启用插件应是显式动作，并留下配置证据

## 12. Compatibility policy

每个插件必须同时声明：
- `extension_api_version`
- `min_app_version`
- `max_app_version`（可选）

任何不兼容插件必须：
- 在发现阶段被拒绝
- 给出明确错误文案
- 留下结构化失败证据

## 13. Immediate engineering consequence

在 `PL-015` 完成前，不应直接开始实现任意运行时插件加载。

正确顺序是：
1. 先固定扩展契约
2. 已落地：manifest discovery / validation / audit / release-preflight gate
3. 再实现最小能力范围（优先 Class A）
4. 再接入运行时装载、验证与交付链

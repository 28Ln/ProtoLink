# ProtoLink Architecture

Last updated: 2026-04-14

## 1. 技术基线

- Language: Python 3.11
- UI: PySide6
- Packaging: `uv` + `pyproject.toml`
- Testing: pytest
- Platform focus: Windows desktop

## 2. 入口链路

正式入口链如下：

1. `src/protolink/__main__.py`
2. `src/protolink/app.py`
3. `src/protolink/core/bootstrap.py`
4. `src/protolink/ui/main_window.py`

CLI 与 GUI 共享同一套 workspace / settings / service bootstrap。

## 3. 分层

### UI Layer
- 主窗口与模块导航
- 具体面板（串口、Modbus、MQTT、TCP/UDP、自动化等）
- 只消费 snapshot 和用户动作，不直接承担 I/O

### Application Layer
- 会话生命周期编排
- 回放、规则、脚本、扫描、桥接等用例协调
- 将底层异常归一化为用户可见状态和结构化事件

### Core Layer
- 传输抽象
- 状态模型
- 配置与工作区模型
- 日志、导入导出、打包、协议解析、数据模型

### Transport Layer
- 串口、TCP、UDP、MQTT 适配器
- 产生 `TransportEvent`，不直接操作 UI

## 4. 关键状态模型

- `TransportKind`
- `ConnectionState`
- `TransportSession`
- 各 service `Snapshot`
- `StructuredLogEntry`
- `WorkspaceLayout`

约束：

- 原始字节为事实源
- UI 不直接做阻塞 I/O
- 连接状态迁移必须经过显式状态模型校验
- 工作区是配置、日志、抓包、导出的统一归属

## 5. 主数据流

### 传输与日志
`TransportAdapter.emit(...)`
-> `EventBus.publish(TransportEvent)`
-> `wire_transport_logging(...)`
-> `StructuredLogEntry`
-> `InMemoryLogStore` + `WorkspaceJsonlLogWriter`
-> `PacketInspectorState`

### UI 与状态
`UI action`
-> `Application service`
-> `Async runtime / adapter`
-> `TransportEvent`
-> `Snapshot update`
-> `UI refresh`

### 协议工作流
`Modbus panel`
-> 组包
-> 通过已连接 transport 发送
-> 日志与包分析台保留原始报文
-> 解析结果 / 寄存器监视复用同一条链路上下文

## 6. 异常流

- 底层传输异常先转为 `TransportEventType.ERROR`
- 应用服务维护 `last_error`
- UI 只显示归一化错误文案
- CLI 失败统一走 `ProtoLinkUserError` / `CliExitCode`
- 关键异常同时进入结构化日志与 failure evidence

## 7. 交付架构

ProtoLink 当前交付链路包含：

- workspace migration
- release preflight
- release bundle
- portable package
- distribution package
- installer-staging package
- installer package
- package verify / install / uninstall
- fresh-install validation

当前交付能力是：**bundled-runtime clean-machine runnable delivery**。  
当前未完成的是：**native signed Windows installer / binary line**。

## 8. 扩展边界

新增能力应优先沿以下边界扩展：

- 新传输：`core.transport` + `transports/*` + 对应 session service
- 新协议面板：复用 packet inspector / register monitor / replay 能力
- 新自动化能力：优先挂接 application service，而不是直接进 UI
- 新交付能力：优先在 `core.packaging` / `scripts` 中建立验证闭环
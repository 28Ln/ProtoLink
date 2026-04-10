# ProtoLink Architecture

## 1. 技术基线

- Language: Python 3.11
- UI: PySide6
- Packaging: `uv` + `pyproject.toml`
- Testing: pytest
- Platform focus: Windows desktop

之所以选 Python，而不是纯 Electron：

- 本项目核心是本地通讯、协议解析、自动化、设备调试，不是网页内容展示
- Python 对串口、协议解析、规则、脚本、数据处理更适合
- Windows 本地资源和后续驱动能力更容易收敛在一条技术栈内

## 2. 分层原则

ProtoLink 从第一天开始就按以下分层建设：

### UI Shell

- 主窗口
- 导航与工作区切换
- 面板布局
- 状态呈现

### Application Layer

- 用例编排
- 连接生命周期管理
- 命令执行
- 配置读写

当前已经开始落地的 application service 模式：

- `ConnectionSessionServiceBase`
- `MappedProfileSessionServiceBase`
- `SerialSessionService`
- `MqttClientSessionService`
- `MqttServerSessionService`
- `TcpClientSessionService`
- `TcpServerSessionService`
- `UdpSessionService`
- `PacketReplayExecutionService`
- 后台 asyncio runner
- 连接服务 runtime 懒启动（仅在 open/send/close/replay 执行时创建）
- UI 主线程回调调度器
- workspace-bound serial profile persistence
- CLI-facing `ProtoLinkUserError` + `CliExitCode` foundation

### Domain Layer

- 传输抽象
- 原始消息模型
- 协议帧模型
- 规则模型
- 设备画像

### Infrastructure Layer

- 串口适配器
- TCP/UDP/MQTT 适配器
- 文件系统与工作区
- 日志与导出

## 3. 关键架构约束

- 原始字节是唯一事实源，解析结果是派生视图
- 不允许 UI 线程承担 I/O 和重解析
- 传输层与协议层必须解耦
- 规则引擎与脚本引擎必须建立在统一消息模型上
- 所有配置都归属工作区，不散落在运行目录

## 4. 核心对象

ProtoLink 后续必须围绕以下对象统一建设：

- `WorkspaceLayout`
- `TransportConfig`
- `ConnectionSession`
- `RawMessage`
- `ProtocolFrame`
- `DeviceProfile`
- `RegisterPoint`
- `AutomationRule`
- `CaptureJob`

## 5. 首版模块地图

- Dashboard
- Serial Studio
- Modbus RTU Lab
- Modbus TCP Lab
- MQTT Client
- MQTT Server
- TCP Client
- TCP Server
- UDP Lab
- Packet Inspector
- Register Monitor
- Automation Rules
- Script Console
- Data Tools
- Network Tools

## 6. 工作区布局

ProtoLink 默认工作区布局如下：

```text
workspace/
  profiles/
  devices/
  rules/
  scripts/
  captures/
  exports/
  logs/
  plugins/
```

## 7. 当前代码骨架说明

当前正式代码已经实现了以下基础能力：

- 正式项目入口
- 工作区初始化与设置持久化
- 桌面主窗口骨架和模块清单
- 传输抽象与会话生命周期基线
- 统一结构化日志模型与原始字节保留基线
- 事件总线到日志存储、包检查器状态的基础联通
- workspace-backed `logs/transport-events.jsonl` 运行时日志落盘基线
- 包检查器状态模型与 dockable 消息控制台面板
- `src/protolink/transports/` 下的具体 transport adapter 落点，当前已实现串口与 TCP client
- `src/protolink/transports/` 下的具体 transport adapter 落点，当前已实现串口、TCP client、TCP server
- `src/protolink/transports/` 下的具体 transport adapter 落点，当前已实现串口、MQTT client、MQTT server、TCP client、TCP server、UDP
- `src/protolink/application/` 下已实现串口、MQTT client、MQTT server、TCP client、TCP server、UDP 会话编排服务
- `src/protolink/application/connection_service.py` 负责统一 open / close / send future handling、transport event state sync、dispatch、shutdown，以及 mapped profile persistence 复用
- 串口 / MQTT client / MQTT server / TCP client / TCP server / UDP UI 面板都通过服务层发起后台 I/O，不在 UI 线程直接执行 open/send/close
- 串口工作流状态保存在 `workspace/profiles/serial_studio.json`，用于 draft 和记忆化 preset
- MQTT client 工作流状态保存在 `workspace/profiles/mqtt_client.json`，用于 draft 和记忆化 preset
- MQTT server 工作流状态保存在 `workspace/profiles/mqtt_server.json`，用于 draft 和记忆化 preset
- TCP client 工作流状态保存在 `workspace/profiles/tcp_client.json`，用于 draft 和记忆化 preset
- TCP server 工作流状态保存在 `workspace/profiles/tcp_server.json`，用于 draft 和记忆化 preset
- UDP 工作流状态保存在 `workspace/profiles/udp_lab.json`，用于 draft 和记忆化 preset
- MQTT client / MQTT server 已具备 draft / preset 持久化
- `src/protolink/core/preset_profile_store.py` 与 `src/protolink/core/transport_profile_codec.py` 负责复用 serial / MQTT client / MQTT server / TCP client / TCP server / UDP 的 preset profile 存储模式
- `src/protolink/core/connection_state_model.py` 负责显式定义连接状态允许迁移关系
- `src/protolink/core/raw_packet_composer.py` 提供 bytes-first 原始报文草稿/预览状态
- `src/protolink/core/packet_replay.py` 提供基于结构化 transport 日志的 replay plan 构建与持久化
- `src/protolink/application/packet_replay_service.py` 提供 replay plan 的 active-transport dispatch 执行能力
- `src/protolink/ui/packet_console.py` 现已包含 replay 执行控制区（计划路径、目标通道、执行状态）以及可见行 replay plan 构建导出
- `src/protolink/core/modbus_rtu_parser.py` 提供 Modbus RTU 帧解析与 CRC 校验基线，并在 packet inspector 选中行展示
- `src/protolink/core/modbus_tcp_parser.py` 提供 Modbus TCP 帧解析与 MBAP 校验基线，并在 packet inspector 选中行展示
- `src/protolink/core/register_monitor.py` 提供寄存器监控的点位模型、缩放和字节序映射解码基线
- `src/protolink/application/register_monitor_service.py` + `src/protolink/ui/register_monitor_panel.py` 提供寄存器点位管理与手工寄存器字解码流程面板
- `src/protolink/core/device_scan.py` 提供 Modbus RTU/TCP 设备扫描的探测报文生成、响应判定和结果汇总基线
- `src/protolink/application/device_scan_execution_service.py` 提供设备扫描的活动会话发送接线与入站响应判定/汇总
- `src/protolink/core/auto_response.py` 提供 RAW/Modbus RTU/Modbus TCP 的自动应答规则匹配与响应动作选择基线
- `src/protolink/application/auto_response_runtime_service.py` 提供自动应答规则的运行时接线，将入站匹配结果回发到活动传输会话
- `src/protolink/core/rule_engine.py` + `src/protolink/application/rule_engine_service.py` 提供自动化规则的动作模型与编排执行基线
- `src/protolink/ui/automation_rules_panel.py` 提供自动化规则的最小工作面，用于保存、运行和删除运行时规则定义
- `src/protolink/core/automation_rule_profiles.py` 提供自动化规则的工作区持久化编解码
- `src/protolink/core/script_host.py` + `src/protolink/application/script_host_service.py` 提供脚本宿主抽象与内置 Python host 基线
- `src/protolink/core/timed_tasks.py` + `src/protolink/application/timed_task_service.py` 提供定时任务的规则调度基线
- `src/protolink/core/channel_bridge.py` + `src/protolink/application/channel_bridge_runtime_service.py` 提供通道桥接与可选脚本变换基线
- `src/protolink/core/preset_profile_store.py` 现使用原子临时文件替换与空文件回退，降低并发持久化损坏风险
- `src/protolink/core/errors.py` 负责 CLI 可见错误文案和退出码基线

## 8. 错误处理约束

- transport 层负责产生结构化 error event
- application service 负责维护用户可见的最近错误状态
- UI 层只显示已归一化的错误文本，不直接暴露原始 traceback
- 所有 transport failure 必须同时进入统一日志与对应功能面的局部状态

## 9. 导入导出约束

- 运行期事实源仍留在工作区原始目录（`captures/`、`logs/`、`profiles/`）
- `exports/` 目录只承担对外打包职责
- 每个导出包都必须附带 manifest，当前基线为 `protolink-export-v1`

这不是最终产品，而是受控起步点，目的是避免直接掉进参考代码的历史包袱。

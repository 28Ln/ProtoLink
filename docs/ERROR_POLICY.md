# ProtoLink Error Reporting Policy

## 1. Goals

ProtoLink 的错误处理必须同时满足：

- 不阻塞 UI
- 保留原始上下文
- 给用户可执行的反馈
- 能进入统一日志与包检查器

## 2. 分层要求

### Transport / Runtime Layer

- transport adapter 负责产生结构化错误事件
- 原始异常不直接弹窗
- 错误必须带上 session / target / transport kind 上下文

### Application Service Layer

- 把底层异常整理成用户可见状态
- 维护最近一次可见错误，例如 `last_error`
- 不吞掉 transport error；必须继续写入统一日志

### UI Layer

- 就地显示当前模块相关错误
- 不在后台线程直接操作控件
- 错误显示不替代日志，二者同时存在

### CLI / Import-Export Layer

- CLI 失败必须收敛到稳定退出码
- 用户可预期错误优先转成 `ProtoLinkUserError`
- 导入导出辅助函数的参数校验应尽量在执行前失败，而不是落到深层 traceback

## 3. 当前落地策略

目前 ProtoLink 已建立以下最小闭环：

- `TransportEventType.ERROR` -> `StructuredLogEntry(category='transport.error')`
- `PacketInspectorState` 持续接收这些日志
- `SerialSessionService.snapshot.last_error` 暴露当前串口会话的最近错误
- `SerialStudioPanel` 在控制面板底部显示最近错误
- `TcpClientSessionService.snapshot.last_error` 暴露当前 TCP client 会话的最近错误
- `TcpClientPanel` 在控制面板底部显示最近错误
- `TcpServerSessionService.snapshot.last_error` / `UdpSessionService.snapshot.last_error` 也使用同一策略暴露最近错误
- `TcpServerPanel` / `UdpPanel` 在控制面板底部显示最近错误
- `MqttClientSessionService.snapshot.last_error` / `MqttServerSessionService.snapshot.last_error` 也使用同一策略暴露最近错误
- `MqttClientPanel` / `MqttServerPanel` 在控制面板底部显示最近错误
- `CliExitCode` 统一 CLI 成功 / 用户错误 / 运行时错误 / GUI 依赖缺失退出码
- `normalize_export_extension()` 对导出后缀做用户态校验并抛出 `ProtoLinkUserError`
- `uv run protolink --create-export-scaffold ...` 已使用同一错误策略返回用户态文案与退出码

## 4. 消息格式原则

- 面向用户的文本优先说明动作失败点：如 `Open failed: ...`
- 底层异常文本可附在后面，但不能替代动作语义
- 错误消息必须足够短，能直接放进状态栏、表单或日志摘要
- CLI 输出必须尽量保持单行稳定格式，便于脚本调用方识别

## 5. 后续扩展要求

- TCP/UDP/MQTT service 复用相同的 `last_error + transport.error log` 模式
- 对需要恢复动作的错误补充建议，例如端口占用、权限不足、目标不可达
- 为 CLI 失败场景补充非零退出码和一致文案
- 为导入导出流程补充文件路径与恢复建议

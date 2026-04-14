# ProtoLink Error Policy

Last updated: 2026-04-14

## 目标

ProtoLink 的错误处理必须满足：

- 不阻塞 UI
- 保留运行证据
- 给出用户可执行的反馈
- 进入统一日志与 failure evidence

## 分层要求

### Transport Layer
- 负责产生结构化错误事件
- 不直接操作 UI
- 错误必须带 transport / session / target 上下文

### Application Layer
- 将底层异常归一化为用户可见状态
- 维护 `last_error`
- 不吞掉应进入统一日志的异常

### UI Layer
- 只显示归一化错误文本
- 不直接暴露原始 traceback
- 错误提示不替代结构化日志

### CLI Layer
- 用户态错误优先转为 `ProtoLinkUserError`
- 用统一退出码表达结果
- CLI 错误必须进入日志与 failure evidence

## 当前落地点

- `TransportEventType.ERROR` -> `StructuredLogEntry(category='transport.error')`
- service snapshot 暴露 `last_error`
- workspace 下保留 `transport-events.jsonl`
- runtime / config failure evidence 以 jsonl 保存
- CLI 使用 `CliExitCode` 统一退出码

## 工程要求

- 新增 transport / service / CLI 命令时，必须同时定义：
  - 用户可见错误文案
  - 结构化日志类别
  - 是否需要 failure evidence
- 关闭、清理、安装、卸载等路径也必须考虑异常证据留存
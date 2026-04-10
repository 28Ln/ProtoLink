# ProtoLink Roadmap

## M0 Foundation

### 目标

把项目从“参考分析”推进到“正式工程可持续开发”。

### 交付物

- 正式工程骨架
- 工作区模型
- 配置加载基础
- 主窗口和导航基线
- 文档、验证路径、任务台账

### 退出条件

- 可启动
- 可验证
- 可继续迭代

## M1 Transport Core

### 目标

打通基础传输层，形成统一连接生命周期。

### 范围

- Serial
- TCP Client
- TCP Server
- UDP
- MQTT Client
- MQTT Server

### 退出条件

- 至少 3 个传输模块达到可连接、可收发、可记录日志
- 统一日志模型可复用

## M2 Modbus Workbench

### 目标

以 Modbus RTU 为主线，建立第一个真正可交付的协议工作流。

### 范围

- 自定义帧
- 设备搜索
- 数据监控
- 自动应答
- 帧解析
- 导入导出

### 退出条件

- 完成 Modbus RTU 端到端流程
- 建立 Modbus TCP 的复用边界

## M3 Automation

### 目标

把 ProtoLink 从工具升级为平台。

### 范围

- 规则引擎
- 脚本宿主
- 通道联动
- 定时任务
- 报文回放

### BL-003 验收边界

- Script Console 只能通过当前受控脚本宿主进入 UI，默认保持 Python builtins 白名单，不扩大文件、模块导入或网络能力。
- Script Console 必须展示 stdout、result、error 和运行状态，并在任何定时任务、通道桥接、自动化规则联动进入 UI 前提供可见停止/禁用路径。
- Data Tools 作为独立工具面进入，不依赖当前 transport session；编码转换、校验和、格式化等能力必须先有 headless 单元测试。
- Network Tools 采用 read-only-first 策略；涉及系统或网络配置写操作时，必须有明确权限边界、审计输出和回滚说明。
- BL-003 不阻塞 M4 release-preparation；只有当 BL-002 干净退出后才进入实现主线。

### BL-003 验证命令

```powershell
uv run pytest tests/test_script_host_service.py tests/test_rule_engine_service.py tests/test_channel_bridge_runtime_service.py -q
uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q
```

## M4 Delivery

### 目标

让项目进入可打包、可测试、可交付状态。

### 范围

- 打包
- 升级策略
- 发布清单
- 回归清单
- 基础 smoke test

# ProtoLink 2.0 Dependency Audit

Last updated: 2026-04-16

## 1. Purpose

本文审计当前 ProtoLink 2.0 阶段版本所依赖的运行时、开发、交付与环境工具，说明：

- 它们为什么存在
- 是否必要
- 风险是什么
- 是否与当前目标匹配

## 2. Source of Truth

当前 Python 依赖的正式来源是：

- `pyproject.toml`

当前额外环境依赖的正式来源是：

- 打包脚本
- 验证脚本
- Windows 平台运行前提

## 3. Python Runtime Dependencies

### `amqtt>=0.11.3,<0.12`

- Role: MQTT 服务端 / 相关消息能力
- Category: Runtime
- Required now: Yes
- Why it exists:
  - 支撑 MQTT server / broker 相关能力
- Risk:
  - 运行时复杂度提升
  - 体积增加
- Fit for 2.0:
  - 匹配当前目标

### `paho-mqtt>=2.1,<3.0`

- Role: MQTT 客户端能力
- Category: Runtime
- Required now: Yes
- Why it exists:
  - 支撑 MQTT client 能力
- Risk:
  - 外部协议栈版本兼容性
- Fit for 2.0:
  - 匹配当前目标

### `pyserial>=3.5,<4.0`

- Role: 串口能力
- Category: Runtime
- Required now: Yes
- Why it exists:
  - 支撑 Serial Studio 与串口调试链
- Risk:
  - 平台 / 驱动差异
- Fit for 2.0:
  - 匹配当前目标

## 4. Optional Python Dependencies

### `PySide6-Essentials>=6.8,<7.0`

- Role: GUI
- Category: Optional / UI
- Required now:
  - 对 GUI 必需
  - 对 headless CLI 非必需
- Why it exists:
  - 支撑 Windows-first 桌面界面
- Risk:
  - 体积较大
  - 打包目录深、资源多
- Fit for 2.0:
  - 匹配当前目标，但也是交付体积的主要来源之一

### `pytest>=8.3,<9.0`

- Role: 回归测试
- Category: Dev
- Required now: 仅开发/验证
- Why it exists:
  - 当前全量验证体系基于 pytest
- Risk:
  - 不应进入正式运行时交付
- Fit for 2.0:
  - 匹配当前目标

## 5. Build / Packaging Dependencies

### `hatchling>=1.27.0`

- Role: build backend
- Category: Build
- Required now: Yes
- Why it exists:
  - 支撑 wheel / sdist 构建
- Risk:
  - 较低
- Fit for 2.0:
  - 匹配当前目标

### `uv`

- Role: 环境管理、运行、构建、脚本入口
- Category: Tooling
- Required now: Yes
- Why it exists:
  - 当前所有正式验证命令以 `uv run` / `uv build` 为主
- Risk:
  - 文档与 CI 必须保持一致
- Fit for 2.0:
  - 匹配当前目标

## 6. External Environment / Platform Dependencies

### Windows

- Role: 当前主要目标平台
- Required now: Yes
- Why it exists:
  - 项目明确 Windows-first
- Risk:
  - 平台锁定
- Fit for 2.0:
  - 匹配当前目标

### PowerShell / CMD / `msiexec`

- Role: 安装与验证脚本链
- Category: Environment
- Required now: Yes
- Why it exists:
  - release-staging / install / uninstall 验证依赖这些原生命令
- Risk:
  - 脚本可移植性差
- Fit for 2.0:
  - 匹配当前 Windows-first 目标

### WiX Toolset v4

- Role: native installer scaffold / MSI build 路线
- Category: Optional external toolchain
- Required now:
  - 对 probe / planning 路线需要
  - 对当前 bundled release line 不必需
- Why it exists:
  - `PL-014` 主线需要
- Risk:
  - 当前本机缺失，正式发布 lane 未闭环
- Fit for 2.0:
  - 匹配当前主线，但仍未成为稳定环境前提

### SignTool

- Role: MSI 签名验证
- Category: Optional external toolchain
- Required now:
  - 对 signed native lane 需要
  - 对当前 bundled release line 不必需
- Why it exists:
  - `PL-014` 目标要求签名链
- Risk:
  - 当前本机缺失，签名发布线未闭环
- Fit for 2.0:
  - 匹配主线，但当前仅到 probe

## 7. Current Audit Conclusion

当前依赖结论：

- Python 运行时依赖数量不大，基本与已交付功能匹配
- 体积压力主要来自 GUI runtime（PySide6）与 bundled runtime 本身
- native installer 相关外部工具是当前主线推进需要，但**不是当前 bundled release 基线的硬前提**
- 当前依赖体系整体可接受，但仓库应继续区分：
  - 正式运行依赖
  - 可选 GUI 依赖
  - 开发/测试依赖
  - 原生安装器外部工具链

## 8. Recommended Follow-up

1. 在不改功能边界的前提下继续评估第二轮 package slimming
2. 保持文档明确区分 bundled baseline 与 native installer probe lane
3. 避免把 WiX / SignTool 写成“当前正式运行前提”
4. 后续若切 native installer 正式发布线，再补更严格的 toolchain governance


# ProtoLink 2.0 Features

Last updated: 2026-04-16

## 1. Purpose

本文说明 ProtoLink 当前 2.0 阶段收尾版本的真实功能范围。

## 2. Transport Capabilities

- Serial Studio
  - 串口连接与调试
- TCP Client
  - TCP 客户端连接与调试
- TCP Server
  - TCP 服务端监听与交互
- UDP Lab
  - UDP 报文调试
- MQTT Client
  - 订阅 / 发布 / 客户端连接
- MQTT Server
  - 服务端 / broker 侧验证能力

## 3. Protocol Capabilities

- Modbus RTU Lab
  - 请求配置
  - 预览与解析
  - 回放与导出
- Modbus TCP Lab
  - 请求配置
  - 预览与解析
  - 回放与导出

## 4. Shared Runtime Capabilities

- Packet Console / Packet Inspector
  - 报文分析
  - 报文构建
  - 报文回放
- Register Monitor
  - 点位配置
  - 解码预览
- Data Tools
- Network Tools

## 5. Automation Capabilities

- Automation Rules
- Auto Response Runtime
- Timed Tasks
- Channel Bridge Runtime
- Device Scan Execution
- Script Console / Script Host

注意：

- 当前脚本能力是受控宿主，不是不受信沙箱。

## 6. Workspace and Evidence

当前已具备：

- workspace 归属
- structured log
- failure evidence
- import/export manifest

## 7. Delivery and Validation

当前已具备：

- release bundle
- portable package
- distribution package
- installer package
- install / uninstall / verify
- fresh-install validation
- release-staging validation
- soak validation
- GUI formal audit

## 8. Extension Capability

当前已具备：

- plugin manifest audit
- descriptor registry
- loading plan
- explicit Class A runtime loading
- preflight runtime gate

当前未具备：

- Class B review workflow
- Class C runtime execution
- lifecycle governance
- 正式 SDK

## 9. Explicit Non-Goals

当前版本不承诺：

- signed native installer 已正式发布
- 云端账号 / SaaS
- Linux / macOS 优先级交付
- 不受信脚本沙箱
- Class B / Class C 扩展运行治理闭环


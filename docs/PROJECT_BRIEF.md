# ProtoLink Project Brief

Last updated: 2026-04-14

## 项目目标

ProtoLink 是一个面向 Windows 本地场景的工业通信与协议调试平台，目标是把常见现场联调能力收敛到一个可维护、可验证、可交付的工程基线中。

## 目标用户

- 设备联调工程师
- 工控协议开发者
- 自动化测试工程师
- 现场实施与售后支持人员

## 当前覆盖范围

- 传输：Serial / TCP Client / TCP Server / UDP / MQTT Client / MQTT Server
- 协议：Modbus RTU / Modbus TCP 基础调试链路
- 共享能力：报文分析、回放、寄存器监视、数据工具、网络诊断
- 自动化：自动应答、规则引擎、脚本控制台、定时任务、通道桥接
- 交付：工作区、导出、release bundle、portable/distribution/installer package、安装/卸载验证

## 非目标

当前阶段不做：

- Web SaaS / 云端账号体系
- Linux / macOS 优先级交付
- 移动端控制台
- 非受信脚本执行环境

## 成功标准

ProtoLink 的当前工程成功标准是：

- 应用可以稳定启动并初始化工作区
- 关键传输链路与 Modbus 调试链路具备自动化回归
- 日志、异常、配置、导出具备统一约束
- 打包、安装、fresh-install、release-staging 有可执行验证
- 新接手开发者可以基于现有文档独立运行、验证并继续迭代
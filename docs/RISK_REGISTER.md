# ProtoLink Risk Register

Last updated: 2026-04-15

## 风险清单

### R-001 Bundled Runtime 体积仍偏大
- Level: High
- Category: Delivery
- Trigger: 发布包继续扩张或引入更多环境级依赖
- Impact: 交付体积、下载成本、安装时间、维护成本上升
- Current control: 已完成第一轮 package slimming，并具备 verify/install 回归
- Evidence: 当前 portable / installer 包仍以 bundled runtime 为核心
- Next action: 在 `PL-014` 中把原生安装器路线作为下一阶段目标
- Residual risk: Medium

### R-002 尚未具备原生签名安装器
- Level: Medium
- Category: Delivery
- Trigger: 对外正式发布或企业内部分发要求提高
- Impact: 安装信任度、系统兼容性、交付口径受限
- Current control: 现有 installer package 可安装、可验证、可卸载
- Evidence: 当前交付能力仍是 bundled-runtime clean-machine runnable delivery
- Next action: 在 `PL-014` 中推进 native installer / signing 路线
- Residual risk: Medium

### R-003 脚本能力不是不受信沙箱
- Level: High
- Category: Security / Runtime Boundary
- Trigger: 将脚本能力误用为通用扩展执行环境
- Impact: 安全边界被误判，导致风险承诺过度
- Current control: 仅支持受控脚本宿主，文档明确非目标
- Evidence: 当前仅做受控 builtins 与超时，不提供系统级隔离
- Next action: 在 handoff、README、架构文档中持续明确边界
- Residual risk: Medium

### R-004 关闭 / 清理路径的异常证据仍需继续扩展
- Level: Medium
- Category: Observability
- Trigger: 资源释放、关闭、卸载路径出现异常
- Impact: 问题复盘与交付诊断困难
- Current control: 已有 runtime/config failure evidence 基线；release-preflight 已拦截记录到的 service close failures
- Evidence: 关键 session service 的 shutdown / close 失败已进入统一 evidence，但安装/卸载与更多清理路径仍需继续覆盖
- Next action: 在后续主线中继续扩展交付链与清理路径 evidence
- Residual risk: Medium

### R-005 插件 / 扩展接入边界仍未进入运行时装载阶段
- Level: Medium
- Category: Extensibility
- Trigger: 新增协议、插件或外部扩展需求进入主线
- Impact: 扩展实现分叉，维护成本上升
- Current control: 已具备正式 `EXTENSION_CONTRACT` 文档、workspace/plugins manifest discovery、静态校验与 release-preflight 阻断
- Evidence: 当前仅做到 manifest discovery / validation / audit；尚未进入受控运行时装载、descriptor contract 与 SDK 化阶段
- Next action: 在 `PL-015` 中推进 registry / descriptor / loading boundary / enforcement
- Residual risk: Medium

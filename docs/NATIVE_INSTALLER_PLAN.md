# ProtoLink Native Installer and Signing Plan

Last updated: 2026-04-14

## 1. Purpose

本文件定义 ProtoLink 从当前 bundled-runtime 交付形态，向 Windows 原生安装器与签名交付形态演进的正式路线。

本文件的作用是：

- 明确目标交付形态
- 明确切换条件
- 明确验证策略
- 明确回退边界

它不是实现记录，而是 `PL-014` 的正式计划基线。

## 2. Current baseline

截至 `0.2.2`，ProtoLink 当前稳定交付形态为：

- release bundle
- portable package
- distribution package
- installer package

其本质是：**bundled Python runtime + application payload + install / verify / uninstall scripts**。

当前基线已经满足：

- clean-machine runnable
- release-staging 可验证
- fresh-install 可验证
- install / uninstall 闭环

因此，native installer 路线不是为了解决“能不能交付”，而是为了解决：

- 更正式的 Windows 分发形态
- 更清晰的企业内分发与信任链
- 更好的安装/升级/卸载体验
- 更明确的签名交付边界

## 3. Primary technical route

### Primary route: WiX Toolset 4 + MSI

ProtoLink 选择 **WiX Toolset 4 + MSI** 作为原生安装器主路线。

选择理由：

1. **Windows 企业交付兼容性最好**
   - MSI 是企业内分发、静默安装、策略部署最常见的标准形态。

2. **适合当前 bundled-runtime 模式**
   - ProtoLink 当前已经能稳定生成安装目录内容，MSI 更适合把这套目录结构固化成正式安装器，而不是重写应用运行模型。

3. **升级/卸载模型清晰**
   - WiX 能明确管理 ProductCode / UpgradeCode / MajorUpgrade 策略。

4. **签名链成熟**
   - MSI 与后续可选 bootstrapper EXE 都可走标准 Authenticode 签名。

### Deferred alternatives

以下路线暂不作为当前主路线：

- **MSIX**
  - 不是当前主路线。原因是其约束更强，当前阶段不优先把 ProtoLink 的本地工业调试能力迁移到 MSIX 约束模型。

- **Inno Setup / NSIS**
  - 可作为战术备选，但不作为主路线。原因是企业标准化、升级策略与长期可维护性不如 WiX/MSI 主路线稳定。

## 4. Target deliverable shape

ProtoLink 的目标原生交付形态定义为：

### Required artifact
- signed MSI installer

### Optional artifact
- signed bootstrapper EXE（后续按需引入，不是 `PL-014` 必需）

### Packaging model

MSI 初期仍沿用当前 bundled-runtime 目录结构，不立即改变应用运行模型：

- bundled runtime
- `sp/` runtime site-packages
- ProtoLink app payload
- launcher / install assets

也就是说：**先切交付形态，再切运行模型**。

## 5. Signing model

### Required signing method
- Windows Authenticode signing

### Required scope
- MSI installer
- 若引入 bootstrapper EXE，则 bootstrapper 也必须签名

### Required supporting pieces
- 可用的代码签名证书
- 时间戳服务（RFC3161 或同等方案）
- 在 CI 或 release lane 中可执行的签名步骤

### Signing policy

在证书、时间戳服务、签名命令链未稳定之前：

- 不切换默认发布路线
- 继续以 `0.2.x` bundled-runtime installer package 作为正式交付基线

## 6. Cutover conditions

ProtoLink 只有在以下条件全部满足时，才允许从当前 installer package 路线切到 native installer 路线：

1. **Payload determinism**
   - 当前安装目录内容可稳定、可重复、可比对。

2. **Versioned install lifecycle**
   - 升级、覆盖安装、卸载策略已经定义。

3. **Silent install support**
   - 支持无人值守安装与卸载。

4. **Signing readiness**
   - 证书、时间戳、签名命令链准备完成。

5. **Verification path exists**
   - native installer 拥有对应的 clean-machine / install / uninstall / headless-summary 验证链。

6. **Rollback path is preserved**
   - 现有 installer package 仍保留为回退基线。

## 7. Verification strategy

native installer 路线至少要具备以下验证：

### Build verification
- WiX source generation成功
- MSI build 成功
- 签名前产物结构正确

### Signature verification
- `Get-AuthenticodeSignature` 或同等级验证通过

### Install verification
- clean-machine / clean-VM 安装成功
- 安装后能运行 `protolink --headless-summary`

### Upgrade verification
- 从旧版本安装到新版本的升级行为明确

### Uninstall verification
- 卸载后主要文件、快捷方式、注册项行为符合预期

### Release lane verification
- 与现有 `verify_release_staging.py` 对齐，新增 native installer lane

## 8. Rollback boundary

在 native installer 路线完全成熟之前：

- 当前 installer package 路线始终保留
- bundled-runtime clean-machine runnable delivery 继续作为正式回退基线

回退触发条件包括：

- MSI build 不稳定
- 签名链不稳定
- 升级/卸载验证失败
- 安装后 headless-summary 不通过

## 9. Non-goals

当前阶段不做：

- 自动更新器
- 多平台安装器统一
- 把应用改造成不带 bundled runtime 的系统 Python 依赖安装
- 以 MSIX 作为第一优先级形态

## 10. PL-014 delivery outputs

`PL-014` 最少产出应包括：

1. 本文件（installer route 计划）
2. 切换条件与回退边界
3. 验证矩阵接入点
4. 下一阶段实现任务入口

## 11. Next implementation handoff

`PL-014` 完成后，下一阶段实现工作至少要回答：

- WiX source 如何从现有 install payload 生成
- UpgradeCode / ProductCode / versioning 策略
- 签名命令链如何进入 CI / release lane
- native installer 验证脚本如何接入现有验证体系

# ProtoLink Native Installer and Signing Plan

Last updated: 2026-04-16

## 1. Purpose

本文件定义 ProtoLink 从当前 bundled-runtime 交付形态，向 Windows 原生安装器与签名交付形态演进的正式路线。

本文件的作用是：

- 明确目标交付形态
- 明确切换条件
- 明确验证策略
- 明确回退边界

它不是实现记录，而是 `PL-014` 的正式计划基线。

与本文配套的机器可读真值文件是：

- `docs/NATIVE_INSTALLER_CUTOVER_POLICY.json`

## 2. Current baseline

截至 `0.2.5`，ProtoLink 当前稳定交付形态为：

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

## 5. Native installer scaffold contract

WiX/native installer 实现进入代码面之前，必须先形成一个 **native installer scaffold** CLI 接口，用于把当前已验证的 installer payload 映射成可继续加工的 WiX/MSI authoring scaffold。

### Current status

当前 `0.2.5` CLI 基线已经暴露：

- `--build-native-installer-scaffold`
- `--verify-native-installer-scaffold`
- `--verify-native-installer-toolchain`
- `--build-native-installer-msi`
- `--verify-native-installer-signature`

### Required role

一旦该接口落地，它必须承担以下职责：

1. **从已验证 payload 出发**
   - 输入应基于现有 installer/distribution payload，而不是重新发明第二套安装内容来源。

2. **生成可审计 scaffold**
   - 输出必须是可检查、可比对、可复用的 WiX authoring scaffold，而不是直接隐藏式构建 MSI。

3. **不越过签名与发布门禁**
   - scaffold 命令只负责生成原生安装器工程骨架，不应隐式执行签名、发布或替换正式交付线。

4. **进入正式文档与真值校验**
   - 命令出现在 CLI 后，必须同步进入 `README.md`、`docs/VALIDATION.md`、`docs/RELEASE_CHECKLIST.md`。
   - `scripts/verify_canonical_truth.py` 必须能校验这些文档是否包含**精确命令名**。

### Required outputs

该接口的最小输出应包括：

- scaffold 根目录
- WiX source / template 文件
- payload 到安装目录的映射说明
- 版本、产品标识、升级策略的占位参数
- 生成记录或 manifest（用于后续 review / verify）
- lifecycle / identity contract，至少覆盖：
  - `target_arch`
  - `install_scope`
  - `install_dir_name`
  - `product_code_policy`
  - `upgrade_strategy`
  - `downgrade_error_message`
  - `silent_install_command`
  - `silent_uninstall_command`
  - `checksums` covering `ProtoLink.wxs` / `ProtoLink.Generated.wxi` / payload included entries

### Minimum acceptance

在 `PL-014` 内，该接口至少要满足：

- 能在 `uv run protolink --help` 中被发现
- 能被正式文档引用
- 能被 canonical truth 检查
- 不破坏当前 bundled-runtime 发布链
- `--verify-native-installer-scaffold` 会校验 manifest、WiX source 与 WiX include 在 lifecycle / identity contract 上保持一致
- `--verify-native-installer-scaffold` 会校验 included entries checksum，不接受仅凭文件存在通过

### Toolchain verification

当前 CLI 还必须提供：

- `--verify-native-installer-toolchain`

它的职责是：

- 检测当前机器上的 `wix` / `wix.exe`
- 检测当前机器上的 `signtool` / `signtool.exe`
- 输出结构化 JSON，而不是依赖人工阅读 stderr
- 给出推荐 build / sign / verify 命令

### MSI build and signature verification

当前 CLI 还必须提供：

- `--build-native-installer-msi`
- `--verify-native-installer-signature`

职责：

- `--build-native-installer-msi`
  - 基于已验证 scaffold 调用 WiX Toolset 构建 MSI
  - 在缺失 WiX 时返回稳定用户态错误
  - 输出结构化 JSON

- `--verify-native-installer-signature`
  - 基于 `signtool verify /pa /v` 校验 MSI 签名
  - 在缺失 SignTool 或签名无效时返回稳定用户态错误
  - 输出结构化 JSON

## 6. Signing model

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

### Current gate split

- 当前 bundled-runtime release gate 仍以 `verify_release_staging.py`、`verify_dist_install.py`、`run_soak_validation.py`、`uv build` 为正式门禁。
- `python scripts/verify_native_installer_lane.py` 在当前阶段只承担 probe truth，不把缺失 WiX / SignTool 直接升级为 bundled release blocker。
- 只有在显式启用 `--require-toolchain` 或 `--require-signed` 时，native installer lane 才进入 cutover gate 语义。
- `python scripts/verify_native_installer_lane.py --receipt-file <path>` 可把当前 lane truth 落盘为正式 JSON receipt。
- `build_release_deliverables.py` 会把 `native-installer-lane-receipt.json` 与 `deliverables-manifest.json` 一起写入 `dist/deliverables/`，作为阶段性交付 evidence。
- `docs/NATIVE_INSTALLER_CUTOVER_POLICY.json` 提供签名 / 时间戳 / 审批 / 回滚要求的机器可读真值；`verify_native_installer_lane.py`、`build_release_deliverables.py` 与 `verify_release_deliverables.py` 必须与其保持一致。
- `verify_native_installer_lane.py` 的结构化输出必须持续说明：
  - `current_canonical_release_lane`
  - `native_installer_lane_phase`
  - `blocking_items`
  - `next_action`

## 7. Cutover conditions

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

### Controlled approval flow

进入 native installer cutover 决策前，至少执行以下顺序：

1. 先跑完 bundled-runtime 正式发布门禁，并保留当前 installer package 作为回退产物。
2. 运行 scaffold / toolchain / MSI build / signature verify，确认 native installer lane 已达到 signed-ready。
3. 使用已批准的代码签名证书与已批准的 RFC3161 时间戳服务完成签名。
4. 记录 release owner 审批与签名操作审批，确保签名来源、证书使用人与时间戳服务可追溯。
5. 在 clean-machine 或 clean-VM 上完成 install / uninstall / `protolink --headless-summary` 验证后，才允许进入 cutover。

## 8. Verification strategy

native installer 路线至少要具备以下验证：

### Build verification
- native installer scaffold 命令已纳入 CLI help、README、validation 与 release checklist
- `--verify-native-installer-toolchain` 可输出结构化结果
- `--verify-native-installer-scaffold` 可校验 lifecycle / identity contract，而不只是文件存在与 checksum
- WiX source generation 成功
- MSI build 成功
- 签名前产物结构正确

### Signature verification
- `Get-AuthenticodeSignature` 或同等级验证通过
- `signtool verify /pa /v` 通过

### Install verification
- clean-machine / clean-VM 安装成功
- 安装后能运行 `protolink --headless-summary`

### Upgrade verification
- 从旧版本安装到新版本的升级行为明确

### Uninstall verification
- 卸载后主要文件、快捷方式、注册项行为符合预期

### Release lane verification
- 与现有 `verify_release_staging.py` 对齐，新增 native installer lane

## 9. Rollback boundary

在 native installer 路线完全成熟之前：

- 当前 installer package 路线始终保留
- bundled-runtime clean-machine runnable delivery 继续作为正式回退基线

回退触发条件包括：

- MSI build 不稳定
- 签名链不稳定
- 升级/卸载验证失败
- 安装后 headless-summary 不通过

## 10. Non-goals

当前阶段不做：

- 自动更新器
- 多平台安装器统一
- 把应用改造成不带 bundled runtime 的系统 Python 依赖安装
- 以 MSIX 作为第一优先级形态

## 11. PL-014 delivery outputs

`PL-014` 最少产出应包括：

1. 本文件（installer route 计划）
2. native installer scaffold contract
3. `--build-native-installer-scaffold`
4. `--verify-native-installer-scaffold`
5. `--verify-native-installer-toolchain`
6. `--build-native-installer-msi`
7. `--verify-native-installer-signature`
8. 切换条件与回退边界
9. 验证矩阵接入点
10. 下一阶段实现任务入口

## 12. Next implementation handoff

`PL-014` 完成后，下一阶段实现工作至少要回答：

- native installer scaffold 的正式 flag、输入、输出与目录布局
- WiX source 如何从现有 install payload 生成
- UpgradeCode / ProductCode / versioning 策略
- 签名命令链如何进入 CI / release lane
- native installer 验证脚本如何接入现有验证体系


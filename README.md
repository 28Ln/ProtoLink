# ProtoLink

ProtoLink 是一个面向 Windows 本地场景的工业通信、协议调试与自动化工作台。

## 项目定位

ProtoLink 的目标不是拼接多个调试工具，而是提供一套可长期维护的桌面工程基线，统一承载：

- 串口、TCP Client、TCP Server、UDP、MQTT Client、MQTT Server
- Modbus RTU / Modbus TCP 调试流程
- 报文分析、回放、寄存器监视
- 自动化规则、自动应答、脚本控制台、定时任务、通道桥接
- 工作区、日志、导出、打包、安装与验证链路

## 当前阶段基线（2026-04-16）

- `uv run python scripts/run_full_test_suite.py` -> `373 passed`
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py --artifact-version 0.2.5` -> passed
- 当前阶段版本：`0.2.5`
- Formal baseline freeze: `PL-012` completed
- Delivery hardening baseline: `PL-013` completed
- Current canonical mainline: `PL-014` Native Installer and Signing Path

## Native installer scaffold and CLI surface

当前 CLI 基线已暴露：
- `--build-native-installer-scaffold`
- `--verify-native-installer-scaffold`
- `--verify-native-installer-toolchain`
- `--build-native-installer-msi`
- `--verify-native-installer-signature`

这些命令已经成为正式 CLI surface，必须同步进入：
- `README.md`
- `docs/NATIVE_INSTALLER_PLAN.md`
- `docs/VALIDATION.md`
- `docs/RELEASE_CHECKLIST.md`

当前 scaffold contract 已额外覆盖：
- `target_arch`
- `install_scope`
- `install_dir_name`
- `product_code_policy`
- `upgrade_strategy`
- `silent_install_command` / `silent_uninstall_command`
- `checksums` for `ProtoLink.wxs` / `ProtoLink.Generated.wxi` / payload included entries

当前 release deliverables 还会额外产出：
- `deliverables-manifest.json`
- `native-installer-lane-receipt.json`
- `native-installer-cutover-evidence.json`

## 快速开始

```powershell
uv sync --python 3.11 --extra dev
uv run protolink --headless-summary
uv run python scripts/run_full_test_suite.py
uv sync --python 3.11 --extra dev --extra ui
uv run protolink
```

## 常用验证命令

```powershell
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 373
uv run python scripts/run_targeted_regressions.py --suite all
uv run python scripts/audit_gui_layout.py --output-dir dist\\gui-audit\\latest
uv run protolink --audit-plugin-manifests
uv run protolink --list-extension-descriptors
uv run protolink --plan-extension-loading
uv run protolink --load-enabled-extensions
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables
uv run python scripts/verify_release_deliverables.py --target-dir dist\\deliverables
python scripts/verify_dist_install.py --artifact-version 0.2.5
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

- `python scripts/verify_native_installer_lane.py` 默认输出 readiness probe；切换为发布门禁时使用 `--require-toolchain` 或 `--require-signed`。
- `python scripts/run_soak_validation.py` 在使用 `--require-all-ready` 时才作为长稳 gate，并输出 `cycle_ready`、`failing_cycles`、`total_duration_ms` 证据。
- `uv run python scripts/run_full_test_suite.py` 是当前正式 full-suite 真值入口；避免直接依赖单次 `pytest -q` 进程退出码。
- `uv run protolink --audit-plugin-manifests` 会审计 `workspace/plugins/*/manifest.json`，并把 invalid manifest 进入 release-preflight 阻断。
- `uv run protolink --list-extension-descriptors` 会列出当前工作区通过静态校验的扩展 descriptor registry。
- `uv run protolink --plan-extension-loading` 会结合 `registry.json` 给出受控装载计划，并标记 `eligible_for_loading` / `review_required` / `blocked_high_risk` / `blocked_registry_invalid` 等状态。
- `uv run protolink --load-enabled-extensions` 只会显式执行 enabled 且 `effective_state=eligible_for_loading` 的 Class A `register()`；Class B / Class C 不会被该入口自动执行。
- `uv run protolink --release-preflight` 现在会把 enabled Class A runtime load 结果纳入正式门禁，并在 `load_failed` 时留下结构化 failure evidence。
- `uv run protolink --verify-native-installer-scaffold` 现在会校验 native installer 的 lifecycle contract，而不只是文件存在与校验和。
- `uv run protolink --verify-native-installer-scaffold` 现在还会校验 `ProtoLink.wxs`、`ProtoLink.Generated.wxi` 与 payload 的 included-entry checksums。
- `uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables` 现在会写出顶层 `deliverables-manifest.json` 与 `native-installer-lane-receipt.json`。
- `uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables` 现在也会归档 `native-installer-cutover-evidence.json`。
- `uv run python scripts/verify_release_deliverables.py --target-dir dist\\deliverables` 会复核 deliverables manifest、archive checksums、package verifiers 与 native lane receipt 一致性。
- `python scripts/verify_native_installer_lane.py` 现在会额外输出 `policy_ready` 与 `policy_status`，把 signing / timestamp / approvals / rollback / clean-machine validation 拆成分节状态。
- `python scripts/verify_native_installer_lane.py --cutover-evidence-file <path>` 可显式提供 approvals / rollback / clean-machine validation evidence。

## 仓库结构

```text
src/protolink/   应用代码（入口、核心、应用服务、传输、UI）
tests/           pytest 回归与验收测试
scripts/         交付验证与工程辅助脚本
docs/            正式工程文档与归档
```

## 文档入口

- `docs/INDEX.md`：文档索引
- `docs/PROJECT_FLOW_2_0.md`：2.0 全链路流程与入口
- `docs/FEATURES_2_0.md`：2.0 功能说明
- `docs/ISSUE_REGISTER_2_0.md`：2.0 问题台账
- `docs/DEPENDENCY_AUDIT_2_0.md`：2.0 依赖与兼容性审计
- `docs/HANDOFF_2_0.md`：2.0 交接文档
- `docs/PROJECT_BRIEF.md`：产品目标、范围与非目标
- `docs/ARCHITECTURE.md`：入口、分层、状态、数据流、异常流
- `docs/CURRENT_STATE.md`：当前真实进展
- `docs/PROJECT_STATUS.md`：未完成事项、当前主线、迭代状态
- `docs/ENGINEERING_TASKLIST.md`：正式任务台账
- `docs/LONG_TERM_ENGINEERING_PLAN.md`：长期架构、配置、异常、存储、GUI 与演进规划
- `docs/MAINLINE_STATUS.md`：单一主线说明
- `docs/ROADMAP.md`：长期演进方向
- `docs/NATIVE_INSTALLER_PLAN.md`：原生安装器与签名路线计划
- `docs/NATIVE_INSTALLER_CUTOVER_POLICY.json`：原生安装器 cutover policy 机器可读真值
- `docs/EXTENSION_CONTRACT.md`：扩展边界与插件契约
- `docs/RISK_REGISTER.md`：风险清单
- `docs/HANDOFF.md`：交接文档
- `docs/VALIDATION.md`：验证矩阵与门禁
- `CHANGELOG.md`：阶段版本变更记录
- `docs/RELEASE_CHECKLIST.md`：发布运行手册
- `docs/SMOKE_CHECKLIST.md`：冒烟检查手册
- `docs/TASK_ARCHIVE.md`：历史归档

## 当前交付边界

ProtoLink 目前已经具备：
- 本地桌面运行能力
- 可执行的测试与回归基线
- 可执行的 release-staging 验证链
- bundled-runtime 便携/分发/安装包链路
- 当前打包后的 GUI 启动入口：`Launch-ProtoLink.bat` / `Launch-ProtoLink.ps1`
- native installer scaffold / toolchain / MSI build / signature verify CLI
- native installer scaffold manifest 的 lifecycle contract 校验
- deliverables 目录级 manifest 与 native installer lane receipt
- `workspace/plugins/<plugin-id>/manifest.json` 的发现、静态校验、descriptor registry、registry.json 装载计划、显式 Class A runtime loading CLI 与 release-preflight runtime gate
- 无口头补充前提下的正式 handoff 文档集

ProtoLink 目前还不承诺：
- 原生签名 Windows 安装器已经可发布
- 云端账号/多端协同
- 跨平台优先级（Linux/macOS）
- 非受信脚本执行环境
- 外部插件的自动激活、Class B / Class C runtime activation、UI/transport/automation 注入或不受控动态加载

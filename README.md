# ProtoLink

ProtoLink 是一个面向 Windows 本地场景的工业通信、协议调试与自动化工作台。

## 项目定位

ProtoLink 的目标不是拼接多个调试工具，而是提供一套可长期维护的桌面工程基线，统一承载：

- 串口、TCP Client、TCP Server、UDP、MQTT Client、MQTT Server
- Modbus RTU / Modbus TCP 调试流程
- 报文分析、回放、寄存器监视
- 自动化规则、自动应答、脚本控制台、定时任务、通道桥接
- 工作区、日志、导出、打包、安装与验证链路

## 当前阶段基线（2026-04-15）

- `uv run python scripts/run_full_test_suite.py` -> `327 passed`
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
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 327
uv run python scripts/run_targeted_regressions.py --suite all
uv run python scripts/audit_gui_layout.py --output-dir dist\\gui-audit\\latest
uv run protolink --audit-plugin-manifests
uv run protolink --list-extension-descriptors
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\\deliverables
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

## 仓库结构

```text
src/protolink/   应用代码（入口、核心、应用服务、传输、UI）
tests/           pytest 回归与验收测试
scripts/         交付验证与工程辅助脚本
docs/            正式工程文档与归档
```

## 文档入口

- `docs/INDEX.md`：文档索引
- `docs/PROJECT_BRIEF.md`：产品目标、范围与非目标
- `docs/ARCHITECTURE.md`：入口、分层、状态、数据流、异常流
- `docs/CURRENT_STATE.md`：当前真实进展
- `docs/PROJECT_STATUS.md`：未完成事项、当前主线、迭代状态
- `docs/ENGINEERING_TASKLIST.md`：正式任务台账
- `docs/MAINLINE_STATUS.md`：单一主线说明
- `docs/ROADMAP.md`：长期演进方向
- `docs/NATIVE_INSTALLER_PLAN.md`：原生安装器与签名路线计划
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
- native installer scaffold / toolchain / MSI build / signature verify CLI
- 无口头补充前提下的正式 handoff 文档集

ProtoLink 目前还不承诺：
- 原生签名 Windows 安装器已经可发布
- 云端账号/多端协同
- 跨平台优先级（Linux/macOS）
- 非受信脚本执行环境

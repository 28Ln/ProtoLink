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

- `uv run pytest -q` -> `288 passed`
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py` -> passed
- 当前阶段版本：`0.2.3`
- Formal baseline freeze: `PL-012` completed
- Delivery hardening baseline: `PL-013` completed
- Current canonical mainline: `PL-014` Native Installer and Signing Path

## Native installer scaffold 状态

- 当前 CLI 基线已暴露：
  - `--build-native-installer-scaffold`
  - `--verify-native-installer-scaffold`
  - `--verify-native-installer-toolchain`
- 这些命令已经成为正式 CLI surface，必须同步进入：
  - `README.md`
  - `docs/NATIVE_INSTALLER_PLAN.md`
  - `docs/VALIDATION.md`
  - `docs/RELEASE_CHECKLIST.md`
- `scripts/verify_canonical_truth.py` 会要求上述文档包含**精确 flag 名称**。

## 快速开始

```powershell
uv sync --python 3.11 --extra dev
uv run protolink --headless-summary
uv run pytest -q
uv sync --python 3.11 --extra dev --extra ui
uv run protolink
```

## 常用验证命令

```powershell
uv run pytest -q
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 288
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --smoke-check
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv build
```

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
- native installer scaffold / toolchain verification CLI
- 无口头补充前提下的正式 handoff 文档集

ProtoLink 目前还不承诺：

- 原生签名 Windows 安装器已可发布
- 云端账号/多端协同
- 跨平台优先级（Linux/macOS）
- 非受信脚本执行环境
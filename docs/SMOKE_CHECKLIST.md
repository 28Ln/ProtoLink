# ProtoLink Smoke Checklist

Last updated: 2026-04-14

## 用途

本文件是最小冒烟运行手册，只保留当前阶段仍需执行的关键步骤。

## 环境

- Python 3.11
- `uv`
- UI 依赖已安装

## 最小冒烟命令

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run protolink --headless-summary
uv run protolink --smoke-check
```

## 冒烟检查项

### 1. 工作区

```powershell
uv run protolink --workspace .\workspace\lab-a --print-workspace
```

期望：
- 输出路径与目标工作区一致
- 设置文件指向目标工作区

### 2. Headless summary

```powershell
uv run protolink --headless-summary
```

期望：
- 命令成功
- transport / module 统计正常输出

### 3. Offscreen UI smoke

```powershell
uv run protolink --smoke-check
```

期望：
- 输出 `smoke-check-ok`
- 启动、展示、关闭过程中无崩溃

### 4. Release preflight

```powershell
uv run protolink --release-preflight
```

期望：
- 返回 JSON 报告
- `ready` 为 `true`

### 5. 工作流快验

```powershell
uv run pytest tests/test_modbus_rtu_workflow_acceptance.py -q
uv run pytest tests/test_modbus_tcp_workflow_acceptance.py -q
```

期望：
- 两条 acceptance 链路通过

## 通过标准

- 冒烟命令通过
- 关键工作流验收通过
- 当前文档与验证口径未出现分叉

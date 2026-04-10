# ProtoLink Validation

## 1. 当前可执行验证

### 当前验证基线

- `uv run pytest` -> 229 passed
- `uv build` -> passed
- `uv run protolink --smoke-check` -> passed with clean `smoke-check-ok` output
- `uv run protolink --release-preflight` -> passed
- `uv run protolink --workspace .\\workspace\\lab-a --build-installer-package audit-fix` -> passed
- `uv run protolink --verify-installer-package .\\workspace\\lab-a\\exports\\20260410-114315-installer-package-audit-fix.zip` -> passed
- The current CI workflow in `.github/workflows/ci.yml` runs `compileall`, `pytest`, `--headless-summary`, and `uv build`

### 环境同步

```powershell
uv sync --python 3.11 --extra dev
```

### 运行无界面摘要

```powershell
uv run protolink --headless-summary
```

### 查看串口枚举结果

```powershell
uv run protolink --list-serial-ports
```

### 运行测试

```powershell
uv run pytest
```

Current full-suite snapshot on 2026-04-10:

- `229 passed`
- no warning summary

### 只验证串口 MVP

```powershell
uv run pytest tests/test_serial_transport.py -q
```

### 只验证 Serial Studio advanced workflow

```powershell
uv run pytest tests/test_serial_profiles.py tests/test_serial_service.py tests/test_ui_serial_panel.py -q
```

### 只验证 TCP client baseline workflow

```powershell
uv run pytest tests/test_tcp_client_transport.py tests/test_tcp_client_service.py tests/test_ui_tcp_client_panel.py -q
```

### 只验证 TCP client advanced workflow

```powershell
uv run pytest tests/test_tcp_client_profiles.py tests/test_tcp_client_service.py tests/test_ui_tcp_client_panel.py -q
```

### 只验证 TCP server baseline workflow

```powershell
uv run pytest tests/test_tcp_server_transport.py tests/test_tcp_server_service.py tests/test_ui_tcp_server_panel.py -q
```

### 只验证 UDP baseline workflow

```powershell
uv run pytest tests/test_udp_transport.py tests/test_udp_service.py tests/test_ui_udp_panel.py -q
```

### 只验证 TCP server advanced workflow

```powershell
uv run pytest tests/test_tcp_server_transport.py tests/test_tcp_server_service.py tests/test_ui_tcp_server_panel.py -q
```

### 只验证 UDP advanced workflow

```powershell
uv run pytest tests/test_udp_profiles.py tests/test_udp_service.py tests/test_ui_udp_panel.py -q
```

### 只验证 MQTT client baseline workflow

```powershell
uv run pytest tests/test_mqtt_client_transport.py tests/test_mqtt_client_service.py tests/test_ui_mqtt_client_panel.py -q
```

### 只验证 MQTT client advanced workflow

```powershell
uv run pytest tests/test_mqtt_client_profiles.py tests/test_mqtt_client_service.py tests/test_ui_mqtt_client_panel.py -q
```

### 只验证 MQTT server baseline workflow

```powershell
uv run pytest tests/test_mqtt_server_transport.py tests/test_mqtt_server_service.py tests/test_ui_mqtt_server_panel.py -q
```

### 只验证 MQTT server advanced workflow

```powershell
uv run pytest tests/test_mqtt_server_profiles.py tests/test_mqtt_server_service.py tests/test_ui_mqtt_server_panel.py -q
```

### 只验证 shared connection lifecycle refactor

```powershell
uv run pytest tests/test_connection_state_model.py tests/test_serial_service.py tests/test_tcp_client_service.py tests/test_bootstrap.py tests/test_ui_main_window.py -q
```

### 只验证 mapped profile persistence refactor + raw composer/replay foundation

```powershell
uv run pytest tests/test_serial_service.py tests/test_tcp_client_service.py tests/test_udp_service.py tests/test_mqtt_client_service.py tests/test_mqtt_server_service.py tests/test_raw_packet_composer.py tests/test_packet_replay.py tests/test_ui_packet_console.py -q
```

### 只验证 replay execution + Modbus RTU parser + TCP server persistence

```powershell
uv run pytest tests/test_packet_replay_service.py tests/test_modbus_rtu_parser.py tests/test_packet_inspector.py tests/test_ui_packet_console.py tests/test_tcp_server_profiles.py tests/test_tcp_server_service.py tests/test_ui_tcp_server_panel.py -q
```

### 只验证 Modbus RTU/TCP parser 基线

```powershell
uv run pytest tests/test_modbus_rtu_parser.py tests/test_modbus_tcp_parser.py tests/test_packet_inspector.py tests/test_ui_packet_console.py -q
```

### 只验证 register monitor 基线模型

```powershell
uv run pytest tests/test_register_monitor.py -q
```

### 只验证 register monitor workflow surface

```powershell
uv run pytest tests/test_register_monitor.py tests/test_register_monitor_service.py tests/test_ui_register_monitor_panel.py -q
```

### 只验证 Modbus RTU workflow surface

```powershell
uv run pytest tests/test_ui_modbus_rtu_panel.py tests/test_ui_main_window.py tests/test_packet_inspector.py tests/test_register_monitor_service.py -q
```

### 只验证 workspace log truth materialization

```powershell
uv run pytest tests/test_logging.py tests/test_wiring.py -q
```

### 导出真实 runtime log bundle

```powershell
uv run pytest tests/test_import_export.py tests/test_app.py -q
```

### 手工导出真实 runtime log bundle

```powershell
uv run protolink --workspace <workspace-path> --export-runtime-log bench-runtime
```

### 手工导出最新 profile bundle

```powershell
uv run protolink --workspace <workspace-path> --export-latest-profile bench-profile
```

### 生成 workspace smoke artifacts

```powershell
uv run protolink --workspace <workspace-path> --generate-smoke-artifacts
```

### 运行 executable smoke-check

```powershell
uv run protolink --smoke-check
```

### 运行 workspace migration baseline

```powershell
uv run protolink --migrate-workspace
```

### 运行 release preflight

```powershell
uv run protolink --release-preflight
```

### 导出 multi-artifact release bundle

```powershell
uv run protolink --workspace <workspace-path> --export-release-bundle bench-release
```

### 运行 one-shot release preparation

```powershell
uv run protolink --workspace <workspace-path> --prepare-release bench-release
```

### 运行 archive package release

```powershell
uv run protolink --workspace <workspace-path> --package-release bench-release
```

### 构建 portable package archive

```powershell
uv run protolink --workspace <workspace-path> --build-portable-package bench-portable
```

### 安装/展开 portable package archive

```powershell
uv run protolink --install-portable-package <archive-path> <target-dir>
```

### 验证 portable package

```powershell
uv run protolink --verify-portable-package <archive-path>
```

### 构建 distribution package archive

```powershell
uv run protolink --workspace <workspace-path> --build-distribution-package bench-distribution
```

### 安装/展开 distribution package archive

```powershell
uv run protolink --install-distribution-package <archive-path> <staging-dir> <target-dir>
```

### 构建 installer-staging package

```powershell
uv run protolink --workspace <workspace-path> --build-installer-staging bench-installer
```

### 安装/展开 installer-staging package

```powershell
uv run protolink --install-installer-staging <archive-path> <staging-dir> <target-dir>
```

### 验证 installer-staging package

```powershell
uv run protolink --verify-installer-staging <archive-path>
```

### 验证 installer package

```powershell
uv run protolink --verify-installer-package <archive-path>
```

### 干净 release-staging 安装顶层 installer package

```powershell
uv run protolink --install-installer-package <archive-path> <clean-staging-dir> <clean-install-dir>
```

验收要点：

- `<clean-staging-dir>` 和 `<clean-install-dir>` 在命令前不存在或为空
- staging 目录包含 `installer-package-manifest.json`、展开后的 installer-staging manifest、distribution manifest
- install 目录包含 portable payload，例如 `README.md`、`INSTALL.ps1`
- install 目录包含 `install-receipt.json`

### 验证 Modbus RTU acceptance path

```powershell
uv run pytest tests/test_modbus_rtu_workflow_acceptance.py -q
```

### 验证 catalog / main-window drift cleanup

```powershell
uv run pytest tests/test_catalog.py tests/test_ui_main_window.py -q
```

### 验证 Modbus TCP workflow surface

```powershell
uv run pytest tests/test_ui_modbus_tcp_panel.py tests/test_ui_main_window.py tests/test_catalog.py -q
```

### 验证 Modbus TCP replay/export slice

```powershell
uv run pytest tests/test_ui_modbus_tcp_panel.py tests/test_tcp_client_service.py tests/test_packet_replay_service.py -q
```

### 验证 Modbus TCP acceptance path

```powershell
uv run pytest tests/test_modbus_tcp_workflow_acceptance.py -q
```

### 只验证 device scan 工作流基线

```powershell
uv run pytest tests/test_device_scan.py -q
```

### 只验证 device scan execution wiring

```powershell
uv run pytest tests/test_device_scan.py tests/test_device_scan_execution_service.py -q
```

### 只验证 auto response 规则基线

```powershell
uv run pytest tests/test_auto_response.py -q
```

### 只验证 auto response runtime 执行接线

```powershell
uv run pytest tests/test_auto_response.py tests/test_auto_response_runtime_service.py -q
```

### 只验证 rule engine 基线

```powershell
uv run pytest tests/test_rule_engine_service.py -q
```

### 只验证 automation-rules workflow surface

```powershell
uv run pytest tests/test_rule_engine_service.py tests/test_ui_automation_rules_panel.py -q
```

### 只验证 automation rule persistence

```powershell
uv run pytest tests/test_automation_rule_profiles.py tests/test_rule_engine_service.py -q
```

### 只验证 script host abstraction

```powershell
uv run pytest tests/test_script_host_service.py -q
```

### 只验证 timed task baseline

```powershell
uv run pytest tests/test_timed_task_service.py -q
```

### 只验证 channel bridge baseline

```powershell
uv run pytest tests/test_channel_bridge_runtime_service.py -q
```

### 只验证 normalized CLI / import-export error policy

```powershell
uv run pytest tests/test_errors.py tests/test_app.py tests/test_import_export.py -q
```

### 只验证 import/export 约定

```powershell
uv run pytest tests/test_import_export.py -q
```

### 启动桌面应用

```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run protolink
```

### 运行离屏 UI smoke

```powershell
@'
import os
import tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from protolink.core.bootstrap import bootstrap_app_context
from protolink.ui.main_window import ProtoLinkMainWindow
from protolink.ui.qt_dispatch import QtCallbackDispatcher
from protolink.ui.theme import APP_STYLESHEET

app = QApplication([])
app.setStyleSheet(APP_STYLESHEET)
with tempfile.TemporaryDirectory() as temp_dir:
    context = bootstrap_app_context(Path(temp_dir), persist_settings=False)
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
    window = ProtoLinkMainWindow(
        workspace=context.workspace,
        inspector=context.packet_inspector,
        serial_service=context.serial_session_service,
        mqtt_client_service=context.mqtt_client_service,
        mqtt_server_service=context.mqtt_server_service,
        tcp_client_service=context.tcp_client_service,
        tcp_server_service=context.tcp_server_service,
        udp_service=context.udp_service,
        packet_replay_service=context.packet_replay_service,
        register_monitor_service=context.register_monitor_service,
        rule_engine_service=context.rule_engine_service,
    )
    window.show()
    app.processEvents()
    print("ui-smoke-ok")
    window.close()
    context.serial_session_service.shutdown()
    context.mqtt_client_service.shutdown()
    context.mqtt_server_service.shutdown()
    context.tcp_client_service.shutdown()
    context.tcp_server_service.shutdown()
    context.udp_service.shutdown()
    context.packet_replay_service.shutdown()
app.quit()
'@ | uv run python -
```

## 2. 当前验证覆盖

当前只覆盖：

- 工作区布局初始化
- 设置持久化与工作区切换
- 模块目录与项目元数据
- 传输抽象与会话事件
- 结构化日志模型与原始字节保留
- 事件总线到日志/包检查器的基础联通
- 包检查器的载荷视图与过滤状态
- 串口端口发现 CLI
- 串口 loopback 生命周期与收发日志
- 串口 session service 的后台 open/close/send 编排
- Serial Studio 面板与 dockable packet console 的离屏 UI 验证
- 串口打开失败时的用户可见错误状态与 transport.error 日志
- Serial Studio workspace profile 的 draft / preset 持久化
- ASCII / HEX / UTF-8 + line ending 发送选项
- TCP client lifecycle、service、UI panel 与 packet inspector 联通
- shared connection-service lifecycle base 在 serial / TCP client 上的复用
- TCP client workspace profile 的 draft / preset 持久化
- TCP server lifecycle、service、UI panel 与 packet inspector 联通
- UDP lifecycle、service、UI panel 与 packet inspector 联通
- TCP server per-client visibility 与 targeted send
- UDP workspace profile 的 draft / preset 持久化
- MQTT client lifecycle、service、UI panel 与 packet inspector 联通
- MQTT client workspace profile 的 draft / preset 持久化
- MQTT server lifecycle、service、UI panel 与 packet inspector 联通
- MQTT server workspace profile 的 draft / preset 持久化
- serial/TCP client/TCP server/UDP/MQTT client/MQTT server 的 mapped profile persistence 复用基线
- TCP server 的 draft / preset persistence 复用基线
- explicit connection lifecycle state transition validation
- raw packet composer 的 bytes-first draft/preview workflow
- packet replay plan 的构建、方向筛选、delay 保留、JSON round-trip
- packet replay execution service 对 active transport 的 dispatch 基线
- packet console 内 replay 执行控制（计划路径 + 目标通道 + 状态反馈）
- packet inspector 选中 payload 的 Modbus RTU 解析与 CRC 校验显示
- packet inspector 选中 payload 的 Modbus TCP 解析与 MBAP 校验显示
- register monitor 的寄存器点位模型、缩放和字节序映射解码
- device scan 的 RTU/TCP 探测报文生成、响应判定和结果汇总
- device scan execution 的活动会话发包、入站响应判定和 finalize 汇总
- auto response 的 RAW/RTU/TCP 规则匹配与响应动作选择
- auto response runtime 的入站报文匹配与活动会话回发
- rule engine 的 replay/auto-response/device-scan preparation 编排执行
- rule engine 的冲突策略与执行历史
- packet inspector 可见行的 replay plan 构建与落盘导出
- register monitor 的点位管理与手工寄存器字解码面板
- register monitor 的入站 Modbus RTU/TCP 响应实时解码
- automation-rules 面板的规则保存、运行与扫描任务清理
- automation rules 的工作区持久化
- script host 的语言注册与内联 Python 执行
- timed task 的固定间隔规则调度
- channel bridge 的入站报文转发与脚本变换
- CLI exit code / user-facing error formatting / export extension validation
- export scaffold CLI 写入 manifest 与 payload 占位文件
- captures/logs/profiles 的导出 bundle 命名与 manifest 约定
- release preflight 的 capture-artifact 阻塞门槛
- portable package 的 manifest / checksum 校验与 verify CLI
- distribution / installer install path 的 nested-archive checksum 校验与 mismatch 拒绝
- portable / distribution / installer install path 的 zip path-traversal / symlink 拒绝
- portable package 输出对 `__pycache__` / `.pyc` residue 的排除
- 应用骨架可被导入

## 3. 后续必须建立的验证路径

### 单元测试

- 配置模型
- 协议解析器
- 规则匹配
- 导入导出
- 日志格式化
- 串口 UI 控制器与错误映射
- import/export 约定与错误恢复路径

### 集成测试

- 串口会话生命周期
- TCP/UDP/MQTT 连接生命周期
- Modbus RTU 请求与响应工作流
- Dockable UI 面板布局与状态同步
- 非串口 transport service 复用同一错误策略
- connection-service 生命周期抽象复用

### 手工验证

- UI 交互一致性
- 大量日志下 UI 是否卡顿
- 自动应答是否可控
- 配置迁移是否可恢复

## 4. 功能完成的验收门槛

后续每个功能模块都要满足：

- 可配置
- 可启动
- 可停止
- 有状态反馈
- 有错误反馈
- 有日志
- 有导出或复现路径

# ProtoLink Handoff

Last updated: 2026-04-16

## 1. 交接目的

本文件用于让新的维护者在无口头补充的情况下，完成：

- 拉起项目
- 跑通验证
- 理解目录与入口
- 继续当前主线任务

## 2. 项目一句话定义

ProtoLink 是一个面向 Windows 的本地工业通信、协议调试与自动化工作台，当前重点是在 0.2.5 正式基线之上推进 native installer / signing 路线与长稳验证准备。

## 3. 当前真实进展

- full pytest: `358 passed`
- targeted regressions: passed
- release-staging: passed
- dist fresh-install: passed
- 当前阶段版本：`0.2.5`
- `PL-012` 已完成并冻结正式交付基线
- `PL-013` 已完成并冻结交付瘦身与运行证据基线
- 当前主线：`PL-014` Native Installer and Signing Path
- GUI 已完成三轮结构化整改，当前重点转为 `docs/GUI_REFACTOR_TASKLIST.md` 中定义的最后一轮视觉收口与一致性验收，而非结构性返工
- `workspace/plugins/*/manifest.json` 的发现、静态校验、审计报告与 release-preflight 阻断已经进入正式基线
- valid manifest 到 extension descriptor registry 的列举边界已经进入正式基线
- controlled loading plan 与 registry.json 装载策略已经进入正式基线
- 显式 Class A runtime loading CLI 已进入正式基线；当前只执行 enabled 且 `effective_state=eligible_for_loading` 的 Class A `register()`
- `uv run protolink --release-preflight` 已把 enabled Class A runtime load gate 纳入正式交付口径
- `audit_gui_layout.py` 当前在目标分辨率下已达到 `highest_severity=clean`
- 当前仍未开放 Class B / Class C runtime activation、自动激活或不受控动态加载

## 4. 关键入口

### 代码入口
- `src/protolink/__main__.py`
- `src/protolink/app.py`
- `src/protolink/core/bootstrap.py`
- `src/protolink/ui/main_window.py`

### 文档入口
- `README.md`
- `docs/INDEX.md`
- `docs/CURRENT_STATE.md`
- `docs/MAINLINE_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/GUI_REFACTOR_TASKLIST.md`
- `docs/RISK_REGISTER.md`

## 5. 目录说明

```text
src/protolink/
  app.py            CLI / GUI 总入口
  core/             领域模型、日志、workspace、打包、协议解析
  application/      用例与运行时编排服务
  transports/       各类 transport adapter
  ui/               主窗口与功能面板

tests/              单元测试、UI 测试、验收测试
scripts/            交付验证与工程脚本
docs/               正式文档与归档
```

## 6. 启动与验证

### 本地运行
```powershell
uv sync --python 3.11 --extra dev --extra ui
uv run protolink
```

### 核心验证
```powershell
uv run python scripts/run_full_test_suite.py
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 358
uv run python scripts/run_targeted_regressions.py --suite all
uv run python scripts/audit_gui_layout.py --output-dir dist\gui-audit\latest
uv run protolink --audit-plugin-manifests
uv run protolink --list-extension-descriptors
uv run protolink --plan-extension-loading
uv run protolink --load-enabled-extensions
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
uv run python scripts/verify_release_staging.py --name local
uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\deliverables
python scripts/verify_dist_install.py --artifact-version 0.2.5
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

- `verify_native_installer_lane.py` 默认是 readiness probe；它会输出 `lane_status`、`blocking_items`、`next_actions` 与 `readiness`。发布线需要显式加 `--require-toolchain` 或 `--require-signed`。
- `verify_release_staging.py` 现在会附带 `native_installer_lane` 结果，便于在同一次交付验证中看到 bundled 基线与 native 路线 readiness。
- `run_soak_validation.py` 在加 `--require-all-ready` 后才作为长稳门禁，并沉淀 `cycle_ready` / `failing_cycles` / `total_duration_ms` 证据。
- `run_full_test_suite.py` 是当前正式 full-suite 入口，用逐文件方式收敛 pytest 真值。
- `list-extension-descriptors` 会输出当前工作区通过静态校验的扩展 descriptor registry。
- `plan-extension-loading` 会输出 registry.json 与 extension descriptors 组合后的受控装载计划。
- `load-enabled-extensions` 会输出 `runtime_load_report`；只有 enabled 且 `effective_state=eligible_for_loading` 的 Class A entrypoint 会被显式执行。
- `release-preflight` 现在会复用同一条 Class A runtime gate，并在 `load_failed` 时写入 failure evidence。
- `list-extension-descriptors` 与 `plan-extension-loading` 不等于应用启动时自动加载外部扩展；当前也不会自动执行 Class B / Class C。

## 7. 当前主线与未完成事项

详见：
- `docs/MAINLINE_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/PROJECT_STATUS.md`

接手后优先继续：
1. native installer / signing 的受控发布 lane
2. 签名与时间戳受控发布流程
3. 在现有 Class A runtime gate 基线上推进 lifecycle、Class B review workflow 与 Class C 执行边界
4. HIL / 长稳回归规划

## 8. 当前已知风险

详见：`docs/RISK_REGISTER.md`

接手时务必先理解：
- 当前 bundled runtime 仍偏大，但已完成第一轮瘦身
- 当前交付不是原生签名安装器正式发布线
- 脚本能力不是不受信沙箱
- 插件扩展当前已开放到 manifest discovery / validation / audit / descriptor registry / loading plan / explicit Class A runtime loading CLI；但仍不含自动激活、Class B / Class C runtime activation、动态 UI 注入或正式 SDK
- 当前 WiX scaffold / toolchain / MSI build / signature verify 只到实现与验证入口，不等于发布闭环已完成

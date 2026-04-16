# ProtoLink 2.0 Project Flow

Last updated: 2026-04-16

## 1. Purpose

本文定义 ProtoLink 当前 2.0 阶段收尾版本的全链路流程，用于说明：

- 入口链
- workspace / settings / logs / exports 归属
- release / install / validation 链
- extension boundary
- truth boundary

## 2. Source Entry Chain

当前源代码正式入口：

1. `src/protolink/__main__.py`
2. `src/protolink/app.py`
3. `src/protolink/core/bootstrap.py`
4. `src/protolink/ui/main_window.py`

CLI 与 GUI 共享同一 bootstrap 过程。

## 3. Installed Entry Chain

当前安装/便携形态下的正式入口仍是：

- `Launch-ProtoLink.ps1`
- `Launch-ProtoLink.bat`
- `runtime/python.exe -m protolink`

当前 canonical truth 中，**没有独立业务 EXE 作为正式交付入口**。

## 4. Workspace Flow

当前 workspace 承载：

- `workspace_manifest.json`
- `logs/`
- `captures/`
- `profiles/`
- `exports/`
- `plugins/`

workspace 是配置、运行、交付与扩展的统一归属边界。

## 5. Settings Flow

当前 settings 路径：

- `.protolink/app_settings.json`

它与 workspace 分离，但在 bootstrap 时统一解析并纳入运行上下文。

## 6. Runtime Flow

主要运行链：

1. UI / CLI 动作进入 `app.py`
2. `bootstrap_app_context(...)`
3. 初始化：
   - workspace
   - settings
   - event bus
   - log store
   - services
   - packet inspector
4. transport / service 产生事件
5. 事件进入日志、snapshot、packet inspector
6. UI 刷新

## 7. Evidence Flow

当前 evidence 链：

- `workspace/logs/transport-events.jsonl`
- `workspace/logs/runtime-failure-evidence.jsonl`
- config failure evidence

`release-preflight` 会读取这些 evidence 并做阻断判断。

## 8. Validation Flow

当前正式验证链如下：

- full suite：`run_full_test_suite.py`
- targeted regressions：`run_targeted_regressions.py`
- release-staging：`verify_release_staging.py`
- fresh-install：`verify_dist_install.py`
- soak：`run_soak_validation.py`
- GUI formal audit：`audit_gui_layout.py`
- native installer probe：`verify_native_installer_lane.py`
- canonical truth：`verify_canonical_truth.py`

## 9. Delivery Flow

当前交付链：

1. release bundle
2. portable package
3. distribution package
4. installer staging package
5. installer package
6. install / uninstall / verify
7. deliverables 归档

当前正式交付基线仍是 bundled-runtime 路线。

## 10. Extension Flow

当前扩展链：

1. plugin manifest discovery
2. plugin validation / audit
3. descriptor registry
4. loading plan
5. explicit Class A runtime loading
6. release-preflight runtime gate

当前边界：

- Class A：允许显式受控加载
- Class B：`review_required`
- Class C：不进入自动执行

## 11. Truth Boundary

当前 truth 分层：

- runtime truth：事件、snapshot、日志、failure evidence
- config truth：settings、workspace manifest、plugin manifest、registry config
- validation truth：validation scripts 的最新执行结果
- document truth：`README.md` + `docs/*` 中 canonical docs

## 12. Current Flow Gaps

仍未闭环：

1. signed native installer release lane
2. extension lifecycle governance
3. HIL / 更长时长 soak
4. GUI 最后一轮产品化收口


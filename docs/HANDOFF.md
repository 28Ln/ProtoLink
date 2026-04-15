# ProtoLink Handoff

Last updated: 2026-04-15

## 1. 交接目的

本文件用于让新的维护者在无口头补充的情况下，完成：

- 拉起项目
- 跑通验证
- 理解目录与入口
- 继续当前主线任务

## 2. 项目一句话定义

ProtoLink 是一个面向 Windows 的本地工业通信、协议调试与自动化工作台，当前重点是在 0.2.5 正式基线之上推进 native installer / signing 路线与长稳验证准备。

## 3. 当前真实进展

- full pytest: `312 passed`
- targeted regressions: passed
- release-staging: passed
- dist fresh-install: passed
- 当前阶段版本：`0.2.5`
- `PL-012` 已完成并冻结正式交付基线
- `PL-013` 已完成并冻结交付瘦身与运行证据基线
- 当前主线：`PL-014` Native Installer and Signing Path

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
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 312
uv run python scripts/run_targeted_regressions.py --suite all
uv run protolink --build-native-installer-scaffold proto-stage
uv run protolink --verify-native-installer-scaffold <scaffold-dir>
uv run protolink --verify-native-installer-toolchain
uv run protolink --build-native-installer-msi <scaffold-dir>
uv run protolink --verify-native-installer-signature <msi-file>
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py --artifact-version 0.2.5
python scripts/verify_native_installer_lane.py
python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready
uv build
```

- `verify_native_installer_lane.py` 默认是 readiness probe；发布线需要显式加 `--require-toolchain` 或 `--require-signed`。
- `run_soak_validation.py` 在加 `--require-all-ready` 后才作为长稳门禁，并沉淀 `cycle_ready` / `failing_cycles` / `total_duration_ms` 证据。
- `run_full_test_suite.py` 是当前正式 full-suite 入口，用逐文件方式收敛 pytest 真值。

## 7. 当前主线与未完成事项

详见：
- `docs/MAINLINE_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/PROJECT_STATUS.md`

接手后优先继续：
1. native installer / signing 的受控发布 lane
2. 签名与时间戳受控发布流程
3. 扩展契约与插件边界文档化
4. HIL / 长稳回归规划

## 8. 当前已知风险

详见：`docs/RISK_REGISTER.md`

接手时务必先理解：
- 当前 bundled runtime 仍偏大，但已完成第一轮瘦身
- 当前交付不是原生签名安装器正式发布线
- 脚本能力不是不受信沙箱
- 扩展契约尚未正式化
- 当前 WiX scaffold / toolchain / MSI build / signature verify 只到实现与验证入口，不等于发布闭环已完成

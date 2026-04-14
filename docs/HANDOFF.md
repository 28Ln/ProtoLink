# ProtoLink Handoff

Last updated: 2026-04-14

## 1. 交接目的

本文件用于让新的维护者在无口头补充的情况下，完成：

- 拉起项目
- 跑通验证
- 理解目录与入口
- 继续当前主线任务

## 2. 项目一句话定义

ProtoLink 是一个面向 Windows 的本地工业通信、协议调试与自动化工作台，当前重点是在正式基线之上继续做交付优化与运行边界补强。

## 3. 当前真实进展

- full pytest: `280 passed`
- targeted regressions: passed
- release-staging: passed
- dist fresh-install: passed
- 当前阶段版本：`0.2.1`
- `PL-012` 已完成并冻结正式交付基线
- 当前主线：`PL-013` Package Slimming and Delivery Hardening

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
uv run pytest -q
uv run python scripts/verify_canonical_truth.py --expected-mainline PL-013 --expected-pytest-count 280
uv run python scripts/run_targeted_regressions.py --suite all
uv run python scripts/verify_release_staging.py --name local
python scripts/verify_dist_install.py
uv build
```

## 7. 当前主线与未完成事项

详见：
- `docs/MAINLINE_STATUS.md`
- `docs/ENGINEERING_TASKLIST.md`
- `docs/PROJECT_STATUS.md`

接手后优先继续：
1. package slimming 与 failure evidence 补强
2. native installer / signing 路线边界化
3. 扩展契约与插件边界文档化

## 8. 当前已知风险

详见：`docs/RISK_REGISTER.md`

接手时务必先理解：
- 当前 bundled runtime 仍偏大
- 当前交付不是原生签名安装器
- 脚本能力不是不受信沙箱
- 扩展契约尚未正式化

## 9. 第一周动作清单

1. 运行完整验证基线
2. 阅读 `README.md`、`docs/INDEX.md`、`docs/ARCHITECTURE.md`
3. 阅读 `docs/MAINLINE_STATUS.md` 与 `docs/ENGINEERING_TASKLIST.md`
4. 确认本地 `git status` 干净（忽略本地工具缓存目录）
5. 再开始新的功能或重构工作

## 10. 当前不建议先做的事

- 不要先做大规模 UI 重构
- 不要先扩更多协议面
- 不要把脚本宿主当成通用插件系统
- 不要绕过现有验证链直接改交付脚本

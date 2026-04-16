# ProtoLink 2.0 Handoff

Last updated: 2026-04-16

## 1. Purpose

本文是 ProtoLink 2.0 阶段收尾版本的正式交接文档，面向下一个 AI 团队。

目标：

- 零口头补充接手
- 快速确认当前真值
- 快速找到 canonical docs
- 快速理解哪些事情已完成、哪些还没完成

## 2. Current Real Status

- branch: `main`
- latest verified pytest truth: `356 passed`
- current active mainline: `PL-014`
- current version baseline: `0.2.5`
- worktree baseline: 以当前仓库为准，接手前先执行 `git status`

## 3. Canonical Documents

接手后优先阅读：

1. `README.md`
2. `docs/CURRENT_STATE.md`
3. `docs/PROJECT_STATUS.md`
4. `docs/ENGINEERING_TASKLIST.md`
5. `docs/VALIDATION.md`
6. `docs/PROJECT_FLOW_2_0.md`
7. `docs/FEATURES_2_0.md`
8. `docs/ISSUE_REGISTER_2_0.md`
9. `docs/DEPENDENCY_AUDIT_2_0.md`
10. 本文

## 4. Current Verified Truth

当前重新执行得到的正式真值：

- `uv build` -> passed
- `uv run protolink --headless-summary` -> passed
- `uv run python scripts/run_full_test_suite.py --json-only` -> `356 passed`
- `uv run python scripts/run_targeted_regressions.py --suite all` -> passed
- `uv run python scripts/verify_release_staging.py --name local` -> passed
- `uv run python scripts/verify_release_staging.py --name ci` -> passed
- `python scripts/verify_dist_install.py --artifact-version 0.2.5` -> passed
- `python scripts/run_soak_validation.py --cycles 2 --sleep-ms 0 --require-all-ready` -> passed
- `uv run python scripts/audit_gui_layout.py --output-dir dist\gui-audit\latest` -> passed
- `python scripts/verify_native_installer_lane.py` -> passed
- `uv run python scripts/build_release_deliverables.py --name release-0.2.5 --target-dir dist\deliverables` -> passed
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 356` -> passed

## 5. What Is Done

- bundled-runtime delivery baseline 已形成
- release-staging / fresh-install / soak / GUI audit / full suite 已可执行
- 扩展边界已到 Class A 显式受控加载
- GUI formal audit 已 clean
- 文档体系已经成形，可用于正式 handoff

## 6. What Is Not Done

### `PL-014`

- 未形成 signed native installer 正式发布线
- 未形成受控签名/时间戳/回滚流程
- native installer 路线仍是 probe / planning lane

### `PL-015`

- lifecycle model 未完成
- Class B review workflow 未完成
- Class C 长期边界未完成
- 正式 SDK 契约未完成

### `PL-016`

- HIL 回归体系未建立
- 更长时长 / 更高负载 soak 未建立

### GUI

- `GUI-101`
- `GUI-103`
- `GUI-104`
- `GUI-105`

仍未关闭。

## 7. Current Risks

优先关注：

1. 无 signed native installer 正式发布线
2. 扩展治理下一阶段未完成
3. script host 不是不受信沙箱
4. HIL 与长稳体系缺失
5. 文档真值漂移风险需要持续控制

详见：`docs/RISK_REGISTER.md` 与 `docs/ISSUE_REGISTER_2_0.md`

## 8. First Steps for the Next Team

1. 执行 `git status`
2. 执行 `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 356`
3. 执行 `uv run python scripts/run_full_test_suite.py --json-only`
4. 阅读：
   - `docs/PROJECT_STATUS.md`
   - `docs/ENGINEERING_TASKLIST.md`
   - `docs/ISSUE_REGISTER_2_0.md`
   - `docs/DEPENDENCY_AUDIT_2_0.md`
5. 决定是继续：
   - `PL-014` 收尾
   - 还是切到 `PL-015`

## 9. Repository Hygiene Notes

当前应保留：

- `dist/deliverables/`
- `dist/gui-audit/latest/`
- 当前 `dist/protolink-0.2.5.*`
- `docs/` canonical 文档

当前可清理：

- 仓库根目录下 `tmp_*` probe 目录
- `dist/_tmp_inspect`
- `dist/gui-audit-smoke`
- `dist/protolink-extension-smoke-*`
- 过期的 `dist/protolink-0.2.4.*`
- `.pytest_cache`

本次已执行清理：

- 根目录 `tmp_*` probe 目录
- `dist/_tmp_inspect`
- `dist/gui-audit-smoke`
- `dist/protolink-extension-smoke-*`
- `dist/protolink-0.2.4.*`
- `.pytest_cache`

## 10. Do Not Assume

不要假设以下事情已经完成：

- native installer signed release
- 独立业务 EXE 已进入正式交付线
- 不受信脚本沙箱
- Class B / Class C 扩展运行治理
- HIL 回归

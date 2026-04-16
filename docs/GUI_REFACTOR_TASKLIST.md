# ProtoLink GUI Refactor Tasklist

Last updated: 2026-04-16

## 1. 文档定位

- 本文件用于沉淀 ProtoLink GUI 改造的正式工程任务、当前进展、剩余工作与验收标准。
- 本文件是 `docs/ENGINEERING_TASKLIST.md` 的配套工作流文档，不替代单一主线任务台账；当前 `Active` 主线仍为 `PL-014`。
- 本文件聚焦 Windows-first PySide6 桌面界面的布局、样式、文案、组件一致性与交付级验收，不负责 native installer / signing 路线本身。

## 2. 当前基线

ProtoLink 的 GUI 已从“主工作面被说明区与底部 dock 挤压”的不可交付状态，推进到“结构稳定、可运行、可回归、可继续精修”的阶段基线。

当前已确认的事实如下：

- 主窗口已完成以主工作面为中心的分栏重构。
- 报文分析台已由长页堆叠改为 `分析 / 构建 / 重放` 的 tab 化结构，并引入 splitter 承载细节区。
- Modbus RTU / Modbus TCP / 寄存器监视 / 自动化规则等复杂面板已完成第一轮 tab 化与 section 化。
- Serial / MQTT / TCP / UDP 等传输面板已完成第二轮 tab 化、状态区换行与长表单拆分。
- Hero、左侧导航、右侧说明区与底部报文分析台已完成减重，小窗口下已具备自动收敛策略。
- GUI 当前剩余工作已从“结构抢救”转为“视觉收口、滚动层级收敛、文案产品化、组件系统统一”。
- `audit_gui_layout.py` 当前已在目标分辨率与关键模块抽样上达到 `highest_severity=clean`。

当前验证真值：

- `uv run python scripts/run_full_test_suite.py --json-only` -> `356 passed`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 356` -> passed

## 3. 已完成进展

### 3.1 第一阶段：主窗口结构止损

状态：`Completed`

已完成事项：

- 中央区改为主工作面优先的分栏结构。
- 右侧说明区从主工作面垂直堆叠中剥离。
- 首次显示时主动收敛底部 dock 高度，避免默认挤压主区。
- 小窗口条件下支持右侧说明区自动收起。

已落地产物：

- `src/protolink/ui/main_window.py`
- `tests/test_ui_main_window.py`

### 3.2 第二阶段：报文分析台结构重构

状态：`Completed`

已完成事项：

- 报文分析台改为三主 tab：`分析 / 构建 / 重放`
- `分析` 页采用“列表 + 详情 tab”的左右 splitter 布局
- `构建` 页采用“草稿 + 预览”的左右 splitter 布局
- 默认最小高度显著降低，不再以超长单页形式压缩主窗口

已落地产物：

- `src/protolink/ui/packet_console.py`
- `tests/test_ui_packet_console.py`

### 3.3 第三阶段：复杂面板 tab 化

状态：`Completed`

已完成事项：

- 寄存器监视改为“点位配置 / 解码预览”双 tab
- 自动化规则改为“规则编辑 / 运行安全”主 tab，并引入动作子 tab
- Modbus RTU / TCP 改为“请求配置 / 预览与解析 / 回放与导出”三 tab
- 复杂面板的 section 边界与长状态文本已完成第一轮收敛

已落地产物：

- `src/protolink/ui/register_monitor_panel.py`
- `src/protolink/ui/automation_rules_panel.py`
- `src/protolink/ui/modbus_rtu_panel.py`
- `src/protolink/ui/modbus_tcp_panel.py`

### 3.4 第四阶段：传输面板统一化

状态：`Completed`

已完成事项：

- 串口、MQTT、TCP、UDP 面板全部完成 tab 化
- 连接配置与负载编辑分离，避免单页长表单
- 高频状态文案已支持换行，避免中文裁切与“乱码假象”
- 中文标签列已完成第一轮最小宽度保护

已落地产物：

- `src/protolink/ui/serial_panel.py`
- `src/protolink/ui/mqtt_client_panel.py`
- `src/protolink/ui/mqtt_server_panel.py`
- `src/protolink/ui/tcp_client_panel.py`
- `src/protolink/ui/tcp_server_panel.py`
- `src/protolink/ui/udp_panel.py`

### 3.5 第五阶段：首屏减重与小窗口收敛

状态：`Completed`

已完成事项：

- Hero 收敛为更轻量的摘要结构
- 左侧路径展示改为项目卡片 + 缩略路径 + tooltip
- 右侧说明区在小窗口下自动折叠
- 底部报文分析台默认高度降至低噪音区间
- GUI 暴露文案已完成第一轮去工程化处理

已落地产物：

- `src/protolink/ui/main_window.py`
- `src/protolink/ui/theme.py`
- `src/protolink/presentation.py`

## 4. 当前剩余任务

以下任务为 GUI 收口阶段的正式工作项。其目标是把当前“结构可用”的界面推进到“正式交付级”的视觉与交互状态，而不是重新推翻现有结构。

| ID | Priority | Status | 目标 | 主要输出 |
| --- | --- | --- | --- | --- |
| GUI-101 | P1 | In Progress | 继续压缩首屏非操作区，保证主工作面成为唯一主角 | 主窗口首屏层级收敛、冗余标题弱化 |
| GUI-102 | P1 | Completed | 收敛滚动层级，避免多层滚动并存 | 主窗口/面板滚动策略统一 |
| GUI-103 | P1 | In Progress | 完成样式 token、间距、圆角、强调色统一 | `theme.py` 组件系统收口 |
| GUI-104 | P1 | In Progress | 清理残余工程口吻，统一 GUI 文案为产品工作台口径 | `presentation.py` 与面板文案统一 |
| GUI-105 | P2 | Pending | 处理右上角模块状态、重复标题与局部视觉碎片 | 顶部状态表达收敛 |
| GUI-106 | P2 | Completed | 完成跨模块截图巡检与视觉一致性复核 | 截图验收矩阵、consistency 结论 |

## 5. 任务明细

### GUI-101 — 首屏主次收敛

目标：

- 让用户在首屏直接进入模块输入与操作，而不是先阅读摘要、说明与状态卡。

必须完成：

1. 进一步弱化 Hero 与全局摘要条的视觉权重
2. 减少主工作面外层冗余标题与说明
3. 收敛重复的模块名称、状态胶囊与说明性标签
4. 保证第一个可操作字段在目标分辨率下尽量首屏可见

完成标准：

- 不再出现“摘要区比工作区更抢眼”的情况
- 主窗口首屏强标题层级不超过 3 处
- 模块标题、状态、tab、section 之间不再形成连续重色条堆叠

### GUI-102 — 滚动层级收敛

目标：

- 避免左栏、中区、面板内部、底部分析台同时形成滚动竞争。

必须完成：

1. 小窗口优先收起辅助区，而不是依赖额外滚动
2. 面板内部优先使用 tab / splitter / 分区替代纵向长页
3. 保持主工作面滚动焦点明确，避免滚轮落点不确定
4. 报文分析台默认状态下仅暴露必要信息与必要滚动

完成标准：

- 目标分辨率下不存在 3 层以上同时活跃滚动容器
- 用户可以明显判断当前滚动对象
- 模块切换后滚动策略一致，不出现局部例外页面

当前结论：

- dashboard 项目路径卡片已从高压缩换行状态收敛到单行可读状态。
- 报文分析台已去除额外 wrapper scroll，并以更稳定的默认 dock 高度通过 formal audit。

### GUI-103 — 视觉 token 与组件系统收口

目标：

- 把当前深色桌面界面从“能用的工程主题”推进到“稳定、专业、耐看的产品化主题”。

必须完成：

1. 统一背景层、边框层、文本层、强调层 token
2. 将黄色从默认标题强调色完全退回到 warning/次要例外场景
3. 统一 panel / tab / splitter / list item / button / input 的间距、圆角、hover、selected、focus 状态
4. 控制 badge / pill / 状态标签的使用密度

完成标准：

- 任意主窗口页面不再出现“满屏都在强调”的观感
- 左侧导航、右侧说明区、主工作面、底部分析台属于同一视觉体系
- 长时间使用场景下不会因高对比强调过多而产生疲劳

### GUI-104 — 文案产品化

目标：

- 彻底清理 GUI 中残余的工程内部话语体系。

必须完成：

1. 清理或替换“主线”“已落地”“当前草稿”“工作面”等暴露工程背景的表述
2. 将概览区文案改为功能说明与使用导向
3. 将状态文案从“调试摘要串”收敛为更短的业务态表达
4. 统一各模块的按钮、提示、空状态与说明文本风格

完成标准：

- GUI 首屏与模块页不再出现内部文档路径、台账口吻或工程阶段口吻
- 说明区与状态条采用统一产品语气
- 用户不需要理解仓库结构即可理解界面文案

### GUI-105 — 重复标题与局部视觉碎片收口

目标：

- 降低“标题条套标题条”“状态条套 section 条”的碎片感。

必须完成：

1. 处理右上角当前模块状态与主区标题的重复表达
2. 继续收紧 tab 与内容区之间的空白与分隔
3. 统一 section 标题与正文间距
4. 统一卡片底部留白与贴边距离

完成标准：

- 模块切换时不会出现明显的顶层标题重复
- section 标题不再像临时辅助框标签
- 页面整体节奏一致，无明显贴边或悬空区域

### GUI-106 — 截图验收与一致性复核

目标：

- 用固定尺寸与 DPI 场景验证 GUI 是否达到交付前的一致性要求。

必须完成：

1. 覆盖 `1180x760`、`1366x768`、`1480x920`、`1680x1050`
2. 覆盖 Windows `125% DPI`
3. 至少检查：Serial、MQTT Client、TCP Server、Modbus TCP、Register Monitor、Automation Rules、Packet Console
4. 记录首屏可见主操作区域、滚动层级、说明区折叠行为、报文分析台默认状态
5. 将结论沉淀到正式文档，而非聊天记录

完成标准：

- 不出现布局塌陷、中文压缩、假性乱码、标题重叠
- 小窗口自动折叠与默认 dock 高度行为稳定
- 模块间视觉风格无明显断层

当前结论：

- `uv run python scripts/audit_gui_layout.py --output-dir dist\\gui-audit\\latest` 已生成可交接截图矩阵与 JSON 报告。
- 当前 `summary.highest_severity = clean`，关键抽样模块与目标分辨率下无剩余 formal blocker / warning。

## 6. 文件级实施边界

GUI 收口阶段默认涉及以下文件族；如需新增例外，必须以测试与验证证据支持。

### 核心文件

- `src/protolink/ui/main_window.py`
- `src/protolink/ui/theme.py`
- `src/protolink/presentation.py`
- `src/protolink/ui/packet_console.py`

### 模块面板

- `src/protolink/ui/serial_panel.py`
- `src/protolink/ui/mqtt_client_panel.py`
- `src/protolink/ui/mqtt_server_panel.py`
- `src/protolink/ui/tcp_client_panel.py`
- `src/protolink/ui/tcp_server_panel.py`
- `src/protolink/ui/udp_panel.py`
- `src/protolink/ui/modbus_rtu_panel.py`
- `src/protolink/ui/modbus_tcp_panel.py`
- `src/protolink/ui/register_monitor_panel.py`
- `src/protolink/ui/automation_rules_panel.py`

### 验证文件

- `tests/test_ui_main_window.py`
- `tests/test_ui_packet_console.py`
- `tests/test_ui_owner_surface_consistency.py`
- 各 `tests/test_ui_*panel.py`

## 7. 验收标准

### 7.1 分辨率与 DPI

必须在以下条件下通过人工与自动化复核：

- `1180x760`
- `1366x768`
- `1480x920`
- `1680x1050`
- Windows `125% DPI`

### 7.2 布局与交互

必须满足：

1. 首屏优先出现主工作区，不再由摘要区或分析台主导
2. 小窗口下右侧说明区自动折叠逻辑稳定
3. 底部报文分析台默认保持低噪音，不压缩主工作面
4. 第一个关键输入字段在目标分辨率下尽量首屏可达
5. 不出现三层以上同时活跃滚动容器

### 7.3 视觉与文案

必须满足：

1. 不再出现“像乱码”的中文裁切或压缩假象
2. 黄色只作为 warning 或例外强调，不再作为全局标题色
3. 标题层级清晰但不碎，不出现大量解释型标题条
4. GUI 不再暴露内部文档路径、主线台账或工程过程性文案
5. 状态条与说明区采用统一、面向用户的产品语言

### 7.4 回归与证据

至少保留以下证据链：

- `uv run python scripts/run_full_test_suite.py --json-only`
- `uv run python scripts/verify_canonical_truth.py --expected-mainline PL-014 --expected-pytest-count 356`
- 关键 UI 测试用例通过
- 固定分辨率截图巡检记录

## 8. 当前结论

ProtoLink GUI 改造已经完成结构性止损与主要面板重构；后续工作应严格围绕“主次、滚动、视觉 token、文案产品化、一致性验收”五个维度推进，不再回到“大规模推翻式重做”。

本文件用于确保 GUI 后续工作以正式工程文档推进，而不是继续依赖聊天结论或临时审计口径。

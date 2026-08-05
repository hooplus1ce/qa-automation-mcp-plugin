---
name: qa-automation-guide
description: SCM/MOM/WMS/ERP 企业级 Web 自动化测试设计指南、用例矩阵设计、高韧性定位与 SOP 执行标准
---

# SCM / MOM / WMS / ERP 自动化测试与用例设计 SOP 指南

本技能为企业级复杂 Web 系统（SCM、MOM、WMS、ERP）的自动化测试架构与执行标准，指导 AI Agent 开展全自动用例录制、动态 UI 组件适配、高韧性语义定位以及 Shadcn 极简风 Excel 报表导出。

---

## 1. 核心测试设计模式矩阵 (Test Matrix)

在设计测试场景或生成步骤序列时，**禁止仅设计简单的 Happy Path 脚本**。必须自动将目标页面功能解构为以下 5 种测试模式：

### Pattern A: Happy Path (正向黄金业务流模式)
- **目标**：验证默认/中位数数据下的完整端到端业务闭环。
- **规则**：映射上游单据依赖（如预先加载PO单自动带出物料），断言终态（如 `单据状态: 已审核`）。

### Pattern B: Boundary Value Analysis (边界值极限校验模式)
- **目标**：挖掘数值、容积、日期与字符长度的数据库/业务规则极限。
- **规则**：识别字段物理上限（如库位最大承重 `5000kg`），自动设计三组输入：
  - **内边界**：`4999`（预期成功）
  - **上边界**：`5000`（预期成功）
  - **外边界**：`5001`（预期出现友好预警并阻断提交）

### Pattern C: Negative & Validation Blocking (负向及异常流拦截模式)
- **目标**：确保系统能安全拦截非法数据与逻辑违规。
- **规则**：设计至少 2 个负向步骤：
  - 必填项空值提交拦截（前端/后端校验提示）。
  - 超报拦截（如报工数量 101 大于派工单计划数 100）。
  - 异常字符/防注入测试。

### Pattern D: State Transition Machine (单据生命周期控制模式)
- **目标**：验证用户权限与 UI 控件状态是否随单据生命周期正确变化。
- **规则**：断言按钮可见性与可编辑性（如单据处于“已关单”或“已审核”状态时，“编辑”与“删除”按钮必须置灰或隐藏）。

### Pattern E: Exception & Hardware Tolerance (容错与硬件交互模式)
- **目标**：验证扫码枪重复扫码、连击防抖及网络延迟下的系统容错能力。

---

## 2. 框架穿透与 UI 适配路由规则

企业级 Web 系统交互复杂，必须动态选择适配器与 iframe 路径，避免易碎定位：

### A. 嵌套 iframe 自动穿透
- 始终分析 `analyze_current_page` 返回的 `frame_path` 链。
- 目标元素在 iframe 内时，使用链式选择器传给 `iframe_selector`（如 `#main-iframe -> iframe[name="sub-grid"]`）。

### B. UI 组件适配器行为路由
原生点击往往无法激活 Web 门户节点（Portal），需路由到对应适配器：
- **Ant Design (React):**
  - *下拉选择 (`select_option`):* 优先通过 `role=option` 语义定位，Portal 下拉层位于 `<body>` 根节点，自动穿透 iframe 上下文。
  - *日期选择 (`fill_date`):* 自动定位内部 input，解绑 `readonly` 并提交回车。
- **Element Plus (Vue):**
  - *下拉选择 (`select_option`):* 触发框点击后，跳至 `<body>` 根节点检索 `.el-select-dropdown__item` 匹配文本。
  - *日期选择 (`fill_date`):* 移除 `readonly` 后原生填充并回车。
- **SAP Fiori:**
  - *下拉选择 (`select_option`):* 点击组合框，等待 `.sapMComboBoxBoxItem` 或 `.sapMSelectListItem` 渲染后匹配文本点击。

---

## 3. 标准执行 SOP (Standard Operating Procedure)

当接收到自动化测试需求时，严格按以下步骤执行：

1. **环境与 DOM 探查**：调起 `analyze_current_page` 截取 DOM、iframe 树及 UI 框架指纹。
2. **用例矩阵规划**：打印 Markdown 格式的用例大纲（涵盖正向、边界与负向拦截场景），供用户确认。
3. **开启会话**：用户确认后调起 `start_recording` 初始化内存会话缓冲。
4. **高韧性交互录制**：按顺序调用 `execute_and_record` 或 `execute_action_chain` 执行动作，优先选用 Test ID、Label、Placeholder 或 ARIA Role 等面向用户的语义化定位器。
5. **极美资产落盘**：调用 `export_session` 将 JSON 证据保存至 `evidence_assets/`，并将 Shadcn Slate 双色调极简 Excel 报表落盘至 `output_testcases/`。

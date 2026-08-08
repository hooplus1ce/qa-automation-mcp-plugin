# 前端 Portal 弹层详解

## 什么是 Portal 弹层

在前端开发中，**Portal（传送门）** 是一种将组件的 DOM 节点插入到 DOM 树中指定位置（通常是 `document.body` 或单独的 `#modal-root` 根节点）的技术，而不是按组件正常的嵌套层级渲染在父节点内部。

由 Portal 实现的弹层（如 Dialog 弹窗、Tooltip 气泡提示、Notification 通知、Select 下拉菜单等），就称为 **Portal 弹层**。

## 为什么需要 Portal 弹层

在没有 Portal 之前，如果你在某个深度嵌套的子组件内部写了一个弹窗组件：

```html
<div class="header">
  <div class="user-card" style="overflow: hidden; z-index: 1;">
    <!-- 弹窗如果在内部，就会被 overflow: hidden 裁剪！ -->
    <div class="modal">我是弹窗</div>
  </div>
</div>
```

你会遇到前端经典的"层叠上下文与裁剪"问题：

1. **overflow: hidden 裁剪问题**：如果父容器设置了 `overflow: hidden` 或 `overflow: scroll`，弹窗尺寸超出父容器时会被截断。

2. **z-index 失效问题**：CSS 中的 z-index 是受父级的"层叠上下文（Stacking Context）"限制的。如果父元素的 z-index 很低，即便你给弹窗设置 `z-index: 9999`，它也可能会被页面上的其他元素挡住。

3. **定位层级混乱**：使用 `position: absolute` 时，它是相对于最近的 `position: relative/absolute` 父元素定位的，容易随父级滚动而错位。

### Portal 的解决方案

通过 Portal，弹窗在 React/Vue 的组件树结构中依然保留在原来的位置（保持数据流和事件传递），但在**真正的 DOM 结构**中被"传送"到了最外层（如 `<body>` 底部）。

这样弹窗就可以轻松获得完美的 `position: fixed` 和独立的顶级 z-index，彻底摆脱父级 CSS 样式的束缚。

## 主流框架中的实现方式

### 1. React (ReactDOM.createPortal)

React 原生提供了 `createPortal` API：

```jsx
import ReactDOM from 'react-dom';

function Modal({ children }) {
  // 将 content 挂载到 document.body 下，而不是当前组件的父 DOM 节点下
  return ReactDOM.createPortal(
    <div class="modal-backdrop">
      <div class="modal-content">{children}</div>
    </div>,
    document.body // 目标 DOM 节点
  );
}
```

**事件冒泡机制（核心特性）**：即便 DOM 被传到了 body 下，React 的虚拟 DOM 冒泡依然遵循 React 组件树。也就是说，在 Portal 内部点击按钮，父组件的 `onClick` 依然能捕获到这个事件！

### 2. Vue 3 (`<Teleport>`)

Vue 3 引入了内置组件 `<Teleport>`，原理与 Portal 完全一致：

```html
<template>
  <button @click="open = true">打开弹窗</button>
  <!-- to 属性指定挂载的目标 DOM 选择器 -->
  <Teleport to="body">
    <div v-if="open" class="modal">
      <p>Hello来自 Portal 弹层！</p>
      <button @click="open = false">关闭</button>
    </div>
  </Teleport>
</template>
```

## 总结：Portal 弹层的核心优势

| 维度 | 普通嵌套弹层 | Portal 弹层 |
|------|-------------|------------|
| DOM 结构 | 嵌套在父组件 DOM 内部 | 挂载在 body 或指定根节点下 |
| 受父级 CSS 影响 | 会被父级 overflow 裁剪，受父级 z-index 压制 | 彻底脱离父级样式影响 |
| 定位（Position） | 容易受父级 relative/absolute 干扰 | 轻松实现相对于视口的 fixed 居中/覆盖 |
| 状态与数据流 | 正常传递 | 保持不变（组件通信逻辑依然在原位） |

几乎所有成熟的前端 UI 组件库（如 Ant Design、Element Plus、MUI 等）中的 Modal、Drawer、Notification 组件，底层都是基于 Portal / Teleport 技术来实现的。

---

## UI 自动化框架如何处理 Portal 弹层

在 UI 自动化框架中，Portal 弹层之所以难以自动化，主要有以下**三大痛点**：

1. **DOM 结构断裂**（不在当前 DOM 节点树内）：点击按钮打开弹窗后，弹窗的 DOM 被"传送"到了 body 的最下方，用常规的相对层级 XPath（如 `//div[@class="card"]//button` 的兄弟节点）直接查找会直接报错。

2. **异步渲染延迟**：Portal 弹层通常伴随着 Enter/Leave 动画过渡，DOM 节点的挂载和可见性有延迟。

3. **多弹层/顶层遮罩压制（Z-Index 遮挡）**：多个 Portal 叠加时（如弹窗里再开选择器），普通的 Locator 可能会定位到被遮挡的旧 Portal 元素。

针对 Portal 场景，目前现代 UI 自动化框架主要通过**语义化无视 DOM 结构的定位机制**和**自适应挂载/可见性等待**来优雅解决。

### 1. Modern UI 自动化框架：Playwright（最推荐）

Playwright 是目前处理 Portal 弹层最优雅、体验最好的自动化工具。它天生就是为了解决现代 SPA（React/Vue）异步与 Portal 动态 DOM 而设计的。

**为什么 Playwright 优雅？**

- **基于 Accessible Role / Text 的全页面自动检索**：Playwright 主推 `getByRole`、`getByText` 等 Selector。它们查找元素时自动忽略 DOM 嵌套层级，在整张页面（包括被 Portal 挂载到 body 底部的节点）中查找无障碍节点。

- **内置 Auto-waiting（自动等待）**：在对 Portal 动画结束前的 DOM 节点进行操作时，Playwright 会自动等待该 Portal 完成挂载、变为可见（Visible）、且未被遮挡（Stable）后再执行点击，无需手写 sleep。

**核心解法范例：**

```javascript
// 1. 无视 Portal 的 DOM 位置，直接通过语义化角色找到弹层中的按钮
await page.getByRole('dialog', { name: '确认删除' }).getByRole('button', { name: '确定' }).click();

// 2. 处理 Popover/Select 下拉这种动态 Portal
await page.getByLabel('选择城市').click(); // 打开下拉 Portal
await page.getByRole('option', { name: '北京' }).click(); // 自动在 body 底部的 Portal 列表中找到并点击
```

> **小技巧**（定位专属 Portal 根）：如果页面上同时有多个 Portal，可以先定位 `role="dialog"` 域，再在内部进行查找，完全无需关心 DOM 在层级树里的实际位置。

### 2. 元素组件级测试框架：Testing Library (React / Vue)

如果你做的是前端组件级/集成级 UI 自动化测试（如 Jest/Vitest + React Testing Library），Testing Library 是行业标准。

**为什么它优雅？**

Testing Library 的核心哲学是"测试你的组件表现，而不是测试实现细节"。React/Vue 的 Portal 在组件逻辑上依然属于同一个 Context。

- **screen 根节点全域扫描**：使用 `screen.getByRole` 或 `screen.getByText` 时，它默认会在全局 `document.body` 节点下寻找元素。无论组件 Portal 到了哪里，screen 都能无感找到。

**核心解法范例：**

```jsx
import { render, screen, fireEvent } from '@testing-library/react';

test('测试 Portal 弹窗交互', async () => {
  render(<MyComplexPage />);
  // 点击触发 Portal 弹窗
  fireEvent.click(screen.getByRole('button', { name: '打开弹窗' }));
  // screen 直接跨越 Portal 找到全局 Body 下出现的对话框
  const modalTitle = await screen.findByRole('heading', { name: '提示信息' });
  expect(modalTitle).toBeInDOM();
});
```

### 3. Cypress（基于 Shadow / Global DOM 扫描）

Cypress 作为经典的 E2E 框架，也能较好地处理 Portal，但其思想略有不同：

- **全局 DOM 链式查询**：Cypress 默认的 `cy.get()` 也是从 document 根节点开始查找的，因此直接用 `cy.get('.ant-modal-content')` 就能直接查到 Portal 节点。

- **`cy.root()` 与 `.within()` 的避坑**：在 Cypress 中，如果使用 `cy.get('.parent-card').within(() => { cy.get('.modal') })` 这种逻辑，会因为 Portal 不在 `.parent-card` 内部而失败。优雅的解法是直接回到全局域或使用 `cy.document()` 重新切换上下文。

### 4. 传统 Selenium / Appium 生态的优雅解法

如果你使用的是 Selenium (Python/Java)，因为缺少现代框架对 Portal 的智能支持，通常需要借助设计模式来实现优雅控制：

**页面对象模型（Page Object Model）+ 显式等待（Explicit Waits）**

在 Selenium 中处理 Portal，千万不要用 Xpath 相对路径写死的父子节点。优雅的处理方式是：把 Portal 弹层声明为一个独立的 Page Component，直接用全局属性选择器定位。

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class PortalModalComponent:
    def __init__(self, driver):
        self.driver = driver
        # 直接使用全页面唯一的类名或 role 特性定位 Portal 根，不依赖触发它的父组件 DOM
        self.modal_locator = (By.CSS_SELECTOR, "body > .ant-modal-root .ant-modal")
        self.confirm_btn = (By.CSS_SELECTOR, ".ant-modal-footer .ant-btn-primary")
    
    def wait_and_confirm(self):
        # 必须显式等待 Portal 渲染挂载完成
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(self.modal_locator)
        )
        self.driver.find_element(*self.confirm_btn).click()
```

## 总结与选型建议

针对 Portal 弹层的自动化探测与交互，框架选择与处理原则如下：

### 1. 首选框架：Playwright

理由：Auto-waiting + 基于 Accessibility (Role/Label/Text) 的全局无障碍节点扫描，天然免疫 Portal 带来的 DOM 结构变形。

### 2. 核心定位策略：从"DOM 结构定位"转向"语义/属性定位"

- ❌ **不推荐**：`//div[@id='app']/div[1]/div[2]/following-sibling::div`（依赖 DOM 相对层级的 XPath 在 Portal 面前极易报废）。

- ✅ **推荐**：`page.getByRole('dialog')` 或 `css=body > .modal-container` 或 `[data-testid="confirm-modal"]`（直接拉取全局最外层的目标）。

3. **对于组件库弹层的识别技巧**：大部分成熟 UI 库（Antd、Element、MUI）的 Portal 容器都有固定的 class 挂载在 body 直属子节点（如 `.ant-modal-root`、`.el-overlay`）。在写自动化脚本时，直接将这些特殊的 Portal 挂载容器作为检索的根节点，即可实现极高的稳定度。

---

## 基于 FastMCP + Playwright + Cypress 的 UI 自动化测试平台设计

结合最新版本的 FastMCP（Model Context Protocol 标准的高级封装框架），将 Playwright 和 Cypress 优雅地结合起来构建 UI 自动化测试 Agent 平台，关键在于"分工互补、架构解耦、语义化抽象"。

Playwright 擅长跨页面全局探查与动态自适应交互，Cypress 擅长组件级沙盒内验证与确定性 E2E 校验。

### 一、整体架构设计 (Architecture)

整体平台采用**分层分工模型**，Agent 作为大脑，FastMCP 提供标准协议工具层，底层驱动 Playwright 和 Cypress 引擎：

```
+-----------------------------------------------------------------------+
| LLM Agent (决策与推理) |
+-----------------------------------------------------------------------+
| (MCP Protocol via JSON-RPC/SSE)
v
+-----------------------------------------------------------------------+
| FastMCP Engine (Tool & Resource Server) |
| - @mcp.tool (暴露原子指令与高级语义) |
| - @mcp.resource (暴露 DOM 截图、执行日志、Cypress 测试报告) |
+-----------------------------------------------------------------------+
|
+--------------------------+--------------------------+
| |
v (探查、定位、动态交互) v (断言、高频重复校验)
+-------------------------------+ +-------------------------------+
| Playwright Adapter | | Cypress Adapter |
| - Global Page Inspection | | - Micro-E2E & Component Test |
| - Dynamic Action execution | | - Fast Deterministic Engine |
| - Accessibility Role Locator | | - Time-Travel Mock & Assert |
+-------------------------------+ +-------------------------------+
```

### 两者的角色分工策略 (Dual-Engine Policy)

#### 1. Playwright (探查与感知引擎)

用于**探索（Exploration）、自适应定位、跨页面/Portal 弹层处理**以及**动作链尝试**。

当 Agent 不确定页面状态时，驱动 Playwright 抓取无障碍树（Accessibility Tree）、快照与视觉 Element 标注。

#### 2. Cypress (验证与沉淀引擎)

用于**固化断言（Assertion）、Component/Micro-E2E 快速回放**以及**Mock API 干扰隔离**。

当 Agent 确认了一条有效测试路径后，将 Playwright 的探索结果编译为 Cypress Spec 文件并运行，输出确定性的测试报告。

### 二、代码实现（Python FastMCP + TypeScript 双核）

这里以 Python 版 FastMCP 封装 Playwright 探索工具 + Cypress 校验执行器为例。

#### 1. 核心 FastMCP 服务封装 (server.py)

```python
import json
import subprocess
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from playwright.async_api import async_playwright

# 初始化 FastMCP 服务
mcp = FastMCP("UI-Automation-Agent-Platform")

# 全局 Playwright 实例上下文管理
class BrowserSession:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

session = BrowserSession()

@mcp.tool()
async def launch_browser(url: str, ctx: Context) -> str:
    """启动浏览器并导航至目标 URL"""
    await ctx.info(f"Navigating to {url}")
    session.playwright = await async_playwright().start()
    session.browser = await session.playwright.chromium.launch(headless=False)
    session.page = await session.browser.new_page()
    await session.page.goto(url)
    return f"Successfully loaded {url}"

@mcp.tool()
async def inspect_interactive_elements(ctx: Context) -> Dict[str, Any]:
    """
    优雅探查当前页面（包含 Portal 弹层/Overlay）。
    返回无障碍角色树（A11y Tree），避开深度嵌套 DOM 痛点。
    """
    if not session.page:
        raise RuntimeError("Browser not started.")
    # 获取可访问性树 (Accessibility Tree)，对 Portal 弹层极度友好
    snapshot = await session.page.accessibility.snapshot()
    return {
        "url": session.page.url,
        "title": await session.page.title(),
        "a11y_tree": snapshot
    }

@mcp.tool()
async def interact_element(
    role: str,
    name: str,
    action: str = "click",
    text_input: Optional[str] = None
) -> str:
    """
    利用 Playwright 的 Locator 语义化执行交互（支持精准拾取 Portal 弹层元素）
    """
    page = session.page
    # 优先采用角色与名称定位，完美规避 Portal 导致的 DOM 离散问题
    locator = page.getBy_role(role, name=name)
    
    if action == "click":
        await locator.click(timeout=5000)
        return f"Clicked element with role={role}, name={name}"
    elif action == "type":
        await locator.fill(text_input or "")
        return f"Typed '{text_input}' into role={role}, name={name}"
    else:
        raise ValueError(f"Unsupported action: {action}")

@mcp.tool()
async def compile_and_run_cypress_spec(spec_code: str, ctx: Context) -> str:
    """
    当 Agent 探索出有效测试路径后，生成对应的 Cypress 脚本并触发 CLI 执行，
    获取极致的确定性断言结果。
    """
    spec_path = "./cypress/e2e/agent_generated.cy.js"
    with open(spec_path, "w") as f:
        f.write(spec_code)
    
    await ctx.info("Executing generated Cypress spec...")
    # 运行 Cypress Headless 模式
    result = subprocess.run(
        ["npx", "cypress", "run", "--spec", spec_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        return f"Cypress test PASS:\n{result.stdout}"
    else:
        return f"Cypress test FAILED:\n{result.stderr}"

if __name__ == "__main__":
    mcp.run()
```

### 三、Agent 端的"探测与识别"优雅闭环设计

在平台设计中，UI 测试 Agent 的工作流包含以下 3 个核心阶段：

#### 1. 探查阶段（Agent Phase 1: Exploration）

- **语义化 DOM 过滤**：针对 Portal 弹层，驱动 Playwright 的 `page.getByRole('dialog')` 或 `page.accessibility.snapshot()`。
- **解决 Portal 痛点**：不让 Agent 依赖容易断裂的绝对/相对 DOM 路径（如 `div > div:nth-child(2)`），而是提取 Accessibility Tree，将所有的 Portal 弹层抽象为 dialog、menu、tooltip 等独立层级直接提供给 Agent。

#### 2. 探索与修正阶段（Agent Phase 2: Action Loop）

- Agent 发起 `interact_element(role="button", name="提交")`。
- FastMCP 的 Context 上报实时日志与图像（利用 FastMCP 暴露 `@mcp.resource` 截图），供 Agent 校验是否触发了期待的 Portal 弹窗。

#### 3. 沉淀与固化阶段（Agent Phase 3: Consolidation）

一旦探索成功，Agent 将操作序列翻译成 Cypress 代码：

```javascript
describe('Agent Generated Test', () => {
  it('should operate inside portal popup', () => {
    cy.visit('http://localhost:3000');
    cy.contains('button', '打开弹窗').click();
    // Cypress 全局扫描 Portal
    cy.get('.ant-modal-content').should('be.visible');
    cy.get('.ant-modal-content').contains('确定').click();
  });
});
```

调用 `compile_and_run_cypress_spec` 工具，将该生成用例纳入 CI/CD 回归库。

### 四、架构总结与优势

1. **协议层统一 (MCP Standard)**：利用 FastMCP 最新的简洁设计，将底层的浏览器控制包装为标准化的 MCP Tools，使任意 Agent（Cursor、Claude Desktop、自定义 Agent 框架）都可以无缝接入。

2. **优雅解决 Portal 弹层**：利用 Playwright 的 `getByRole` 与无障碍树作为 Agent 的"眼睛"，完全摒弃常规 DOM 树层级的干扰。

3. **探索与稳定兼得**：利用 Playwright 完成动态探索与 Portal 解决，利用 Cypress 固化回归测试与确定性断言，构建高效的 UI 自动化平台闭环。

---

## 优化方案：降低 Token 消耗与提升执行效率

要实现"降低 Token 浪费"与"加快 UI 自动化执行链路效率"的双重目标，问题的本质在于解决两个瓶颈：

1. **上下文膨胀问题**：原始 DOM/A11y 树包含大量样式、无交互属性和离散节点，导致 LLM 输入暴涨。
2. **网络与交互延迟问题**：Agent 频繁与 LLM 发生 HTTP 来回交互（LLM 决策一个动作，环境执行一次），链路延迟极高。

基于 FastMCP + Playwright + Cypress 的架构，可以通过以下 **4 个维度的优化方案** 来大幅削减 Token 并提升执行效率：

### 1. 语义树剪枝与元素编码（Context Minimization）

如果直接将 `page.accessibility.snapshot()` 全量传给 LLM，一个复杂页面可能消耗几万 Token。必须在本地 FastMCP 端进行极致剪枝。

**优化手段：**

- **扁平化索引与简写 YAML/JSON（Ref-based Element Ref）**：参照 Playwright MCP 的实现方式，将深层嵌套的 A11y 树提取为扁平化的可交互元素列表，并为每个元素赋予本地临时编号（Ref ID）。

- **过滤非交互/不可见节点**：剔除纯装饰性的 div、span、被 `display: none` 或覆盖隐藏的节点，仅保留 button, input, select, link, dialog 等具名交互角色。

**剪枝前后对比：**

```yaml
# ❌ 原始臃肿结构 (几千 Token)
- role: banner
  children:
  - role: heading
    name: Welcome
    level: 1
  - role: group
    children:
    - role: button
      name: Delete
      disabled: false
      focused: false
```

```yaml
# ✅ 优化后的精简 YAML / A11y Ref Map (不足几十 Token)
- [e1] button "Delete"
- [e2] textbox "Username" [value=""]
- [e3] dialog "Confirm Delete":
  - [e4] button "Cancel"
  - [e5] button "Confirm"
```

**效果**：每次发送给模型的页面上下文 Token 数量从 10,000+ 直接降至 300~800，压缩率达 90% 以上。

### 2. 引入 Agent 本地决策缓存与批处理（Batching & Macro Actions）

减少 LLM 与本地执行引擎的来回往返次数（Round-Trips），是提高 UI 自动化整体速度最快的方法。

**优化手段：**

- **宏动作（Macro-Actions / Action Chains）**：不要让模型"点击输入框" -> (等待) -> "输入文本" -> (等待) -> "点击提交"。扩展 FastMCP Tool，允许 Agent 一次性返回组合动作链。

```python
# 优化前：4 次 LLM 往返
# 优化后：1 次 LLM 往返，本地直接连续执行
@mcp.tool()
async def execute_action_chain(actions: list[dict]):
    """
    actions: [
      {"action": "type", "role": "textbox", "name": "账号", "value": "admin"},
      {"action": "type", "role": "textbox", "name": "密码", "value": "123456"},
      {"action": "click", "role": "button", "name": "登录"}
    ]
    """
    for act in actions:
        await perform_single_action(act)
```

- **本地状态感知校验（Avoid LLM Call on Predictable UI）**：若操作触发了前端纯表单校验或不需要模型推理的简单等待，直接在 FastMCP Adapter 端用 Playwright 的 expect 自动消化，无需将"组件重绘中"的中间态传回模型。

### 3. Dynamic Portal 空间裁剪（Modal Focus Protocol）

当页面弹出 Portal 弹层（如 Dialog/Modal/Drawer）时，页面其余背景通常处于 Mask 遮罩状态，且不可交互。此时发送全页面的 DOM 结构是纯粹的 Token 浪费。

**优化手段：**

- **Portal 自动域隔离（Focus Scope）**：FastMCP 在采集 A11y 树时，先检测页面是否存在带 `aria-modal="true"` 或特定弹层类名（如 `.ant-modal` / `.el-dialog`）的节点。

- **局部上下文发送**：如果存在 Modal 弹层，仅提取并发送该 Modal 内部的子节点树，自动剔除背景 DOM。

```python
# FastMCP 端的局部上下文提取逻辑
@mcp.tool()
async def get_focused_context() -> dict:
    # 优先查找页面中激活的 Portal 弹层
    active_modal = await page.locator('[role="dialog"], [role="alertdialog"], .modal-active').element_handle()
    
    if active_modal:
        # 仅仅只获取 Modal 内部的 A11y 节点，背景页面内容直接丢弃！
        return {"scope": "modal", "tree": await get_a11y_tree(active_modal)}
    return {"scope": "page", "tree": await get_a11y_tree(page)}
```

### 4. Cypress 测试代码生成模式（AST 编译生成）

在将 Playwright 的探查链路转化为 Cypress Spec 时，很多平台倾向于让大模型生成完整的 JS 代码，这不仅容易产生语法错误，还会消耗大量 Output Token。

**优化手段：**

- **结构化 JSON Schema 替代纯文本代码生成**：让 LLM 只输出极其紧凑的操作 Intent JSON，由 FastMCP 本地框架通过模板或 AST（抽象语法树）翻译为 Cypress 校验代码。

```json
// LLM 只需要输出极简的 JSON (极其节省 Output Token):
{
  "test_name": "Portal Delete Flow",
  "steps": [
    {"type": "click", "target": "button:has-text('删除')"},
    {"type": "assert_visible", "target": ".ant-modal-content"},
    {"type": "click", "target": ".ant-modal-footer button:has-text('确定')"}
  ]
}
```

- **本地模板编译**：FastMCP 接手该 JSON，使用本地 Jinja2 或 AST 动态生成符合规范的 Cypress `.cy.js` 脚本并驱动运行。

### 5. 优化后的全链路时序对比 (Architecture Workflow)

**[旧模式]**
```
LLM <--- (传递 10,000 Token 完整 DOM) ---> FastMCP ---> 执行 1 次 Click
LLM <--- (传递 10,000 Token 完整 DOM) ---> FastMCP ---> 执行 1 次 Input 
... (链路极慢且贵)
```

**[新模式 (经过上述优化)]**
```
LLM <--- (发送剪枝后的 300 Token A11y 树) --- FastMCP (检测到 Portal 自动裁剪背景)
LLM ---> (返回批量 Macro-Action 动作链) ---> FastMCP (本地 Playwright 快速无缝连续执行)
LLM ---> (输出极简步骤 JSON) ---> FastMCP (本地生成 Cypress 代码并纳入回归库)
```

### 总结收益对比

| 优化维度 | 优化前 | 优化后 | 收益 |
|---------|--------|--------|------|
| Input Token / 次 | ~10,000+ | ~300 - 800 | Token 节省 90% 以上 |
| Output Token / 次 | 大量 JS 代码串 (~1,500) | 结构化 Intent JSON (~150) | 响应速度提升 3~5 倍 |
| 网络往返次数 (RTT) | 每个 Action 1 次 | 1 轮探查发起多动作链 | 交互时延降低 60% |
| Portal 处理 | 包含全页杂音，易定错元素 | 域隔离，只感知 Modal 内部 | 定位准确率接近 100% |

**参考资料**
- Accessibility | Playwright
- Snapshot testing | Playwright Python
- FastMCP: The Framework for MCP

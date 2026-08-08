# QA Automation Plugin (Claude Code / Desktop 插件)

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.4-green)](https://gofastmcp.com/)
[![Playwright](https://img.shields.io/badge/Playwright-CDP-orange)](https://playwright.dev/)
[![License](https://img.shields.io/badge/license-MIT-brightgreen)](#)

企业级 Web 系统（SCM / MOM / WMS / ERP）自动化测试 **Claude Code & Claude Desktop 插件**。

通过 Playwright CDP 接管本地物理 Chrome 浏览器，提供 DOM/iframe 语义分析、高韧性点击输入、批量动作链、VTable 场景图渲染层交互、动态浮层探查、测试用例实时录制、文件下载/上传控制以及 Shadcn 极简风格 Excel 报表与证据 JSON 一键落盘导出（内置 **27 个 MCP 工具** + **测试设计 SOP 技能指南**）。

---

## 目录

- [核心架构设计与原理总结](#核心架构设计与原理总结)
- [项目目录结构](#项目目录结构)
- [前置条件与环境准备](#前置条件与环境准备)
- [插件安装与使用 SOP](#插件安装与使用-sop)
  - [方式一：Claude Desktop 导入 ZIP 插件包（推荐生产使用）](#方式一claude-desktop-导入-zip-插件包推荐生产使用)
  - [方式二：Claude Code 插件加载与市场安装](#方式二claude-code-插件加载与市场安装)
  - [方式三：常规 MCP 客户端直接接入（Cursor / VS Code / Claude Desktop 手动配置）](#方式三常规-mcp-客户端直接接入cursor--vs-code--claude-desktop-手动配置)
- [MCP 工具与 SOP 技能清单](#mcp-工具与-sop-技能清单)
- [开发验证与单元测试](#开发验证与单元测试)

---

## 核心架构设计与原理总结

在项目设计与优化过程中，针对 MCP 插件的生命周期、环境打包、变量注入与启动性能得出了以下核心架构原理与结论：

### 1. 无需打包 `.venv` 的“现场自动建环”机制
- **零体积发布**：分发 Zip 插件包时**绝对不需要**包含庞大的 `.venv` 虚拟环境，打出的插件 Zip 包体积仅 **~200 KB**。
- **外层 `uv run` 负责环境感知与现场构建**：当 MCP 客户端启动插件时，命令最外层的 `uv run` 会首先检查插件目录下是否存在 `.venv`。若不存在，`uv` 会读取 `fastmcp.json` / `pyproject.toml` 依赖声明，在目标机器上自动下载 Python 环境并瞬间构建虚拟环境、安装依赖。
- **内层 `--skip-env` 防止二次建环死循环**：子命令 `fastmcp run --skip-env fastmcp.json` 中的 `--skip-env` 标志用于告知 FastMCP 内部 CLI 引擎：*“外层 `uv` 已经完成了虚拟环境的创建与激活，FastMCP 无需在内部重复拉起 `uv` 嵌套构建”*。此举杜绝了死循环，并将服务启动耗时缩短至毫秒级。
- **`uv.lock` 随包分发锁定依赖**：依赖解析结果（含全部传递依赖）提交在 `uv.lock` 中并随 Zip 包分发，用户机器首次 `uv run` 严格按锁定版本建环。杜绝 `pyproject.toml` 范围依赖（如 `playwright>=1.60`）在用户侧解析到新版本导致的“开发环境正常、用户环境异常”。（修改 `pyproject.toml` 依赖后需重新生成：`uv lock` 或直接 `uv add`。）

### 2. 插件全局挂载与 `${CLAUDE_PLUGIN_ROOT}` 路径寻址
- **解决 `not loaded` 的关键**：在 Claude Code / Claude Desktop 插件体系中，用户安装插件后，插件文件解压挂载在插件系统的全局路径下（如 `~/.claude/plugins/qa-automation-plugin/`）。当用户在任意其他工作区目录使用该插件时，如果没有指定 `--directory "${CLAUDE_PLUGIN_ROOT}"`，`uv` 会在用户当前工作区寻找 `fastmcp.json`，从而导致找不到配置文件并引发 **`qa-automation-mcp: not loaded`** 加载失败。
- **`${CLAUDE_PLUGIN_ROOT}` 自动注入与挂载**：在 `.claude-plugin/plugin.json` 与 `.mcp.json` 中配置 `--directory "${CLAUDE_PLUGIN_ROOT}"`，确保了无论用户在电脑上的哪个项目路径下触发插件，`uv` 都能准确跳至插件的实际安装根目录去加载 `fastmcp.json` 并激活环境，实现跨目录、跨项目的全局无缝调用。
### 3. 用户项目根目录 (`CLAUDE_PROJECT_DIR`) 与相对路径锚定
- **进程 cwd ≠ 用户项目**：插件化部署时 MCP 服务进程 cwd 是插件安装目录（见第 2 点），若相对路径按 cwd 解析，`describe_image` 的图片入参（粘贴图片、`capture_screenshot` 落盘的 `evidence_assets/` 截图地址）以及 `download_file` / `upload_file` / `export_session` 的文件路径都会解析到插件目录，导致"找不到图片/文件"。
- **`CLAUDE_PROJECT_DIR` 还原用户项目根**：Claude Code 启动 MCP 服务时会向子进程注入 `CLAUDE_PROJECT_DIR` 环境变量（用户当前项目根目录）。`src/qa_mcp/config.py` 以 `PROJECT_DIR = CLAUDE_PROJECT_DIR > 进程 cwd` 解析项目根，所有相对目录（`evidence_assets/`、`output_testcases/`、`downloads/`）与工具的相对路径入参（图片/上传文件）统一锚定到用户项目根，其次回退进程 cwd，保证在任意工作区使用插件时图片识别与文件读写都能正确命中。
### 4. 全面支持 Python 3.14 稳定版与向下兼容
- 项目依赖规范配置为 `requires-python = ">=3.11"`（`pyproject.toml`）与 `"python": ">=3.11"`（`fastmcp.json`）。
- 完全支持已正式发布的 **Python 3.14 稳定版**，同时对 Python 3.11 / 3.12 / 3.13 保持向下兼容。

---

## 项目目录结构

```text
qa-automation-plugin/
├── .claude-plugin/
│   ├── plugin.json           # 插件主清单 (定义名称、版本、mcpServers 与 skills 显式映射)
│   └── marketplace.json      # 插件市场注册清单 (定义 Marketplace 索引与 GitHub 源码源)
├── .mcp.json                 # 工作区 MCP 配置 (用于开发者在本项目根目录下直接调试)
├── fastmcp.json              # FastMCP 声明式服务、入口与依赖配置
├── pyproject.toml            # Hatchling 构建与项目依赖声明 (包含 pytest 开发依赖组)
├── .env.example              # 环境变量配置模板
├── prompts/                  # 按需读取的提示词模板 (未注册 Skill, 不自动注入上下文)
├── skills/
│   └── qa-automation-guide/
│       └── SKILL.md          # SCM/MOM/WMS/ERP Web 自动化测试 SOP 技能指南
├── src/qa_mcp/               # FastMCP 3.x 服务源码
│   ├── server.py             # 服务装配入口 (Lifespan, Middleware, Provider 与导出工具)
│   ├── config.py             # 统一超时、轮询与环境变量配置
│   ├── providers/            # FastMCP Provider 扩展 (BrowserProvider, VTableProvider)
│   ├── tools/                # 25 个 MCP 核心工具实现 (browser, vtable, recorder, vision 等)
│   └── utils/                # UI 组件适配器、场景图 JS 注入脚本与 Shadcn Excel 渲染器
└── tests/                    # 单元测试套件 (127 个自动化测试用例)
```

---

## 前置条件与环境准备

1. **安装必要工具**：
   - 已安装 [Claude Code](https://code.claude.com) 或 [Claude Desktop](https://claude.ai/download)。
   - 已安装 [uv](https://docs.astral.sh/uv/)（Python 包与环境管理工具）。
   - 环境支持 Python 3.11、3.12、3.13 或 **3.14+**。

2. **启动本地物理 Chrome 远程调试端口**：
   Playwright CDP 需连接至开启调试端口的 Chrome 实例，在终端运行：
   - **Windows**:
     ```cmd
     chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Temp\ChromeDebugProfile"
     ```
   - **macOS**:
     ```bash
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/ChromeDebugProfile"
     ```

3. **配置环境变量（可选）**：
   复制项目模板并根据需要调整配置：
   ```bash
   cp .env.example .env
   ```
   - `CDP_URL`: Chrome CDP 调试地址（默认 `http://127.0.0.1:9222`）。
   - `VISUAL_EFFECTS`: 是否开启鼠标点击与定位框可视化高亮（默认 `true`）。
   - `VISION_API_KEY`: 腾讯云 TokenHub GLM-5V 视觉 API Key（仅当主模型为纯文本模型需要图像理解降级时配置）。
   - `ELEMENT_WAIT_TIMEOUT_MS`: 元素定位等待超时（click/fill/select/press 的 wait_for visible，默认 `10000`ms）。
   - `ACTION_STEP_TIMEOUT_MS`: 动作链单步执行上限（默认 `90000`ms；单步超时记为失败，防止链中一个死动作堵死整条链）。
   - `TOOL_MAX_EXECUTION_MS`: 全局工具执行看门狗（默认 `300000`ms；Chrome 假死/CDP 连接半开时协议调用可能无限等待，超时后强制中断、释放串行队列并重置浏览器连接）。

---

## 插件安装与使用 SOP

### 方式一：Claude Desktop 导入 ZIP 插件包（推荐生产使用）

1. **打包插件（开发者）**：
   直接将项目根目录下除 `.venv`、`__pycache__` 外的文件打包为 `qa-automation-plugin.zip`（体积约 200KB）。
2. **导入 Claude Desktop**：
   - 打开 Claude Desktop $\rightarrow$ 设置 $\rightarrow$ Plugins / MCP Servers $\rightarrow$ 选择导入 `qa-automation-plugin.zip`。
3. **自动运行**：
   - Claude Desktop 会解压插件到本地插件目录。
   - 首次触发时外层 `uv run` 自动建环并安装依赖，内层 `--skip-env` 快速调起 MCP 服务。
4. **首次启用预热（重要，避免"连接中"卡死）**：
   - 插件首次启用时，客户端调用 `uv run` 现场构建虚拟环境并安装依赖（
     fastmcp/playwright 等，首次约 20-60 秒）。部分客户端（如 Claude Desktop
     cowork）对 MCP 服务启动存在超时窗口，若首次依赖安装未完成即被中断，
     服务会一直显示"连接中"、工具加载不出来。
   - **遇到"连接中"时**：在插件安装目录执行一次预热，再重启客户端：
     ```bash
     uv sync --no-dev --directory "<插件安装目录>"
     ```
     插件安装目录示例（Claude Desktop）：`%LOCALAPPDATA%\Claude-3p\
     local-agent-mode-sessions\<账号>\00000000\cowork_plugins\cache\
     qa-automation-plugins\qa-automation-plugin\<版本>\`
   - 预热幂等（依赖已装时秒级完成）；**每次通过 Update 更新插件后建议重新
     预热一次**——更新会重置插件目录，依赖需重装，uv 全局缓存使重装仅需
     数秒到数十秒，远快于首次。

### 方式二：Claude Code 插件加载与市场安装

- **本地开发调试**：
  在 Claude Code 中直接指定插件目录运行：
  ```bash
  claude --plugin-dir ./qa-automation-plugin
  ```
- **通过 Marketplace 安装**：
  在 Claude Code 中添加市场并安装：
  ```bash
  /plugin marketplace add hooplus1ce/qa-automation-plugin
  /plugin install qa-automation-plugin
  ```

### 方式三：常规 MCP 客户端直接接入（Cursor / VS Code / Claude Desktop 手动配置）

若不使用插件包装机制，可以直接在客户端配置（如 `~/.claude/claude_desktop_config.json` 或 `.cursor/mcp.json`）中添加 `mcpServers`：

```json
{
  "mcpServers": {
    "qa-automation-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/绝对路径/到/qa-automation-plugin",
        "fastmcp",
        "run",
        "--skip-env",
        "fastmcp.json"
      ],
      "env": {
        "CDP_URL": "http://127.0.0.1:9222",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## MCP 工具与 SOP 技能清单

项目共装配 **27 个 MCP 核心工具** 及 **1 个企业级 Web 测试设计 SOP 技能**：

### 1. 基础页面分析与交互工具 (13 个)
- `analyze_current_page`: 递归分析 DOM 及嵌套 iframe，生成可见交互元素定位器。
- `click_interact`: 统一点击工具（支持 CSS/XPath、get_by_role 语义定位、视口坐标点击，附带弹窗浮层与跳转观察）。
- `fill_input`: 文本框填充（支持清空、逐字模拟键盘输入、回车触发）。
- `execute_action_chain`: 批量动作链顺序执行（含 fallback 变体容错与降级机制）。
- `probe_dynamic_layers`: 探查页面/iframe 出现的可见弹窗、下拉悬浮层及消息气泡。
- `wait_for_condition`: 页面条件轮询等待（文本出现/元素可见/URL跳转）。
- `download_file`: 点击触发下载的按钮/链接，下载文件落盘到指定目录（默认 ./downloads）并验证，供后续读取分析（如 xlsx 用 pandas 编辑）。
- `upload_file`: 点击上传按钮/输入框注入指定文件（input 直设或 filechooser 拦截），可选等待"上传成功"反馈验证。
- `capture_screenshot`: CDP 原生无卡顿截屏（支持整页或视口，生成 PNG 及文件凭证）。
- `switch_target_page`: 显式重绑/锁定 MCP 操作的目标标签页。
- `describe_image`: 纯文本主模型环境下的视觉理解降级工具（GLM-5V 流式解析，返回思考过程与回答）。
- `start_recording`: 初始化测试用例录制会话。
- `execute_and_record`: 执行动作并自动记录最优高韧性语义定位步骤。

### 2. VTable 场景图表格交互工具 (13 个)
- `vtable_refresh_instance`: 挂载并刷新 Canvas 渲染表格的 `window._vtable` 实例。
- `vtable_analyze_headers`: 【场景图驱动】分析列头图标与单元格交互组件。
- `vtable_scan_columns`: 【推荐】扫描全部列头及视口坐标（直接传给坐标点击）。
- `vtable_get_row_count`: 获取表格纯数据总行数。
- `vtable_get_all_records`: 一次性读取整表后台行记录 JSON。
- `vtable_get_cell_text`: 读取指定单元格展示文本（可读取场景图渲染层）。
- `vtable_get_column_values`: 按中文列标题批量提取列数据。
- `vtable_get_cell_render_info`: 读取单元格场景图渲染详情（颜色/背景色/字体/节点）。
- `vtable_get_cell_center`: 计算单元格中心顶层视口坐标。
- `vtable_scroll_to`: 精确滚动 VTable 表格到指定行/列/坐标。
- `vtable_select_rows`: 勾选/取消勾选 Canvas 表格多行复选框。
- `vtable_drag_column`: 复刻真实鼠标拖拽移动 VTable 列位置。
- `vtable_resize_column`: 复刻真实鼠标拖拽 VTable 列头分隔线调整列宽（拖后自动校验）。

### 3. 会话导出工具 (1 个)
- `export_session`: 结束录制，生成证据 JSON 资产并落盘 Shadcn 极简风格 Excel 报表。

### 4. Agent SOP 技能
- `qa-automation-guide`: 提供 SCM/MOM/WMS/ERP 测试矩阵设计模式（Pattern A~E）及 UI 框架穿透路由标准。

---

## 开发验证与单元测试

在项目修改或扩展后，请执行以下命令进行完整验证：

```bash
# 1. 验证 Claude Plugin 清单格式与 Marketplace 架构
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json

# 2. 检查 FastMCP 服务工具装配与状态
uv run fastmcp list src/qa_mcp/server.py

# 3. 运行自动化单元测试套件 (包含 127 个测试用例)
uv run pytest
```

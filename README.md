# qa-automation-mcp-plugin

SCM/MOM/WMS/ERP 企业级 Web 自动化测试 **Claude Code Plugin**：通过 Playwright CDP 接管本地 Chrome，提供页面元素分析、点击/输入/动作链、动态层探查、VTable 场景图交互、用例录制与 Shadcn 风格 Excel 资产导出（24 个 MCP 工具 + 测试设计 SOP 技能）。

## 目录结构

```text
qa-automation-mcp-plugin/
├── .claude-plugin/
│   ├── plugin.json           # 插件清单 (定义名称、版本、mcpServers 与 skills 映射，使用 ${CLAUDE_PLUGIN_ROOT})
│   └── marketplace.json      # 插件市场注册清单 (定义插件源与元数据)
├── .mcp.json                 # 本地工作区 MCP 配置文件 (开发者直接在本项目中调试使用)
├── fastmcp.json              # FastMCP 声明式服务与依赖配置
├── pyproject.toml            # 项目依赖声明 (支持 Python >=3.11 及 Python 3.14 稳定版)
├── src/qa_mcp/               # MCP 服务源码 (Provider/Tools/Middleware/Lifespan)
├── skills/
│   └── qa-automation-guide/  # SCM/MOM/WMS/ERP 测试设计 SOP 技能指南
└── tests/                    # 单元测试 (76 个测试用例)
```

## 前置条件

1. 已安装 [Claude Code](https://code.claude.com) / [Claude Desktop](https://claude.ai/download) 与 [uv](https://docs.astral.sh/uv/) (支持 Python >=3.11，包含 Python 3.14 稳定版)。
2. 本地 Chrome 以调试端口启动：
   ```bash
   chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Temp\ChromeDebugProfile"
   ```
3. （可选）在 `.env` 中配置 `MIMO_API_KEY` 以启用视觉降级识别工具。

## 安装与使用

### 方式一：Claude Desktop / Claude Code 导入 Zip 插件包（推荐生产使用）

1. 项目仅需打包源码文件（无需打包 `.venv` 虚拟环境，压缩包仅 200KB 左右）。
2. 在 Claude Desktop 中导入 zip 插件包或添加 Marketplace。
3. **自动建环机制**：外层 `uv run` 会在首次运行时根据 `fastmcp.json` / `pyproject.toml` 自动下载 Python 并构建 `.venv`；内层的 `--skip-env` 标志确保在已准备好的环境中毫秒级拉起 FastMCP 服务，无需手工执行 `uv sync`。

### 方式二：本地目录直接加载（插件开发调试）

```bash
claude --plugin-dir ./qa-automation-mcp-plugin
```

### 方式三：常规 MCP 接入（工作区直接调试）

在目标项目的 `.mcp.json` 中配置：

```json
{
  "mcpServers": {
    "qa-automation-mcp": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "--skip-env", "fastmcp.json"],
      "env": { "CDP_URL": "http://127.0.0.1:9222" }
    }
  }
}
```
## 验证

```bash
# 校验插件清单与市场清单
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json

# 列出 MCP 工具 (包含 24 个工具 + Skills Provider)
uv run fastmcp list src/qa_mcp/server.py

# 运行单元测试
uv run pytest
```

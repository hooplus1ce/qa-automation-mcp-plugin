# qa-automation-mcp-plugin

SCM/MOM/WMS/ERP 企业级 Web 自动化测试 **Claude Code Plugin**：通过 Playwright CDP 接管本地 Chrome，提供页面元素分析、点击/输入/动作链、动态层探查、VTable 场景图交互、用例录制与 Shadcn 风格 Excel 资产导出（24 个 MCP 工具 + 测试设计 SOP 技能）。

## 目录结构

```text
qa-automation-mcp-plugin/
├── .claude-plugin/
│   └── plugin.json           # 插件清单 (名称/版本/作者)
├── .mcp.json                 # 插件 MCP 服务器配置 (${CLAUDE_PLUGIN_ROOT} 可移植路径)
├── fastmcp.json              # FastMCP 声明式服务配置
├── src/qa_mcp/               # MCP 服务源码 (Provider/Tools/Middleware/Lifespan)
├── skills/
│   └── qa-automation-guide/  # 测试设计 SOP 技能
└── tests/                    # 单元测试
```

## 前置条件

1. 已安装 [Claude Code](https://code.claude.com) 与 [uv](https://docs.astral.sh/uv/)。
2. 本地 Chrome 以调试端口启动：
   ```
   chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Temp\ChromeDebugProfile"
   ```
3. （可选）在 `.env` 中配置 `MIMO_API_KEY` 以启用视觉降级识别工具。

## 安装与使用

### 方式一：本地目录直接加载（开发调试）

```bash
claude --plugin-dir ./qa-automation-mcp-plugin
```

### 方式二：安装为全局插件（发布后）

```bash
# 在 Claude Code 中执行
/plugin install <marketplace>/qa-automation
```

### 方式三：常规 MCP 接入（非插件环境）

在目标项目的 `.mcp.json` 中配置：

```json
{
  "mcpServers": {
    "qa-automation-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/qa-automation-mcp-plugin", "fastmcp", "run", "fastmcp.json"],
      "env": { "CDP_URL": "http://127.0.0.1:9222" }
    }
  }
}
```

首次启动时 FastMCP 会自动在插件目录下用 uv 构建虚拟环境，无需手动 `uv sync`。

## 验证

```bash
# 本地测试插件
claude plugin validate .

# 列出 MCP 工具
uv run fastmcp list src/qa_mcp/server.py

# 运行单元测试
uv run python -m unittest discover tests
```

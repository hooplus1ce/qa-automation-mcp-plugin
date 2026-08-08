# QA Automation Plugins (Claude Code 插件市场)

Claude Code **插件市场仓库**（官方 marketplace 布局），托管企业级 Web 自动化测试插件：

- 市场清单：`.claude-plugin/marketplace.json`（官方 `plugins/` 子目录 + 相对路径 source 布局）
- 插件本体：`plugins/qa-automation-plugin/`（含独立 `.claude-plugin/plugin.json` 清单）

## 目录结构

```text
qa-automation-plugin/
├── .claude-plugin/
│   └── marketplace.json              # 市场清单 (name/owner/plugins[].source)
├── plugins/
│   └── qa-automation-plugin/         # 插件根目录 (独立可分发)
│       ├── .claude-plugin/
│       │   └── plugin.json           # 插件清单 (mcpServers + skills)
│       ├── skills/                   # Agent Skills（设计 SOP + 场景复验，按需加载）
│       ├── src/qa_mcp/               # FastMCP 3.x 服务源码
│       ├── tests/                    # 单元测试
│       ├── fastmcp.json              # FastMCP 声明式服务配置
│       ├── pyproject.toml / uv.lock  # Python 依赖声明与锁定
│       └── README.md                 # 插件详细文档
└── .mcp.json.example                 # 手动接入 MCP 客户端的工作区示例
```

## 安装

**Claude Code（CLI）：**

```bash
/plugin marketplace add hooplus1ce/qa-automation-plugin
/plugin install qa-automation-plugin@hoolinks
```

**Claude Desktop（桌面应用）：** Desktop 与 CLI 共享 marketplace 配置，分两步：

1. 先在 Claude Code CLI 中执行一次 `/plugin marketplace add hooplus1ce/qa-automation-plugin`（或在受管环境中由管理员通过 `extraKnownMarketplaces` 预注册）。
2. 在桌面应用 Code 标签页的会话中，点击输入框旁 **+** → **Plugins** → **Add plugin**，在插件浏览器中找到 **QA Automation Plugin** 安装即可（可选 user/project/local 作用域）。

> 云会话不支持插件浏览器；需在仓库 `.claude/settings.json` 的 `enabledPlugins` 中声明插件名。
> 无需 CLI 时也可走 ZIP 导入：见插件 README「方式一」。

## 本地开发调试

```bash
# 直接以插件目录加载 (跳过市场安装)
claude --plugin-dir ./plugins/qa-automation-plugin

# 校验市场清单与插件清单
claude plugin validate .
claude plugin validate plugins/qa-automation-plugin --strict

# 运行插件单元测试
uv run --directory plugins/qa-automation-plugin pytest
```

详细功能、安装 SOP 与环境准备见 [`plugins/qa-automation-plugin/README.md`](plugins/qa-automation-plugin/README.md)。

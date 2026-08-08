"""prompts/ 目录模板 → MCP Prompts 注册器。

将项目内 prompts/*.md 参数化模板暴露为 MCP 协议层 prompts
(list_prompts / get_prompt)。关键语义: prompts 只在客户端**显式请求**
时才渲染, 不会自动注入任何对话上下文——与项目"按需读取, 不自动注入"
的提示词形态约束一致。

模板文件约定 (见 prompts/ui-automation-test-template.md):
- 正文包裹在 ```markdown 代码块中 (代码块之外为使用说明/速查表, 不输出)
- 正文内 {中文占位符} 即 prompt 参数; 客户端提供值后渲染时替换,
  未提供的参数保留占位符原文 (由调用方模型自行确认填写)
- 一个模板文件 = 一个 prompt, 文件名 (去 -template 后缀) 即 prompt 名
"""

import re
from pathlib import Path
from typing import Callable

from fastmcp import FastMCP
from fastmcp.prompts.prompt import Prompt

# 中文占位符 → 英文参数名 (MCP 客户端参数名须为合法标识符)。
# 未收录的占位符自动命名为 param_<N>, 渲染仍按 {占位符} 原文替换。
PLACEHOLDER_TO_PARAM: dict[str, str] = {
    "测试用例文档": "test_case_doc",
    "子表名": "sheet_name",
    "过滤字段": "filter_field",
    "过滤值": "filter_value",
    "被测系统 URL": "system_url",
    "账号": "account",
    "执行人": "executor",
    "证据根目录": "evidence_root",
    "报告路径": "report_path",
    "Bug 系统": "bug_system",
}

_CODE_BLOCK_RE = re.compile(r"```markdown\s*\n(.*?)```", re.S)
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")
# 速查表数据行: 以 | 开头且含 {占位符} (支持一格多占位符, 如 "| {被测系统 URL} / {账号} |")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\{[^}]+\}.*$", re.M)


def extract_template_body(md_text: str) -> str:
    """提取模板正文: 优先取 ```markdown 代码块, 无代码块则返回全文。"""
    m = _CODE_BLOCK_RE.search(md_text)
    return m.group(1).strip() if m else md_text.strip()


def extract_placeholders(md_text: str) -> list[str]:
    """提取参数占位符集合 (去重保序)。

    权威来源是代码块外的"占位符速查表" (表格数据行内的全部 {xxx}) ——
    正文中的 {xxx} 混杂格式示例 (如 "{二级模块}/{用例ID}_{步骤}.png"、
    "{Bug 系统=禅道}"), 不能作为参数。无速查表时回退: 正文中不含 '=' 与
    '/' 的 {xxx}。
    """
    outside = _CODE_BLOCK_RE.sub("", md_text)
    seen: list[str] = []
    for line in outside.splitlines():
        if _TABLE_ROW_RE.match(line):
            # 只取第一格 (首个 | 与第二个 | 之间): 支持一格多占位符
            # (如 "| {被测系统 URL} / {账号} |"), 排除后续单元格中的示例
            first_cell = line.split("|", 2)[1]
            for ph in _PLACEHOLDER_RE.findall(first_cell):
                if ph not in seen:
                    seen.append(ph)
    if seen:
        return seen
    # 回退: 正文占位符, 排除带默认值说明 (=) 与路径格式 (/) 的示例
    body = extract_template_body(md_text)
    for ph in _PLACEHOLDER_RE.findall(body):
        if ph not in seen and "=" not in ph and "/" not in ph:
            seen.append(ph)
    return seen


def _apply_placeholders(
    body: str, mapping: dict[str, str], values: dict[str, str]
) -> str:
    """渲染: 有值的参数 (按 参数名→占位符 映射) 替换 (含 "{参数=默认值}" 变体),
    未提供保留原文。"""
    text = body
    for param_name, ph in mapping.items():
        value = values.get(param_name, "")
        if value:
            text = re.sub(r"\{" + re.escape(ph) + r"(?:=[^}]*)?\}", value, text)
    return text


def _build_render_fn(
    body: str, placeholders: list[str]
) -> Callable[..., str]:
    """为模板动态构造带固定参数签名的渲染函数。

    不能使用 **kwargs: FastMCP 需要为 MCP 协议生成完整参数 schema
    (可变参数列表不支持), 故按占位符集合生成具名参数 (均带默认值 = 可选)。
    """
    params: list[str] = []
    mapping: dict[str, str] = {}  # 参数名 → 中文占位符
    for i, ph in enumerate(placeholders):
        param_name = PLACEHOLDER_TO_PARAM.get(ph, f"param_{i}")
        params.append(f"{param_name}: str = ''")
        mapping[param_name] = ph
    ns: dict = {
        "_body": body,
        "_mapping": mapping,
        "_apply": _apply_placeholders,
    }
    src = (
        "def _render(" + ", ".join(params) + "):\n"
        "    return _apply(_body, _mapping, dict(locals()))\n"
    )
    exec(src, ns)  # noqa: S102 - 参数名来自受控映射表, 非外部输入
    return ns["_render"]  # type: ignore[return-value]


def register_prompt_templates(mcp: FastMCP, prompts_dir: str | Path) -> list[Prompt]:
    """扫描 prompts_dir 下所有 *.md, 逐一注册为 MCP prompt。

    返回已注册的 Prompt 列表 (便于测试断言)。
    """
    root = Path(prompts_dir)
    registered: list[Prompt] = []
    if not root.is_dir():
        return registered
    for md_file in sorted(root.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        body = extract_template_body(text)
        if not body:
            continue
        placeholders = extract_placeholders(text)
        name = md_file.stem.removesuffix("-template")
        description = f"UI 自动化测试执行提示词模板 ({md_file.stem})"
        fn = _build_render_fn(body, placeholders)
        prompt = Prompt.from_function(
            fn,
            name=name,
            description=description,
            tags={"qa", "ui-test"},
        )
        mcp.add_prompt(prompt)
        registered.append(prompt)
    return registered

"""prompts_registry 单元测试: prompts/ 模板目录 → MCP Prompts 注册与渲染。"""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastmcp import FastMCP

from qa_mcp.prompts_registry import (
    PLACEHOLDER_TO_PARAM,
    extract_placeholders,
    extract_template_body,
    register_prompt_templates,
)

TEMPLATE_MD = """# 测试模板

> 使用说明：这行不应出现在 prompt 正文中。

```markdown
执行任务：对 {文档} 中的 {子表} 执行测试，账号 {账号}。
```

## 占位符速查

| 占位符 | 含义 |
|---|---|
| {文档} | 文档路径 |
"""


class TestTemplateParsing(unittest.TestCase):
    def test_extract_template_body_takes_code_block_only(self):
        body = extract_template_body(TEMPLATE_MD)
        self.assertEqual(body, "执行任务：对 {文档} 中的 {子表} 执行测试，账号 {账号}。")
        self.assertNotIn("使用说明", body)

    def test_extract_placeholders_from_spec_table(self):
        # 权威来源: 速查表 (表格行内全部占位符), 正文格式示例不混入
        self.assertEqual(extract_placeholders(TEMPLATE_MD), ["文档"])

    def test_extract_placeholders_fallback_to_body(self):
        # 无速查表: 回退正文占位符, 排除 '='(默认值说明) 与 '/'(路径) 变体
        md = "```markdown\nA {x} B {y=默认} C {dir}/{file}\n```"
        self.assertEqual(extract_placeholders(md), ["x", "dir", "file"])

    def test_unknown_placeholder_gets_param_n_name(self):
        body = "只含未知占位符 {未知项}"
        registry = FastMCP("test")
        register_prompt_templates(registry, _tmp_dir_with("unknown.md", f"```markdown\n{body}\n```"))

        async def scenario():
            prompts = await registry.list_prompts()
            self.assertEqual(len(prompts), 1)
            arg_names = [a.name for a in prompts[0].arguments]
            self.assertIn("param_0", arg_names)
            self.assertNotIn("未知项", arg_names)

        asyncio.run(scenario())


class TestPromptRegistration(unittest.TestCase):
    def test_registers_and_renders_real_template(self):
        registry = FastMCP("test")
        prompts_dir = PROJECT_ROOT / "prompts"
        registered = register_prompt_templates(registry, prompts_dir)
        self.assertTrue(registered, "prompts/ 下应有模板被注册")

        async def scenario():
            prompts = await registry.list_prompts()
            by_name = {p.name: p for p in prompts}
            self.assertIn("ui-automation-test", by_name)
            prompt = by_name["ui-automation-test"]
            self.assertEqual(prompt.name, "ui-automation-test")
            self.assertIn("ui-test", prompt.tags)

            # 10 个已知占位符全部成为可选参数
            arg_names = [a.name for a in prompt.arguments]
            expected = sorted(PLACEHOLDER_TO_PARAM.values())
            self.assertEqual(sorted(arg_names), expected)

            # 渲染: 提供部分参数 → 对应占位符被替换, 未提供保留原文
            rendered = await prompt.render(
                {"test_case_doc": "用例V2.0", "executor": "Hoo"}
            )
            text = rendered.messages[0].content.text
            self.assertIn("用例V2.0", text)
            self.assertIn("Hoo", text)
            self.assertIn("{子表名}", text)  # 未提供 → 占位符保留, 交由模型确认
            self.assertNotIn("{测试用例文档}", text)

        asyncio.run(scenario())


def _tmp_dir_with(filename: str, content: str) -> Path:
    tmp = Path(tempfile.mkdtemp())
    (tmp / filename).write_text(content, encoding="utf-8")
    return tmp


if __name__ == "__main__":
    unittest.main()

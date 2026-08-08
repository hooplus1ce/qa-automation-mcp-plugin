"""vision.py 单元测试: API Key 加载 / 图片解析 / GLM-5V 流式思考解析 (describe_image)。"""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_mcp.tools import vision  # noqa: E402

# 1x1 红色 PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class _FakeDelta:
    def __init__(self, reasoning=None, content=None):
        self.reasoning_content = reasoning
        self.content = content


class _FakeChunk:
    def __init__(self, delta=None):
        self.choices = [SimpleNamespace(delta=delta)] if delta is not None else []


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


def _make_fake_openai(chunks):
    class _FakeOpenAI:
        latest = None

        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = SimpleNamespace(completions=_FakeCompletions(chunks))
            type(self).latest = self

    return _FakeOpenAI


class TestLoadApiKey(unittest.TestCase):
    def test_env_var_wins(self):
        with patch.dict(os.environ, {"VISION_API_KEY": "from-env"}, clear=True):
            self.assertEqual(vision._load_api_key(), "from-env")

    def test_dotenv_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text('VISION_API_KEY=from-dotenv\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch(
                "qa_mcp.tools.vision.Path.cwd", return_value=Path(tmp)
            ), patch.object(vision, "PROJECT_DIR", tmp), patch.object(
                vision, "__file__", str(Path(tmp) / "vision.py")
            ):
                self.assertEqual(vision._load_api_key(), "from-dotenv")

    def test_dotenv_in_project_dir_wins_over_plugin_dir(self):
        """插件部署: VISION_API_KEY 配置在用户项目 .env, 进程 cwd 是插件目录。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            (Path(proj) / ".env").write_text(
                'VISION_API_KEY=from-project\n', encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "qa_mcp.tools.vision.Path.cwd", return_value=Path(plug)
            ), patch.object(vision, "PROJECT_DIR", proj), patch.object(
                vision, "__file__", str(Path(plug) / "vision.py")
            ):
                self.assertEqual(vision._load_api_key(), "from-project")

    def test_missing_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "qa_mcp.tools.vision.Path.cwd", return_value=Path(tempfile.gettempdir())
        ), patch.object(vision, "PROJECT_DIR", tempfile.gettempdir()), patch.object(
            vision, "__file__", str(Path(tempfile.gettempdir()) / "vision.py")
        ):
            self.assertEqual(vision._load_api_key(), "")


class TestResolveImageUrl(unittest.TestCase):
    def test_http_url_passthrough(self):
        self.assertEqual(
            vision._resolve_image_url("https://example.com/a.png"),
            {"url": "https://example.com/a.png"},
        )

    def test_local_file_becomes_data_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "shot.png"
            p.write_bytes(TINY_PNG)
            obj = vision._resolve_image_url(str(p))
            self.assertTrue(obj["url"].startswith("data:image/png;base64,"))
            self.assertEqual(
                base64.b64decode(obj["url"].split(",", 1)[1]), TINY_PNG
            )

    def test_relative_path_resolves_in_project_dir(self):
        """插件部署: 相对图片路径相对用户项目根 (PROJECT_DIR), 与进程 cwd 无关。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            (Path(proj) / "shot.png").write_bytes(TINY_PNG)
            with patch.object(vision, "PROJECT_DIR", proj), patch(
                "qa_mcp.tools.vision.Path.cwd", return_value=Path(plug)
            ):
                obj = vision._resolve_image_url("shot.png")
                self.assertTrue(obj["url"].startswith("data:image/png;base64,"))

    def test_relative_path_falls_back_to_cwd(self):
        """本地直跑: 项目根没有该文件时回退进程 cwd。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            (Path(plug) / "shot.png").write_bytes(TINY_PNG)
            with patch.object(vision, "PROJECT_DIR", proj), patch(
                "qa_mcp.tools.vision.Path.cwd", return_value=Path(plug)
            ):
                obj = vision._resolve_image_url("shot.png")
                self.assertTrue(obj["url"].startswith("data:image/png;base64,"))

    def test_missing_file_raises(self):
        with self.assertRaisesRegex(RuntimeError, "图片文件不存在"):
            vision._resolve_image_url("D:/no/such/file.png")

    def test_oversized_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "big.png"
            p.write_bytes(b"\x89PNG" + b"0" * (vision.MAX_IMAGE_BYTES + 1))
            with self.assertRaisesRegex(RuntimeError, "50MB"):
                vision._resolve_image_url(str(p))


class TestExtractLatestPastedImage(unittest.TestCase):
    def test_session_located_by_project_dir_not_cwd(self):
        """插件部署: 会话 jsonl 目录按用户项目路径 (PROJECT_DIR) 定位, 而非进程 cwd。"""
        with tempfile.TemporaryDirectory() as home_tmp, tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug, tempfile.TemporaryDirectory() as evid:
            home = Path(home_tmp)
            project = Path(proj) / "my_app"
            project.mkdir()
            parts = project.resolve().parts
            drive = parts[0][0]
            rest = "-".join(parts[1:])
            session_dir = home / ".claude" / "projects" / f"{drive.lower()}--{rest}"
            session_dir.mkdir(parents=True)
            rec = {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.b64encode(TINY_PNG).decode("ascii"),
                            },
                        }
                    ]
                },
            }
            # 与 Claude Code 会话 jsonl 一致的紧凑分隔符 (行内需含 '"type":"image"')
            (session_dir / "20260807.jsonl").write_text(
                json.dumps(rec, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            with patch.object(vision, "PROJECT_DIR", str(project)), patch(
                "qa_mcp.tools.vision.Path.home", return_value=home
            ), patch("qa_mcp.tools.vision.Path.cwd", return_value=Path(plug)), patch.object(
                vision, "EVIDENCE_DIR", evid
            ):
                out = vision._extract_latest_pasted_image()
            self.assertIsNotNone(out)
            self.assertEqual(out.read_bytes(), TINY_PNG)
            self.assertTrue(out.name.startswith("pasted_image_latest"))

    def test_no_session_for_cwd_returns_none(self):
        """插件部署且无注入项目: 按进程 cwd 找不到会话时返回 None 而非报错。"""
        with tempfile.TemporaryDirectory() as home_tmp, tempfile.TemporaryDirectory() as plug:
            home = Path(home_tmp)
            parts = Path(plug).resolve().parts
            drive = parts[0][0]
            rest = "-".join(parts[1:])
            session_dir = home / ".claude" / "projects" / f"{drive.lower()}--{rest}"
            session_dir.mkdir(parents=True)  # cwd 会话目录存在但无 jsonl
            with patch.object(vision, "PROJECT_DIR", plug), patch(
                "qa_mcp.tools.vision.Path.home", return_value=home
            ):
                self.assertIsNone(vision._extract_latest_pasted_image())


class TestDescribeImage(unittest.IsolatedAsyncioTestCase):
    def _make_png(self, tmp: str) -> str:
        p = Path(tmp) / "shot.png"
        p.write_bytes(TINY_PNG)
        return str(p)

    async def test_error_without_api_key(self):
        with patch("qa_mcp.tools.vision._load_api_key", return_value=""):
            result = await vision.describe_image_impl(images=["a.png"])
        self.assertEqual(result["status"], "error")
        self.assertIn("VISION_API_KEY", result["message"])

    async def test_error_without_images(self):
        with patch("qa_mcp.tools.vision._load_api_key", return_value="k"), patch(
            "qa_mcp.tools.vision._extract_latest_pasted_image", return_value=None
        ):
            result = await vision.describe_image_impl(images=[])
        self.assertEqual(result["status"], "error")
        self.assertIn("未指定图片", result["message"])

    async def test_streaming_success_splits_reasoning_and_content(self):
        """流式块解析: reasoning_content 归 reasoning, content 归 description;
        空 choices 块跳过; 请求参数与参考示例一致 (stream + thinking + reasoning_effort)。"""
        chunks = [
            _FakeChunk(),  # 无 choices 的块应跳过
            _FakeChunk(_FakeDelta(reasoning="第一步：识别图片", content=None)),
            _FakeChunk(_FakeDelta(reasoning="第二步：分析布局", content="图中有一个")),
            _FakeChunk(_FakeDelta(reasoning=None, content="红色按钮")),
        ]
        fake_cls = _make_fake_openai(chunks)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("qa_mcp.tools.vision._load_api_key", return_value="test-key"), patch(
                "qa_mcp.tools.vision.OpenAI", fake_cls
            ):
                result = await vision.describe_image_impl(
                    images=[self._make_png(tmp)], question="图中有什么？"
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["reasoning"], "第一步：识别图片第二步：分析布局")
        self.assertEqual(result["description"], "图中有一个红色按钮")
        self.assertTrue(result["thinking"])

        client = fake_cls.latest.chat.completions
        kwargs = client.last_kwargs
        self.assertEqual(kwargs["model"], "glm-5v-turbo")
        self.assertTrue(kwargs["stream"])
        self.assertEqual(kwargs["max_tokens"], 2048)
        self.assertEqual(
            kwargs["extra_body"],
            {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
        )
        user_content = kwargs["messages"][1]["content"]
        self.assertTrue(user_content[0]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(user_content[1]["text"], "图中有什么？")

    async def test_thinking_disabled_skips_reasoning_extra_body(self):
        chunks = [_FakeChunk(_FakeDelta(content="直接回答"))]
        fake_cls = _make_fake_openai(chunks)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("qa_mcp.tools.vision._load_api_key", return_value="test-key"), patch(
                "qa_mcp.tools.vision.OpenAI", fake_cls
            ):
                result = await vision.describe_image_impl(
                    images=[self._make_png(tmp)], thinking=False
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["reasoning"], "")
        self.assertEqual(result["description"], "直接回答")
        self.assertEqual(fake_cls.latest.chat.completions.last_kwargs["extra_body"], {})

    async def test_api_exception_returns_error_status(self):
        def _boom(*args, **kwargs):
            raise RuntimeError("network down")

        fake_cls = MagicMock(side_effect=_boom)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("qa_mcp.tools.vision._load_api_key", return_value="test-key"), patch(
                "qa_mcp.tools.vision.OpenAI", fake_cls
            ):
                result = await vision.describe_image_impl(images=[self._make_png(tmp)])

        self.assertEqual(result["status"], "error")
        self.assertIn("network down", result["message"])


if __name__ == "__main__":
    unittest.main()

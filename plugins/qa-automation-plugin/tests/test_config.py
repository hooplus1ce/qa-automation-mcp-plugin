"""config.py 单元测试: 用户项目根目录 (PROJECT_DIR) 解析与相对路径锚定。"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_mcp import config  # noqa: E402


class TestProjectDir(unittest.TestCase):
    def test_claude_project_dir_env_wins(self):
        """插件部署: CLAUDE_PROJECT_DIR (用户项目) 优先于进程 cwd (插件目录)。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as cwd:
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": proj}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(proj))

    def test_explicit_project_dir_highest_priority(self):
        """显式 PROJECT_DIR 环境变量优先于 CLAUDE_PROJECT_DIR 与嗅探。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as other:
            with patch.dict(
                os.environ, {"PROJECT_DIR": proj, "CLAUDE_PROJECT_DIR": other}, clear=True
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(proj))

    def test_explicit_project_dir_missing_ignored(self):
        """显式 PROJECT_DIR 指向不存在目录时忽略, 继续走 CLAUDE_PROJECT_DIR。"""
        with tempfile.TemporaryDirectory() as proj:
            with patch.dict(
                os.environ,
                {"PROJECT_DIR": "D:/no/such/dir", "CLAUDE_PROJECT_DIR": proj},
                clear=True,
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(proj))

    def test_falls_back_to_cwd(self):
        """本地直跑/无项目注入/嗅探失败: 回退进程 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ), patch.object(
                config, "_detect_project_dir_from_process_tree", return_value=None
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))

    def test_env_missing_dir_ignored(self):
        """CLAUDE_PROJECT_DIR 指向不存在的目录时忽略, 回退 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            with patch.dict(
                os.environ, {"CLAUDE_PROJECT_DIR": "D:/no/such/dir"}, clear=True
            ), patch("os.getcwd", return_value=cwd), patch.object(
                config, "_detect_project_dir_from_process_tree", return_value=None
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))


class _FakeProc:
    """psutil.Process 假链: cwd() 返回路径, parent() 返回下一节点或 None。"""

    def __init__(self, cwd, parent=None, cwd_error=None):
        self._cwd = cwd
        self._parent = parent
        self._cwd_error = cwd_error

    def cwd(self):
        if self._cwd_error:
            raise self._cwd_error
        return self._cwd

    def parent(self):
        return self._parent


class TestProcessTreeDetection(unittest.TestCase):
    def test_detects_client_project_skipping_plugin_chain(self):
        """嗅探: 跳过插件目录链 (fastmcp/uv 均在插件目录), 命中带项目标志的客户端目录。"""
        with tempfile.TemporaryDirectory() as proj:
            (Path(proj) / ".gitignore").write_text("", encoding="utf-8")
            root = str(config._plugin_root())
            chain = _FakeProc(root, _FakeProc(proj, None))
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=root
            ), patch("psutil.Process", return_value=chain):
                self.assertEqual(
                    config._resolve_project_dir(), str(Path(proj).resolve())
                )

    def test_skips_plugin_ancestor_chain(self):
        """插件装在 ~/.claude 下: 跳过插件目录的祖先链 (如仓库根/home), 命中项目目录。"""
        with tempfile.TemporaryDirectory() as proj:
            (Path(proj) / ".git").mkdir()
            root = str(config._plugin_root())
            ancestor = str(Path(root).parent)  # 真实祖先 (仓库根): root.is_relative_to(ancestor)
            chain = _FakeProc(root, _FakeProc(ancestor, _FakeProc(proj, None)))
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=root
            ), patch("psutil.Process", return_value=chain):
                self.assertEqual(
                    config._resolve_project_dir(), str(Path(proj).resolve())
                )

    def test_system_dir_without_markers_not_matched(self):
        """回归: 无关但无项目标志的系统目录 (如 System32) 不命中, 继续上溯/回退。"""
        with tempfile.TemporaryDirectory() as cwd:
            chain = _FakeProc(str(Path(cwd)), None)  # 无关目录, 无标志文件
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ), patch("psutil.Process", return_value=chain):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))

    def test_cwd_permission_error_falls_back_to_cwd(self):
        """嗅探遇权限错误 (跨用户进程) 静默回退 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            chain = _FakeProc(None, None, cwd_error=PermissionError("denied"))
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ), patch("psutil.Process", return_value=chain):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))

    def test_no_psutil_falls_back_to_cwd(self):
        """psutil 缺失时嗅探跳过, 回退 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ), patch.dict("sys.modules", {"psutil": None}):
                self.assertIsNone(config._detect_project_dir_from_process_tree())


class TestProjectPath(unittest.TestCase):
    def test_relative_anchored_to_project_dir(self):
        with tempfile.TemporaryDirectory() as proj:
            with patch.object(config, "PROJECT_DIR", proj):
                self.assertEqual(
                    config.project_path("evidence_assets"),
                    os.path.join(proj, "evidence_assets"),
                )

    def test_absolute_and_empty_passthrough(self):
        with tempfile.TemporaryDirectory() as proj:
            with patch.object(config, "PROJECT_DIR", proj):
                self.assertEqual(config.project_path(proj), proj)
                self.assertEqual(config.project_path(""), "")

    def test_output_dirs_are_absolute(self):
        """EVIDENCE_DIR/OUTPUT_DIR/DOWNLOAD_DIR 必须锚定为绝对路径。"""
        self.assertTrue(os.path.isabs(config.EVIDENCE_DIR))
        self.assertTrue(os.path.isabs(config.OUTPUT_DIR))
        self.assertTrue(os.path.isabs(config.DOWNLOAD_DIR))


class TestEnvLoading(unittest.TestCase):
    """用户项目 .env → 插件进程环境变量注入 (端到端子进程验证)。"""

    def _run_config_in_subprocess(self, cwd: str, extra_env: dict) -> str:
        code = (
            "import os, sys; "
            f"sys.path.insert(0, {str(PROJECT_ROOT / 'src')!r}); "
            "from qa_mcp import config; "
            "print(os.environ.get('TEST_PROJECT_KEY', ''), "
            "os.environ.get('VISION_PROVIDER', ''), config.PROJECT_DIR)"
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROJECT_DIR", "CLAUDE_PROJECT_DIR", "VISION_PROVIDER", "GEMINI_API_KEY")
        }
        env.update(extra_env)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_project_dotenv_injected_and_wins_over_plugin_dir(self):
        """项目根 .env 注入插件进程, 且优先于插件目录 .env (override=False)。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            (Path(proj) / ".env").write_text(
                "TEST_PROJECT_KEY=from-project\nVISION_PROVIDER=antigravity\n",
                encoding="utf-8",
            )
            (Path(plug) / ".env").write_text(
                "TEST_PROJECT_KEY=from-plugin\n", encoding="utf-8"
            )
            out = self._run_config_in_subprocess(
                cwd=plug, extra_env={"PROJECT_DIR": proj}
            )
        parts = out.split()
        self.assertEqual(parts[0], "from-project")  # 项目 .env 优先
        self.assertEqual(parts[1], "antigravity")
        self.assertEqual(parts[2], os.path.abspath(proj))

    def test_no_project_dotenv_falls_back_to_cwd(self):
        """项目根无 .env 时回退加载进程 cwd (插件目录) 的 .env。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            (Path(plug) / ".env").write_text(
                "TEST_PROJECT_KEY=from-plugin\n", encoding="utf-8"
            )
            out = self._run_config_in_subprocess(
                cwd=plug, extra_env={"PROJECT_DIR": proj}
            )
        parts = out.split()
        self.assertEqual(parts[0], "from-plugin")

    def test_user_level_dotenv_loaded(self):
        """用户级 ~/.qa-automation-plugin/.env 被加载 (Desktop 等无项目注入客户端)。"""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as plug:
            user_env = Path(home) / ".qa-automation-plugin"
            user_env.mkdir(parents=True)
            (user_env / ".env").write_text(
                "TEST_PROJECT_KEY=from-user-level\n", encoding="utf-8"
            )
            out = self._run_config_in_subprocess(
                cwd=plug,
                extra_env={"PROJECT_DIR": proj, "USERPROFILE": home},
            )
        parts = out.split()
        self.assertEqual(parts[0], "from-user-level")


if __name__ == "__main__":
    unittest.main()

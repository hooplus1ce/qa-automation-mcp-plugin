"""config.py 单元测试: 用户项目根目录 (PROJECT_DIR) 解析与相对路径锚定。"""

import os
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

    def test_falls_back_to_cwd(self):
        """本地直跑/无项目注入: 回退进程 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            with patch.dict(os.environ, {}, clear=True), patch(
                "os.getcwd", return_value=cwd
            ):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))

    def test_env_missing_dir_ignored(self):
        """CLAUDE_PROJECT_DIR 指向不存在的目录时忽略, 回退 cwd。"""
        with tempfile.TemporaryDirectory() as cwd:
            with patch.dict(
                os.environ, {"CLAUDE_PROJECT_DIR": "D:/no/such/dir"}, clear=True
            ), patch("os.getcwd", return_value=cwd):
                self.assertEqual(config._resolve_project_dir(), os.path.abspath(cwd))


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


if __name__ == "__main__":
    unittest.main()

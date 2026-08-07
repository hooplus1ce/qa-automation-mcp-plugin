import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_mcp.tools import browser as browser_tools  # noqa: E402
from qa_mcp.tools.browser import (  # noqa: E402
    _resolve_download_dir,
    _resolve_upload_paths,
    download_file_impl,
    upload_file_impl,
)


# ==================== Fakes ====================

class FakeCDP:
    """模拟浏览器级 CDP 会话: 记录 send, 支持手动 fire 事件。"""

    def __init__(self):
        self.sent = []
        self.listeners = {}
        self.detached = False

    def on(self, event, callback):
        self.listeners[event] = callback

    async def send(self, method, params=None):
        self.sent.append((method, params or {}))
        return {}

    async def detach(self):
        self.detached = True

    def fire(self, event, payload):
        self.listeners[event](payload)

    @property
    def set_download_calls(self):
        return [p for m, p in self.sent if m == "Browser.setDownloadBehavior"]


class FakeBrowser:
    def __init__(self, cdp):
        self._cdp = cdp

    async def new_browser_cdp_session(self):
        return self._cdp


class FakeContext:
    def __init__(self, browser):
        self.browser = browser


class FakePage:
    def __init__(self, cdp):
        self.context = FakeContext(FakeBrowser(cdp))


class FakeFileChooser:
    def __init__(self, multiple=True):
        self._multiple = multiple
        self.set_files = mock.AsyncMock()

    def is_multiple(self):
        return self._multiple


class FakeExpectFileChooser:
    """模拟 page.expect_file_chooser() 异步上下文管理器 (value 为 awaitable)。"""

    def __init__(self, chooser):
        self._chooser = chooser

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def value(self):
        async def _get():
            return self._chooser

        return _get()


class FakeLocator:
    def __init__(self, is_file_input=True):
        self.is_file_input = is_file_input
        self.wait_for = mock.AsyncMock()
        self.scroll_into_view_if_needed = mock.AsyncMock()
        self.set_input_files = mock.AsyncMock()
        self.click = mock.AsyncMock()
        self.evaluate = mock.AsyncMock(return_value=is_file_input)


class FakeTarget:
    def __init__(self, locator):
        self._lc = locator

    def get_by_role(self, role, name=None):
        return self._lc

    def locator(self, selector):
        return self._lc


# ==================== download_file ====================

class DownloadDirTests(unittest.TestCase):
    def test_default_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = asyncio.run(_resolve_download_dir(os.path.join(tmp, "dl")))
            self.assertTrue(os.path.isdir(path))
            self.assertTrue(path.endswith(os.path.join("dl")))

    def test_explicit_dir_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = asyncio.run(_resolve_download_dir(tmp))
            self.assertEqual(os.path.abspath(tmp), path)

    def test_relative_dir_anchored_to_project(self):
        """插件部署: 相对下载目录基于用户项目根 (PROJECT_DIR), 而非进程 cwd。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as cwd:
            old = os.getcwd()
            os.chdir(cwd)
            try:
                with mock.patch.object(browser_tools, "PROJECT_DIR", proj):
                    path = asyncio.run(_resolve_download_dir("dl"))
                self.assertEqual(os.path.abspath(path), os.path.join(proj, "dl"))
            finally:
                os.chdir(old)


class DownloadFileTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, download_dir, side_effect=None, wait_timeout_ms=30000, **kwargs):
        cdp = FakeCDP()
        page = FakePage(cdp)

        with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
            with mock.patch.object(
                browser_tools, "_do_click",
                new=mock.AsyncMock(side_effect=side_effect or (lambda **kw: {"status": "success"})),
            ):
                return await download_file_impl(
                    by="css", selector="#dl", download_dir=download_dir,
                    wait_timeout_ms=wait_timeout_ms, **kwargs,
                ), cdp

    def _fire_download(self, cdp, guid="g1", suggested="report.xlsx", final_state="completed"):
        cdp.fire("Browser.downloadWillBegin", {
            "guid": guid, "suggestedFilename": suggested, "url": "blob:http://x/1",
        })
        cdp.fire("Browser.downloadProgress", {"guid": guid, "state": final_state})

    async def test_success_saves_file_and_restores_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdp_holder = {}

            def side_effect(page, by, selector, iframe_selector, **kwargs):
                cdp_holder["cdp"].fire("Browser.downloadWillBegin", {
                    "guid": "g1", "suggestedFilename": "report.xlsx", "url": "blob:http://x/1",
                })
                with open(os.path.join(tmp, "report.xlsx"), "wb") as f:
                    f.write(b"x")
                cdp_holder["cdp"].fire("Browser.downloadProgress", {"guid": "g1", "state": "completed"})
                return {"status": "success"}

            cdp = FakeCDP()
            cdp_holder["cdp"] = cdp
            page = FakePage(cdp)
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_do_click", new=mock.AsyncMock(side_effect=side_effect)):
                    result = await download_file_impl(
                        by="css", selector="#dl", download_dir=tmp, wait_timeout_ms=3000,
                    )
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["files"]), 1)
            self.assertEqual(result["files"][0]["filename"], "report.xlsx")
            self.assertEqual(result["files"][0]["size_bytes"], 1)
            self.assertEqual(result["downloads"][0]["state"], "completed")
            self.assertEqual(result["downloads"][0]["suggested_filename"], "report.xlsx")
            # 下载行为恢复默认
            calls = cdp.set_download_calls
            self.assertEqual(calls[0]["behavior"], "allow")
            self.assertEqual(calls[0]["downloadPath"], tmp)
            self.assertTrue(calls[-1]["behavior"] == "default")
            self.assertTrue(cdp.detached)

    async def test_filename_override_renames_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdp = FakeCDP()

            def side_effect(page, by, selector, iframe_selector, **kwargs):
                with open(os.path.join(tmp, "report (1).xlsx"), "wb") as f:
                    f.write(b"y" * 10)
                cdp.fire("Browser.downloadWillBegin", {
                    "guid": "g1", "suggestedFilename": "report.xlsx", "url": "blob:http://x/1",
                })
                cdp.fire("Browser.downloadProgress", {"guid": "g1", "state": "completed"})
                return {"status": "success"}

            page = FakePage(cdp)
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_do_click", new=mock.AsyncMock(side_effect=side_effect)):
                    result = await download_file_impl(
                        by="css", selector="#dl", download_dir=tmp,
                        filename="final.xlsx", wait_timeout_ms=3000,
                    )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["files"][0]["filename"], "final.xlsx")
            self.assertTrue(os.path.isfile(os.path.join(tmp, "final.xlsx")))

    async def test_no_download_when_no_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdp = FakeCDP()
            page = FakePage(cdp)
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_do_click", new=mock.AsyncMock(return_value={"status": "success"})):
                    result = await download_file_impl(
                        by="css", selector="#dl", download_dir=tmp, wait_timeout_ms=3000,
                    )
            self.assertEqual(result["status"], "no_download")
            self.assertEqual(result["files"], [])
            self.assertTrue(cdp.set_download_calls[-1]["behavior"] == "default")

    async def test_timeout_when_download_stuck(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdp = FakeCDP()

            def side_effect(page, by, selector, iframe_selector, **kwargs):
                cdp.fire("Browser.downloadWillBegin", {
                    "guid": "g1", "suggestedFilename": "slow.bin", "url": "blob:http://x/1",
                })
                cdp.fire("Browser.downloadProgress", {"guid": "g1", "state": "inProgress"})
                return {"status": "success"}
                # 永不 completed

            page = FakePage(cdp)
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_do_click", new=mock.AsyncMock(side_effect=side_effect)):
                    result = await download_file_impl(
                        by="css", selector="#dl", download_dir=tmp, wait_timeout_ms=1000,
                    )
            self.assertEqual(result["status"], "timeout")
            self.assertEqual(result["downloads"][0]["state"], "inProgress")

    async def test_canceled_when_download_canceled(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdp = FakeCDP()

            def side_effect(page, by, selector, iframe_selector, **kwargs):
                cdp.fire("Browser.downloadWillBegin", {
                    "guid": "g1", "suggestedFilename": "c.bin", "url": "blob:http://x/1",
                })
                cdp.fire("Browser.downloadProgress", {"guid": "g1", "state": "canceled"})
                return {"status": "success"}

            page = FakePage(cdp)
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_do_click", new=mock.AsyncMock(side_effect=side_effect)):
                    result = await download_file_impl(
                        by="css", selector="#dl", download_dir=tmp, wait_timeout_ms=3000,
                    )
            self.assertEqual(result["status"], "canceled")

    async def test_param_validation(self):
        with self.assertRaises(RuntimeError):
            await download_file_impl(by="coordinate")
        with self.assertRaises(RuntimeError):
            await download_file_impl(by="css", selector=None)
        with self.assertRaises(RuntimeError):
            await download_file_impl(by="role", role=None)


# ==================== upload_file ====================

class ResolveUploadPathsTests(unittest.TestCase):
    def test_missing_files_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "不存在"):
                _resolve_upload_paths([os.path.join(tmp, "nope.xlsx")])

    def test_empty_raises(self):
        with self.assertRaisesRegex(RuntimeError, "不能为空"):
            _resolve_upload_paths([])

    def test_relative_resolved_to_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                with open("a.txt", "w") as f:
                    f.write("x")
                resolved = _resolve_upload_paths(["a.txt"])
                self.assertEqual(resolved, [os.path.join(tmp, "a.txt")])
            finally:
                os.chdir(old)

    def test_relative_resolved_in_project_dir_first(self):
        """插件部署: 上传相对路径优先基于用户项目根 (PROJECT_DIR) 解析。"""
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as cwd:
            with open(os.path.join(proj, "a.txt"), "w") as f:
                f.write("x")
            old = os.getcwd()
            os.chdir(cwd)
            try:
                with mock.patch.object(browser_tools, "PROJECT_DIR", proj):
                    resolved = _resolve_upload_paths(["a.txt"])
                self.assertEqual(resolved, [os.path.join(proj, "a.txt")])
            finally:
                os.chdir(old)


class UploadFileTests(unittest.IsolatedAsyncioTestCase):
    async def _make_file(self, tmp, name="a.xlsx"):
        path = os.path.join(tmp, name)
        with open(path, "wb") as f:
            f.write(b"x")
        return path

    async def test_input_file_direct_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = await self._make_file(tmp)
            locator = FakeLocator(is_file_input=True)
            target = FakeTarget(locator)
            cdp = FakeCDP()
            page = FakePage(cdp)

            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_resolve_frame_target", new=mock.AsyncMock(return_value=(target, []))):
                    result = await upload_file_impl(
                        file_paths=[path], by="css", selector="#file",
                    )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["mode"], "set_input_files")
            locator.set_input_files.assert_awaited_once_with([path])
            locator.click.assert_not_awaited()

    async def test_button_uses_filechooser(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = await self._make_file(tmp)
            chooser = FakeFileChooser(multiple=True)
            locator = FakeLocator(is_file_input=False)
            locator.click = mock.AsyncMock()
            target = FakeTarget(locator)
            page = FakePage(FakeCDP())
            page.expect_file_chooser = mock.Mock(return_value=FakeExpectFileChooser(chooser))

            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_resolve_frame_target", new=mock.AsyncMock(return_value=(target, []))):
                    result = await upload_file_impl(
                        file_paths=[path], by="css", selector="#upload-btn",
                    )
            self.assertEqual(result["mode"], "filechooser")
            self.assertTrue(result["is_multiple"])
            locator.click.assert_awaited_once()
            chooser.set_files.assert_awaited_once_with([path])

    async def test_success_text_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = await self._make_file(tmp)
            locator = FakeLocator(is_file_input=True)
            target = FakeTarget(locator)
            page = FakePage(FakeCDP())

            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock(return_value=page)):
                with mock.patch.object(browser_tools, "_resolve_frame_target", new=mock.AsyncMock(return_value=(target, []))):
                    with mock.patch.object(
                        browser_tools, "wait_for_condition_impl",
                        new=mock.AsyncMock(return_value={"status": "success", "state": {"frame": "x", "match": True}, "elapsed_ms": 100}),
                    ):
                        result = await upload_file_impl(
                            file_paths=[path], by="css", selector="#file",
                            success_text="上传成功", wait_timeout_ms=5000,
                        )
                        self.assertTrue(result["success_text_found"])
                        self.assertEqual(result["success_check"]["status"], "success")
                        browser_tools.wait_for_condition_impl.assert_awaited_once()
            self.assertTrue(result["success_text_found"])

    async def test_missing_file_raises_before_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(browser_tools.browser_mgr, "get_page", new=mock.AsyncMock()) as gp:
                with self.assertRaises(RuntimeError):
                    await upload_file_impl(
                        file_paths=[os.path.join(tmp, "ghost.txt")], by="css", selector="#file",
                    )
                gp.assert_not_awaited()

    async def test_param_validation(self):
        with self.assertRaises(RuntimeError):
            await upload_file_impl(file_paths=["x"], by="coordinate")


if __name__ == "__main__":
    unittest.main()

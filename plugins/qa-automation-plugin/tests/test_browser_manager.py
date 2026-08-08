import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_mcp.tools.browser import BrowserManager  # noqa: E402


class FakeTab:
    def __init__(self, url, visible=True, closed=False):
        self.url = url
        self._visible = visible
        self._closed = closed

    def is_closed(self):
        return self._closed

    async def evaluate(self, expression):
        return self._visible  # 真实浏览器返回布尔 (visibilityState === 'visible')

    def close(self):
        self._closed = True

    def __repr__(self):
        return f"<FakeTab {self.url}>"


class FakeContext:
    def __init__(self, pages):
        self.pages = pages


def make_manager(pages):
    mgr = BrowserManager("http://fake-cdp:9222")
    mgr._context = FakeContext(pages)
    return mgr


class PageSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_picks_visible_hoolinks_first(self):
        hidden = FakeTab("https://demo18-scm.hoolinks.com/old", visible=False)
        visible = FakeTab("https://demo18-scm.hoolinks.com/static/admin")
        mgr = make_manager([hidden, visible])
        self.assertIs(await mgr._select_page(), visible)

    async def test_falls_back_to_any_hoolinks_when_none_visible(self):
        hidden1 = FakeTab("https://demo18-scm.hoolinks.com/a", visible=False)
        hidden2 = FakeTab("https://demo18-scm.hoolinks.com/b", visible=False)
        mgr = make_manager([hidden1, hidden2])
        self.assertIs(await mgr._select_page(), hidden1)

    async def test_non_hoolinks_falls_back_to_non_system_page(self):
        user_page = FakeTab("https://www.google.com/")
        chrome_page = FakeTab("chrome://newtab/")
        mgr = make_manager([chrome_page, user_page])
        self.assertIs(await mgr._select_page(), user_page)

    async def test_all_system_pages_falls_back_to_first(self):
        a = FakeTab("chrome://newtab/")
        b = FakeTab("about:blank")
        mgr = make_manager([a, b])
        self.assertIs(await mgr._select_page(), a)

    async def test_locked_page_is_reused_after_new_tab_opens(self):
        """锁定页保持: 用户新开 hoolinks 标签页后, 操作仍作用于原测试页。"""
        test_page = FakeTab("https://demo18-scm.hoolinks.com/static/admin")
        mgr = make_manager([test_page])
        first = await mgr._select_page()
        self.assertIs(first, test_page)

        # 用户新开一个 hoolinks 标签页 (模拟日常活动)
        user_page = FakeTab("https://www.hoolinks.com/somewhere", visible=True)
        mgr._context.pages.append(user_page)
        self.assertIs(await mgr._select_page(), test_page)

    async def test_re_selects_when_locked_page_closed(self):
        """锁定页被关闭 → 重新选择, 不误选用户活动页 (优先可见 hoolinks/非系统页)。"""
        test_page = FakeTab("https://demo18-scm.hoolinks.com/static/admin")
        mgr = make_manager([test_page])
        self.assertIs(await mgr._select_page(), test_page)

        test_page.close()
        user_page = FakeTab("https://www.google.com/", visible=True)
        mgr._context.pages.append(user_page)
        self.assertIs(await mgr._select_page(), user_page)

    async def test_switch_target_binds_by_url_substring(self):
        test_page = FakeTab("https://demo18-scm.hoolinks.com/static/admin")
        other_page = FakeTab("https://docs.qq.com/doc/xyz")
        mgr = make_manager([test_page, other_page])
        self.assertIs(await mgr._select_page(), test_page)

        bound = await mgr.switch_target("docs.qq.com")
        self.assertIs(bound, other_page)
        self.assertIs(await mgr._select_page(), other_page)

    async def test_switch_target_without_match_raises(self):
        mgr = make_manager([FakeTab("https://demo18-scm.hoolinks.com/static/admin")])
        with self.assertRaises(RuntimeError):
            await mgr.switch_target("does-not-exist.example")


if __name__ == "__main__":
    unittest.main()

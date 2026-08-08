import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_mcp.utils.dynamic_layers import scan_dynamic_layers  # noqa: E402


class FakeClock:
    """可注入的假时钟: advance 由 FakePage.wait_for_timeout 驱动。"""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class FakeFrame:
    def __init__(self, path, url, layers, responses=None):
        self.path = path
        self.url = url
        self.layers = layers
        # responses: 每次 evaluate 依次返回的 snapshot 列表 (末项复用);
        # None 时恒返回 {"layers": self.layers}
        self.responses = responses
        self.call_count = 0

    async def evaluate(self, script, *args):
        self.call_count += 1
        if self.responses is not None:
            idx = min(self.call_count - 1, len(self.responses) - 1)
            return self.responses[idx]
        return {"layers": self.layers}


class FakePage:
    def __init__(self, frames, clock=None):
        self.frames = frames
        self.clock = clock or FakeClock()

    async def wait_for_timeout(self, timeout):
        self.clock.advance(timeout / 1000)
        return None


async def fake_frame_path(frame):
    return frame.path


class DynamicLayerTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_scans_only_requested_iframe_and_keeps_frame_path(self):
        target_layer = {
            "kind": "message",
            "selector": ".message-content",
            "text": "保存成功",
        }
        page = FakePage([
            FakeFrame([], "https://demo18-scm.hoolinks.com/static/admin/", []),
            FakeFrame(["#target"], "https://demo18-scm.hoolinks.com/app", [target_layer]),
            FakeFrame(["#other"], "https://demo18-scm.hoolinks.com/other", [target_layer]),
        ])

        result = await scan_dynamic_layers(
            page,
            fake_frame_path,
            iframe_selector="#target",
            wait_ms=0,
        )

        self.assertEqual(result["frames_scanned"], 1)
        self.assertEqual(result["layer_count"], 1)
        self.assertEqual(result["layers"][0]["frame_path"], ["#target"])
        self.assertEqual(result["layers"][0]["frame_url"], "https://demo18-scm.hoolinks.com/app")
        self.assertEqual(result["detail"], "brief")

    async def test_rejects_invalid_detail(self):
        page = FakePage([FakeFrame([], "https://x/", [])])
        with self.assertRaises(ValueError):
            await scan_dynamic_layers(page, fake_frame_path, wait_ms=0, detail="invalid")

    async def test_early_return_after_new_layer_stabilizes(self):
        """新层出现并稳定 250ms 后提前返回, 不轮询满 wait_ms。
        满轮次 = 1500/100 = 15 轮; 提前返回应 ≤ 5 轮 (第 1 轮空, 第 2 轮出现, 稳定 0.3s 后第 5 轮停)。"""
        msg = {"kind": "message", "selector": ".ant-message", "text": "操作成功"}
        clock = FakeClock()
        frame = FakeFrame(
            ["#target"],
            "https://demo18-scm.hoolinks.com/app",
            [],
            responses=[
                {"layers": []},
                {"layers": [msg]},
                {"layers": [msg]},
                {"layers": [msg]},
                {"layers": [msg]},
                {"layers": [msg]},
            ],
        )
        page = FakePage([frame], clock=clock)

        result = await scan_dynamic_layers(
            page,
            fake_frame_path,
            iframe_selector="#target",
            wait_ms=1500,
            poll_interval_ms=100,
            clock=clock,
        )

        self.assertLessEqual(frame.call_count, 5)
        self.assertEqual(result["layer_count"], 1)
        self.assertLess(result["observation_ms"], 1500)

    async def test_wait_full_window_when_no_new_layer(self):
        """无新层时仍等满 wait_ms (消息可能在途中)。"""
        clock = FakeClock()
        frame = FakeFrame([], "https://demo18-scm.hoolinks.com/static/admin/", [])
        page = FakePage([frame], clock=clock)

        result = await scan_dynamic_layers(
            page,
            fake_frame_path,
            wait_ms=300,
            poll_interval_ms=100,
            clock=clock,
        )

        self.assertEqual(result["layer_count"], 0)
        self.assertGreaterEqual(result["observation_ms"], 300)
        # 满轮次: 300/100 = 3 轮 + 收尾检查
        self.assertGreaterEqual(frame.call_count, 3)


if __name__ == "__main__":
    unittest.main()

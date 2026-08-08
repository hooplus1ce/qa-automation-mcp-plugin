"""Playwright (Python) adaptation of the cursor + target-highlight visuals.

The rendering capability itself lives in the frozen JS artifact
``visuals_js.INSTALL_SCRIPT`` — do not edit it. This module only provides the
Playwright plumbing: inject, drive, clean up.

Pick the class matching your server's Playwright flavour:
- ``PlaywrightVisualEffects``       for ``playwright.sync_api``
- ``AsyncPlaywrightVisualEffects``  for ``playwright.async_api``
  (FastMCP / asyncio servers)

Key Playwright facts this relies on:
- ``page.evaluate`` awaits promises and returns the resolved value, so the
  ``show()`` promise (cursor move animation) resolves before the click runs.
- Payloads are JSON-embedded into the expression string, which sidesteps
  Playwright Python's function-vs-expression string heuristic entirely.
- ``page.add_init_script`` is the equivalent of CDP
  ``Page.addScriptToEvaluateOnNewDocument``: it keeps visuals alive across
  navigation, but only for documents created *after* registration — so the
  script is always evaluated once on the current document too.
"""

from __future__ import annotations

import json
from threading import RLock
from typing import Any

from playwright.async_api import Page as AsyncPage

try:
    from .visuals_js import INSTALL_SCRIPT
except ImportError:  # package dropped in as loose files
    from visuals_js import INSTALL_SCRIPT

VISUAL_KEY = "__drissionpageMcpVisuals"
MIN_MOVE_DURATION_MS = 280
MAX_MOVE_DURATION_MS = 640


def _invoke(expression: str) -> str:
    """Run JS as an expression and return its value."""
    return f"(() => {expression})()"


def _payload(
    rect: tuple[float, float, float, float],
    point: tuple[float, float],
    label: str,
    action: str,
) -> dict[str, Any]:
    return {
        "rect": [round(v, 2) for v in rect],
        "point": [round(v, 2) for v in point],
        "label": label[:80],
        "action": action,
        "minDurationMs": MIN_MOVE_DURATION_MS,
        "maxDurationMs": MAX_MOVE_DURATION_MS,
    }


def _show_expr(payload: dict[str, Any]) -> str:
    return _invoke(f"globalThis[{json.dumps(VISUAL_KEY)}].show({json.dumps(payload)})")


def _finish_expr(success: bool) -> str:
    return _invoke(f"globalThis[{json.dumps(VISUAL_KEY)}].finish({json.dumps(success)})")


def _disable_expr() -> str:
    return _invoke(f"globalThis[{json.dumps(VISUAL_KEY)}]?.disable()")


def _snapshot_expr() -> str:
    return _invoke(f"globalThis[{json.dumps(VISUAL_KEY)}]?.snapshot() ?? null")


def _result(
    snapshot: dict[str, Any] | None,
    payload: dict[str, Any],
    persistent: bool,
) -> dict[str, Any]:
    rendering = snapshot.get("rendering", {}) if snapshot else {}
    return {
        "enabled": True,
        "mode": "cursor_highlight",
        "persistent_across_navigation": persistent,
        "rect": payload["rect"],
        "point": payload["point"],
        "label": payload["label"],
        "action": payload["action"],
        "move_duration_ms": rendering.get("requested_duration_ms"),
        "snapshot": snapshot,
    }


class AsyncPlaywrightVisualEffects:
    """Cursor + highlight overlay for one Playwright async ``Page``.

    Used by this FastMCP / asyncio service; the sync counterpart was removed.
    """

    def __init__(self) -> None:
        self._registered_pages: set[int] = set()
        self._lock = RLock()

    async def show(
        self,
        page: AsyncPage,
        *,
        rect: tuple[float, float, float, float],
        point: tuple[float, float],
        label: str,
        action: str,
    ) -> dict[str, Any]:
        with self._lock:
            persistent = await self._ensure(page)
            payload = _payload(rect, point, label, action)
            snapshot = await page.evaluate(_show_expr(payload))
            if not isinstance(snapshot, dict):
                snapshot = await self.snapshot(page)
            return _result(snapshot, payload, persistent)

    async def finish(self, page: AsyncPage, success: bool) -> None:
        await page.evaluate(_finish_expr(success))

    async def disable(self, page: AsyncPage) -> None:
        await page.evaluate(_disable_expr())

    async def snapshot(self, page: AsyncPage) -> dict[str, Any] | None:
        result = await page.evaluate(_snapshot_expr())
        return result if isinstance(result, dict) else None

    async def _ensure(self, page: AsyncPage) -> bool:
        key = id(page)
        persistent = key in self._registered_pages
        if not persistent:
            try:
                await page.add_init_script(INSTALL_SCRIPT)
                self._registered_pages.add(key)
                persistent = True
            except Exception:
                persistent = False
        await page.evaluate(INSTALL_SCRIPT)
        return persistent

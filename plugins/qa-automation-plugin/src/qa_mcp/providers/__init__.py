"""领域工具 Provider 装配层 (FastMCP 3.x/4.0 官方 Provider 架构)。"""

from qa_mcp.providers.browser import BrowserAutomationProvider
from qa_mcp.providers.vtable import VTableAutomationProvider

__all__ = [
    "BrowserAutomationProvider",
    "VTableAutomationProvider",
]

"""必应搜索 MCP 服务封装

通过魔搭社区接入必应搜索 MCP，提供中文搜索能力。
使用 langchain-mcp-adapters 官方适配器，SSE 传输方式。
"""

import threading
from typing import Optional, Dict, Any, List

from langchain_core.tools import BaseTool

from ..config import get_settings
from .base_mcp_service import BaseMCPService


class BingMCPConfigError(Exception):
    """必应 MCP 配置错误"""
    pass


class BingMCPService(BaseMCPService):
    """必应 MCP 服务封装类"""

    _service_name = "必应"

    def _build_mcp_config(self) -> Dict[str, Any]:
        settings = get_settings()
        if not settings.bing_mcp_url:
            raise BingMCPConfigError("BING_MCP_URL 未配置")
        return {
            "bing": {
                "transport": "sse",
                "url": settings.bing_mcp_url,
                "timeout": 60,
                "sse_read_timeout": 300,
            }
        }

    # ---- 必应业务方法 ----

    async def search(self, query: str, count: int = 5, offset: int = 0) -> Any:
        """必应搜索"""
        result = await self._call_tool(
            "bing_search",
            {"query": query, "count": count, "offset": offset},
            timeout=30.0,
        )
        return result

    async def crawl_webpage(self, url: str) -> Any:
        """抓取网页内容"""
        result = await self._call_tool(
            "crawl_webpage",
            {"url": url},
            timeout=30.0,
        )
        return result


# ---- 单例 ----

_bing_service: Optional[BingMCPService] = None
_service_lock = threading.Lock()


def get_bing_service() -> Optional[BingMCPService]:
    """获取必应 MCP 服务实例

    如果 BING_MCP_URL 未配置，返回 None，调用方应降级到 DuckDuckGo。
    """
    global _bing_service
    if _bing_service is None:
        with _service_lock:
            if _bing_service is None:
                try:
                    _bing_service = BingMCPService()
                    _bing_service._build_mcp_config()  # 验证配置
                except BingMCPConfigError as e:
                    print(f"⚠️ 必应 MCP 未配置: {e}")
                    return None
    return _bing_service

"""LangChain 兼容的高德地图服务封装

本模块是 LangGraph 重构后的新 MCP 调用层，独立于旧的 amap_service.py。
使用 langchain-mcp-adapters 官方适配器替代 hello_agents.MCPTool，
通过 SSE 传输连接高德官方 MCP 云服务（无需本地安装 uvx/Node.js），
提供 LangChainAmapService 异步服务类，统一封装所有高德地图 MCP 工具调用。

韧性增强:
- SSE 断线自动重连机制
- 单次工具调用超时控制
- 连接异常自动重置客户端
- 健康检查接口
"""

import asyncio
import threading
from typing import Optional, Dict, Any, List

from langchain_core.tools import BaseTool

from ..config import get_settings
from .base_mcp_service import BaseMCPService


class LangChainAmapService(BaseMCPService):
    """LangChain 兼容的高德地图服务封装类

    使用 langchain-mcp-adapters 官方适配器，提供统一的异步服务接口。
    MCP 工具自动从服务器加载，无需手动定义 @tool 函数。

    韧性增强:
    - _call_tool 内置超时控制和断线重连
    - health_check 方法用于探测连接状态
    """

    _service_name = "高德地图"

    def _build_mcp_config(self) -> Dict[str, Any]:
        settings = get_settings()
        if not settings.amap_api_key:
            raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")
        return {
            "amap": {
                "transport": "sse",
                "url": f"https://mcp.amap.com/sse?key={settings.amap_api_key}",
                "timeout": 60,
                "sse_read_timeout": 300,
            }
        }

    # ---- 高德地图业务方法 ----

    async def search_poi(self, keywords: str, city: str) -> Any:
        result = await self._call_tool("maps_text_search", {
            "keywords": keywords,
            "city": city,
            "citylimit": "true"
        })
        return self._parse_result(result)

    async def get_weather(self, city: str) -> Any:
        result = await self._call_tool("maps_weather", {"city": city})
        return self._parse_result(result)

    async def _geocode_address(self, address: str, city: Optional[str] = None) -> Optional[str]:
        arguments = {"address": address}
        if city:
            arguments["city"] = city
        result = await self._call_tool("maps_geo", arguments)
        parsed = self._parse_result(result)
        if isinstance(parsed, dict):
            geocodes = parsed.get("geocodes", [])
            if geocodes:
                location = geocodes[0].get("location", "")
                if location:
                    return location
        return None

    async def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Any:
        tool_name_map = {
            "walking": "maps_direction_walking",
            "driving": "maps_direction_driving",
            "transit": "maps_direction_transit_integrated",
            "bicycling": "maps_direction_bicycling",
        }
        tool_name = tool_name_map.get(route_type)
        if not tool_name:
            return {"error": f"不支持的路线类型: {route_type}"}

        origin_coord = await self._geocode_address(origin_address, origin_city)
        dest_coord = await self._geocode_address(destination_address, destination_city)

        if not origin_coord:
            return {"error": f"无法解析起点地址: {origin_address}"}
        if not dest_coord:
            return {"error": f"无法解析终点地址: {destination_address}"}

        arguments = {
            "origin": origin_coord,
            "destination": dest_coord
        }
        if route_type == "transit":
            arguments["city"] = origin_city or destination_city or ""
            arguments["cityd"] = destination_city or origin_city or ""

        result = await self._call_tool(tool_name, arguments)
        return self._parse_result(result)

    async def geocode(self, address: str, city: Optional[str] = None) -> Any:
        arguments = {"address": address}
        if city:
            arguments["city"] = city
        result = await self._call_tool("maps_geo", arguments)
        return self._parse_result(result)

    async def get_poi_detail(self, poi_id: str) -> Any:
        result = await self._call_tool("maps_search_detail", {"id": poi_id})
        return self._parse_result(result)

    async def measure_distance(
        self,
        origins: str,
        destination: str,
        distance_type: str = "3"
    ) -> Any:
        result = await self._call_tool("maps_distance", {
            "origins": origins,
            "destination": destination,
            "type": distance_type
        })
        return self._parse_result(result)

    async def regeocode(self, location: str) -> Any:
        result = await self._call_tool("maps_regeocode", {"location": location})
        return self._parse_result(result)


# ---- 单例 ----

_langchain_amap_service: Optional[LangChainAmapService] = None
_service_lock = threading.Lock()


def get_langchain_amap_service() -> LangChainAmapService:
    global _langchain_amap_service
    if _langchain_amap_service is None:
        with _service_lock:
            if _langchain_amap_service is None:
                _langchain_amap_service = LangChainAmapService()
    return _langchain_amap_service


# ---- 向后兼容的模块级函数（utils/route.py 等引用） ----

def _is_connection_error(e: Exception) -> bool:
    return BaseMCPService._is_connection_error(e)


async def _reset_mcp_client() -> None:
    service = get_langchain_amap_service()
    await service._reset_client()


async def get_mcp_tools() -> List[BaseTool]:
    service = get_langchain_amap_service()
    return await service.get_tools()


async def get_mcp_tool_by_name(name: str) -> Optional[BaseTool]:
    service = get_langchain_amap_service()
    return await service.get_tool(name)

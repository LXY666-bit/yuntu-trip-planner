"""AIGoHotel MCP 服务封装

通过魔搭社区接入 AIGoHotel MCP，提供酒店搜索和详情查询能力。
使用 langchain-mcp-adapters 官方适配器，streamable_http 传输方式。

工具列表:
- GetHotelSearchTags: 获取酒店搜索标签元数据
- SearchHotels (find-hotels): 多条件酒店信息搜索
- GetHotelDetail: 单个酒店房型价格及详细信息
"""

import threading
from typing import Optional, Dict, Any, List

from langchain_core.tools import BaseTool

from ..config import get_settings
from .base_mcp_service import BaseMCPService


class AIGoHotelConfigError(Exception):
    """AIGoHotel 配置错误"""
    pass


class AIGoHotelService(BaseMCPService):
    """AIGoHotel MCP 服务封装类

    提供酒店搜索和详情查询的统一异步接口。
    韧性增强:
    - _call_tool 内置超时控制和断线重连
    - health_check 方法用于探测连接状态
    """

    _service_name = "AIGoHotel"

    def _build_mcp_config(self) -> Dict[str, Any]:
        settings = get_settings()
        if not settings.aigohotel_mcp_url:
            raise AIGoHotelConfigError("AIGOHOTEL_MCP_URL 未配置")
        return {
            "aigohotel": {
                "transport": "streamable_http",
                "url": settings.aigohotel_mcp_url,
                "timeout": 60,
            }
        }

    # ---- AIGoHotel 业务方法 ----

    async def search_hotels(
        self,
        place: str,
        origin_query: str = "",
        place_type: str = "城市",
        check_in: Optional[str] = None,
        stay_nights: Optional[int] = None,
        star_ratings: Optional[List[float]] = None,
        adult_count: Optional[int] = None,
        distance_in_meter: Optional[int] = None,
        size: Optional[int] = None,
        with_hotel_amenities: bool = True,
        with_room_amenities: bool = True,
    ) -> Any:
        """搜索酒店

        Args:
            place: 搜索地点（城市、景点、机场等）
            origin_query: 用户原始需求描述（如"帮我找杭州西湖附近的酒店"）
            place_type: 地点类型（城市/景点/机场/火车站/地铁站/酒店/具体地址），默认"城市"
            check_in: 入住日期 yyyy-MM-dd
            stay_nights: 住宿天数
            star_ratings: 星级范围如 [4.0, 5.0]
            adult_count: 每间房成人数量
            distance_in_meter: 以POI为中心的半径（米）
            size: 返回数量，默认10，最大20
            with_hotel_amenities: 是否包含酒店设施
            with_room_amenities: 是否包含房间设施
        """
        arguments: Dict[str, Any] = {"place": place, "placeType": place_type}
        if origin_query:
            arguments["originQuery"] = origin_query

        # 新版 MCP Schema: 日期/人数收进 checkInParam，筛选条件收进 filterOptions
        check_in_param: Dict[str, Any] = {}
        if check_in:
            check_in_param["checkInDate"] = check_in
        if stay_nights is not None:
            check_in_param["stayNights"] = stay_nights
        if adult_count is not None:
            check_in_param["adultCount"] = adult_count
        if check_in_param:
            arguments["checkInParam"] = check_in_param

        filter_options: Dict[str, Any] = {}
        if star_ratings:
            filter_options["starRatings"] = star_ratings
        if distance_in_meter is not None:
            filter_options["distanceInMeter"] = distance_in_meter
        if filter_options:
            arguments["filterOptions"] = filter_options

        if size is not None:
            arguments["size"] = size
        if with_hotel_amenities:
            arguments["withHotelAmenities"] = True
        if with_room_amenities:
            arguments["withRoomAmenities"] = True

        result = await self._call_tool("SearchHotels", arguments, timeout=45.0)
        return self._parse_result(result)

    async def get_hotel_detail(
        self,
        hotel_id: int | str,
        check_in: Optional[str] = None,
        stay_nights: Optional[int] = None,
        adult_count: Optional[int] = None,
    ) -> Any:
        """获取酒店详情（新 Schema: 日期收进 dateParam，人数收进 occupancyParam）"""
        arguments: Dict[str, Any] = {"hotelId": hotel_id}
        date_param: Dict[str, Any] = {}
        if check_in:
            date_param["checkInDate"] = check_in
        if stay_nights is not None:
            date_param["stayNights"] = stay_nights
        if date_param:
            arguments["dateParam"] = date_param
        if adult_count is not None:
            arguments["occupancyParam"] = {"adultCount": adult_count}

        result = await self._call_tool("GetHotelDetail", arguments, timeout=30.0)
        return self._parse_result(result)


# ---- 单例 ----

_aigohotel_service: Optional[AIGoHotelService] = None
_service_lock = threading.Lock()


def get_aigohotel_service() -> Optional[AIGoHotelService]:
    """获取 AIGoHotel 服务实例

    如果 AIGOHOTEL_MCP_URL 未配置，返回 None，调用方应降级到高德搜索。
    """
    global _aigohotel_service
    if _aigohotel_service is None:
        with _service_lock:
            if _aigohotel_service is None:
                try:
                    _aigohotel_service = AIGoHotelService()
                    _aigohotel_service._build_mcp_config()  # 验证配置
                except AIGoHotelConfigError as e:
                    print(f"⚠️ AIGoHotel MCP 未配置: {e}")
                    return None
    return _aigohotel_service

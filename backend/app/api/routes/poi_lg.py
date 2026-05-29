"""POI相关API路由 (LangGraph版本)

重构说明:
- 原始路由(poi.py)使用 amap_service (旧MCP封装) 和 unsplash_service
- 本路由使用 langchain-mcp-adapters 官方适配器
- 图片搜索: 优先小红书实拍, 降级高德POI
- 响应模型统一使用 schemas.py 中定义的类型
- 所有服务调用均为异步
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ...models.schemas import (
    POISearchResponse,
    POIDetailResponse
)
from ...services.langchain_amap_tools import get_langchain_amap_service
router = APIRouter(prefix="/poi", tags=["POI"])


@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息，使用LangChain MCP适配器"
)
async def get_poi_detail(poi_id: str):
    try:
        service = get_langchain_amap_service()
        result = await service.get_poi_detail(poi_id=poi_id)

        return POIDetailResponse(
            success=True,
            message="获取POI详情成功",
            data=result
        )

    except Exception as e:
        print(f"❌ 获取POI详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取POI详情失败: {str(e)}")


@router.get(
    "/search",
    response_model=POISearchResponse,
    summary="搜索POI",
    description="根据关键词搜索POI，使用LangChain MCP适配器"
)
async def search_poi(
    keywords: str = Query(..., description="搜索关键词", example="故宫"),
    city: str = Query(default="北京", description="城市名称", example="北京")
):
    try:
        service = get_langchain_amap_service()
        result = await service.search_poi(keywords=keywords, city=city)

        return POISearchResponse(
            success=True,
            message="搜索成功",
            data=result if isinstance(result, list) else []
        )

    except Exception as e:
        print(f"❌ 搜索POI失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索POI失败: {str(e)}")


@router.get(
    "/photo",
    summary="获取景点图片",
    description="根据景点名称获取图片: 优先小红书实拍, 降级高德POI"
)
async def get_attraction_photo(
    name: str = Query(..., description="景点名称"),
    city: str = Query(default="", description="所在城市"),
):
    try:
        photo_url = None

        # 1. 优先: 小红书真实用户照片
        try:
            from ...services.xhs_service import is_xhs_available, get_photo_from_xhs
            if is_xhs_available():
                search_query = f"{city} {name} 风景" if city else f"{name} 风景"
                xhs_url = await get_photo_from_xhs(search_query)
                if xhs_url:
                    photo_url = xhs_url
                    print(f"📷 小红书照片: {name} -> {photo_url[:80]}...")
                else:
                    print(f"⚠️ 小红书未找到照片: {name}, 降级高德")
        except Exception as e:
            print(f"⚠️ 小红书照片获取失败: {str(e)[:80]}，降级高德")

        # 2. 降级: 高德 maps_text_search 获取照片 (免费, 不限量)
        if not photo_url:
            try:
                amap_service = get_langchain_amap_service()
                search_tool = await amap_service.get_tool("maps_text_search")
                if search_tool:
                    search_kw = f"{city} {name}" if city else name
                    from ...agents.langgraph_agent.exceptions import _invoke_tool_with_retry
                    result = await _invoke_tool_with_retry(
                        search_tool,
                        {"keywords": search_kw, "city": city or name},
                        max_retries=1,
                        per_attempt_timeout=8.0,
                    )
                    result_str = str(result)
                    import re, json
                    photo_patterns = [
                        r'"photo"\s*:\s*"([^"]+)"',
                        r'"photos"\s*:\s*\[.*?"url"\s*:\s*"([^"]+)"',
                        r'"image_url"\s*:\s*"([^"]+)"',
                    ]
                    for pattern in photo_patterns:
                        match = re.search(pattern, result_str, re.DOTALL)
                        if match:
                            photo_url = match.group(1)
                            if photo_url.startswith("http"):
                                break
                            photo_url = None

                    if not photo_url:
                        match = re.search(r'"photos"\s*:\s*(\[.*?\])', result_str, re.DOTALL)
                        if match:
                            try:
                                photos = json.loads(match.group(1))
                                if photos and isinstance(photos, list) and isinstance(photos[0], dict):
                                    photo_url = photos[0].get("url")
                            except (json.JSONDecodeError, TypeError):
                                pass

                    if photo_url:
                        print(f"📷 高德POI照片: {name} -> {photo_url[:80]}...")
            except Exception as e:
                print(f"⚠️ 高德照片获取失败: {str(e)[:80]}，无更多降级源")

        return {
            "success": True,
            "message": "获取图片成功" if photo_url else "未找到图片",
            "data": {
                "name": name,
                "photo_url": photo_url
            }
        }

    except Exception as e:
        print(f"❌ 获取景点图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取景点图片失败: {str(e)}")

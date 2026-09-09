import re
import json
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from ..exceptions import _invoke_llm_with_retry, _invoke_tool_with_retry, NonRetryableError
from ..prompts import WEB_SEARCH_ATTRACTION_PROMPT, EXTRACT_ATTRACTIONS_PROMPT, WEATHER_AGENT_PROMPT, HOTEL_AGENT_PROMPT
from ..state import TripPlannerState
from ..utils.parsing import _extract_poi_names
from ....services.langchain_amap_tools import get_langchain_amap_service
from ....services.llm_service import get_llm
from ....services.preferences_service import format_preference_hint

_DDG_AVAILABLE = False
try:
    from langchain_community.tools import DuckDuckGoSearchResults
    _DDG_AVAILABLE = True
except ImportError:
    print("⚠️ duckduckgo-search 未安装，景点搜索将降级使用高德API。请运行: pip install duckduckgo-search")

_BING_AVAILABLE = False
try:
    from ....services.bing_mcp_service import get_bing_service
    _BING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 必应 MCP 服务导入失败: {e}")

_XHS_AVAILABLE = False
try:
    from ....services.xhs_service import is_xhs_available, search_xhs_attractions
    _XHS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 小红书服务导入失败: {e}")

# 城市名中文→英文映射
_CITY_EN_MAP: dict[str, str] = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
    "深圳": "Shenzhen", "杭州": "Hangzhou", "成都": "Chengdu",
    "重庆": "Chongqing", "西安": "Xi'an", "南京": "Nanjing",
    "武汉": "Wuhan", "厦门": "Xiamen", "苏州": "Suzhou",
    "三亚": "Sanya", "丽江": "Lijiang", "大理": "Dali",
    "拉萨": "Lhasa", "哈尔滨": "Harbin", "昆明": "Kunming",
    "青岛": "Qingdao", "桂林": "Guilin", "张家界": "Zhangjiajie",
    "长沙": "Changsha", "郑州": "Zhengzhou", "天津": "Tianjin",
    "济南": "Jinan", "合肥": "Hefei", "南昌": "Nanchang",
    "贵阳": "Guiyang", "南宁": "Nanning", "沈阳": "Shenyang",
    "大连": "Dalian", "福州": "Fuzhou", "珠海": "Zhuhai",
}

# 中文短语→英文翻译（长→短排序，确保长短语优先匹配）
_CN_TO_EN_PHRASES: list[tuple[str, str]] = [
    ("必去景点 top10", "top attractions"),
    ("旅游攻略 必去", "must visit travel guide"),
    ("最值得去的景点", "best places to visit"),
    ("旅游景点推荐", "tourist attractions"),
    ("十大景点", "top 10 attractions"),
    ("冷门景点 小众", "hidden gems"),
    ("周边景点推荐", "nearby attractions"),
    ("低价景点推荐", "budget attractions"),
    ("免费景点", "free attractions"),
    ("必去景点", "must-see attractions"),
    ("景点推荐", "attraction recommendations"),
    ("旅游攻略", "travel guide"),
    ("一个人", "solo"),
    ("情侣", "couple"),
    ("亲子", "family"),
    ("朋友", "friends"),
    ("老人", "elderly"),
    ("团队", "group"),
]

# 偏好关键词中文→英文映射
_PREF_EN_MAP: dict[str, str] = {
    "自然风光": "nature scenery",
    "历史文化": "history culture",
    "美食": "food cuisine",
    "购物": "shopping",
    "休闲": "leisure",
    "娱乐": "entertainment",
    "户外": "outdoor adventure",
    "浪漫": "romantic",
    "摄影": "photography",
    "建筑": "architecture",
    "博物馆": "museums",
    "公园": "parks",
    "海滩": "beach",
    "温泉": "hot springs",
    "古镇": "ancient town",
    "夜景": "night view",
    "文艺": "artsy",
    "小众": "hidden gems",
    "网红": "instagram worthy",
}


def _query_to_en(query: str) -> str:
    """将中文搜索查询翻译为英文（替换所有可识别部分）"""
    result = query
    for cn, en in _CITY_EN_MAP.items():
        if cn in result:
            result = result.replace(cn, en)
            break
    for cn_phrase, en_phrase in _CN_TO_EN_PHRASES:
        result = result.replace(cn_phrase, en_phrase)
    for cn_pref, en_pref in _PREF_EN_MAP.items():
        result = result.replace(cn_pref, en_pref)
    return result


class FreeTextAnalysis(BaseModel):
    attractions: List[str] = Field(default_factory=list, description="用户指定的景点名称")
    food_preferences: List[str] = Field(default_factory=list, description="用户提到的美食/餐饮偏好")
    accommodation_preferences: List[str] = Field(default_factory=list, description="用户提到的住宿偏好")
    general_suggestions: List[str] = Field(default_factory=list, description="用户的非具体意见或建议")


FREE_TEXT_ANALYSIS_PROMPT = """你是一个旅行需求分析专家。请分析用户的额外要求文本，将其分类为以下四类：

1. **attractions**: 用户明确想去的景点、地标、公园、博物馆等具体地点
2. **food_preferences**: 用户提到的美食、餐饮偏好（如"吃广式早茶"、"品尝火锅"）
3. **accommodation_preferences**: 用户提到的住宿要求（如"住江景房"、"要带泳池的酒店"）
4. **general_suggestions**: 用户的其他非具体意见或建议（如"行程不要太赶"、"多留点自由时间"）

请严格按照以下JSON格式返回：
```json
{
  "attractions": ["景点1", "景点2"],
  "food_preferences": ["美食1"],
  "accommodation_preferences": ["住宿要求1"],
  "general_suggestions": ["建议1"]
}
```

注意：
- 只提取用户明确提到的内容，不要推测
- "吃XX"、"品尝XX"、"喝XX"属于food_preferences，不是attractions
- 如果某类没有内容，返回空数组
- 景点名称保持用户原始表述"""


async def analyze_free_text(free_text: str) -> Dict[str, List[str]]:
    if not free_text or not free_text.strip():
        return {"attractions": [], "food_preferences": [], "accommodation_preferences": [], "general_suggestions": []}

    llm = get_llm()
    messages = [
        SystemMessage(content=FREE_TEXT_ANALYSIS_PROMPT),
        HumanMessage(content=f"请分析以下用户额外要求：\n{free_text}"),
    ]

    try:
        response = await _invoke_llm_with_retry(llm, messages, max_retries=1, per_attempt_timeout=15.0)
        content = response.content.strip()

        from ..utils.parsing import _extract_json_from_llm_response
        json_str = _extract_json_from_llm_response(content)
        data = json.loads(json_str)
        result = {
            "attractions": data.get("attractions", []),
            "food_preferences": data.get("food_preferences", []),
            "accommodation_preferences": data.get("accommodation_preferences", []),
            "general_suggestions": data.get("general_suggestions", []),
        }
        print(f"🧠 额外要求分析结果: 景点={result['attractions']}, 美食={result['food_preferences']}, 住宿={result['accommodation_preferences']}, 建议={result['general_suggestions']}")
        return result
    except Exception as e:
        print(f"⚠️ LLM分析额外要求失败，降级到简单提取: {str(e)[:100]}")
        attractions = []
        from ._landmarks import KNOWN_LANDMARKS
        for landmark in KNOWN_LANDMARKS:
            if landmark in free_text:
                attractions.append(landmark)
        return {"attractions": attractions, "food_preferences": [], "accommodation_preferences": [], "general_suggestions": []}


def _extract_must_visit_attractions(free_text: str) -> List[str]:
    if not free_text:
        return []
    names = set()
    trigger_patterns = [
        r'想去(.+)',
        r'一定要去(.+)',
        r'必须去(.+)',
        r'特别想去(.+)',
        r'希望去(.+)',
        r'想要去(.+)',
    ]
    for pattern in trigger_patterns:
        matches = re.findall(pattern, free_text)
        for match in matches:
            parts = re.split(r'[，,、；;和还有以及\s]+', match)
            for name in parts:
                name = name.strip().rstrip('。.！!？?')
                if name and 2 <= len(name) <= 20:
                    names.add(name)
    from ._landmarks import KNOWN_LANDMARKS
    for landmark in KNOWN_LANDMARKS:
        if landmark in free_text:
            names.add(landmark)
    return list(names)


def _get_preference_hint(state: TripPlannerState) -> str:
    preferences = state.get("user_preferences")
    if preferences:
        return "\n\n" + format_preference_hint(preferences)
    return ""


async def web_search_attractions_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🔍 执行节点: web_search_attractions_node")
    request = state["request"]
    city = request.city
    preferences = request.preferences or []
    companions = request.companions
    budget = request.budget

    if not _DDG_AVAILABLE:
        print("⚠️ DuckDuckGo不可用，降级使用高德搜索景点")
        try:
            service = get_langchain_amap_service()
            search_tool = await service.get_tool("maps_text_search")
            if search_tool:
                keywords = preferences[0] if preferences else "景点"
                fallback_result = await _invoke_tool_with_retry(
                    search_tool,
                    {"keywords": keywords, "city": city},
                    max_retries=2,
                    per_attempt_timeout=15.0,
                )
                return {
                    "raw_search_results": "",
                    "attractions_info": str(fallback_result),
                }
        except Exception as e:
            print(f"⚠️ 降级高德搜索也失败: {e}")
        return {
            "raw_search_results": "",
            "errors": ["web_search_attractions: DuckDuckGo不可用且降级搜索失败"],
        }

    try:
        travel_days = request.travel_days
        search_queries = []

        search_queries.extend([
            f"{city} 必去景点 top10",
            f"{city} 旅游攻略 必去",
            f"{city} 最值得去的景点",
        ])

        if travel_days >= 3:
            search_queries.extend([
                f"{city} 十大景点",
                f"{city} 旅游景点推荐",
            ])

        if travel_days >= 5:
            search_queries.extend([
                f"{city} 冷门景点 小众",
                f"{city} 周边景点推荐",
            ])

        if preferences:
            companion_label = ""
            if companions:
                companion_map = {
                    "solo": "一个人",
                    "couple": "情侣",
                    "family": "亲子",
                    "friends": "朋友",
                    "elderly": "老人",
                    "group": "团队",
                }
                companion_label = companion_map.get(companions.type, "")

            for pref in preferences[:3]:
                if companion_label:
                    search_queries.append(f"{city} {pref} {companion_label} 景点推荐")
                search_queries.append(f"{city} {pref} 必去景点")
                search_queries.append(f"{city} {pref} 旅游攻略")

        if budget is not None and budget < 3000:
            search_queries.append(f"{city} 免费景点")
            search_queries.append(f"{city} 低价景点推荐")

        analysis = await analyze_free_text(request.free_text_input or "")
        must_visit = analysis.get("attractions", [])
        if must_visit:
            for name in must_visit[:3]:
                search_queries.append(f"{name} {city} 旅游攻略")

        import asyncio as asyncio_mod

        # ========== 主搜索: 小红书 + 必应 并行 ==========
        async def _search_xhs():
            """小红书搜索 (真实游记数据)"""
            results = []
            xhs_keywords = "旅游攻略"
            if not _XHS_AVAILABLE or not is_xhs_available():
                print("  ⚠️ 小红书服务不可用或 Cookie 未配置，跳过")
                return results, 0
            print(f"  📕 尝试使用小红书搜索 {city} 的景点...")
            try:
                xhs_result = await asyncio_mod.to_thread(search_xhs_attractions, city, xhs_keywords)
                if xhs_result and "未在小红书检索到" not in xhs_result and "结构化数据失败" not in xhs_result:
                    results.append(f"=== [小红书] {city} 热门游记提纯结果 ===\n{xhs_result}")
                    print(f"  ✅ 小红书搜索成功: {city} {xhs_keywords}")
                    return results, 1
                else:
                    print(f"  ⚠️ 小红书搜索无结果")
            except Exception as e:
                print(f"  ⚠️ 小红书搜索失败({city}): {str(e)[:100]}")
            return results, 0

        async def _search_bing():
            """必应 MCP 搜索（中文被拦截时自动切换英文）"""
            results = []
            bing_service = get_bing_service() if _BING_AVAILABLE else None
            if not bing_service:
                print("  ⚠️ 必应 MCP 未配置或导入失败，跳过")
                return results, 0
            print("  🔍 尝试使用必应 MCP 搜索...")
            count = 0
            _MODERATION_KW = ["不当内容", "请修改输入", "content policy", "inappropriate", "unsafe"]

            for query in search_queries[:6]:
                en_query = _query_to_en(query)
                candidates = [query]
                if en_query != query:
                    candidates.append(en_query)

                for attempt, q in enumerate(candidates):
                    try:
                        result = await bing_service.search(query=q, count=5)
                        result_str = str(result) if not isinstance(result, str) else result
                        if result_str and len(result_str) > 50:
                            results.append(f"=== [必应] 搜索词: {q} ===\n{result_str}")
                            count += 1
                            if attempt > 0:
                                print(f"  ✅ 必应英文重试成功: '{query}' -> '{q}'")
                            else:
                                print(f"  ✅ 必应搜索成功: {q}")
                            break
                    except Exception as e:
                        error_msg = str(e)
                        if any(kw in error_msg for kw in _MODERATION_KW):
                            if attempt < len(candidates) - 1:
                                print(f"  🔄 中文被拦截，切换英文: '{q}' -> '{candidates[attempt+1]}'")
                                continue
                            print(f"  🚫 必应中英文均被拦截: {query}")
                        else:
                            print(f"  ⚠️ 必应搜索失败({q}): {error_msg[:100]}")
                        break
            if count > 0:
                print(f"  ✅ 必应 MCP 共获取 {count} 条结果")
            else:
                print(f"  ⚠️ 必应 MCP 0 条结果")
            return results, count

        # 并行执行主搜索 (小红书 + 必应)
        xhs_results, bing_results = await asyncio_mod.gather(
            _search_xhs(),
            _search_bing(),
        )

        xhs_success_count = xhs_results[1]
        bing_success_count = bing_results[1]
        all_results = xhs_results[0] + bing_results[0]

        # ========== 降级: DuckDuckGo (仅当主搜索全部失败) ==========
        ddg_success_count = 0
        if not all_results and _DDG_AVAILABLE:
            print("  🔍 主搜索无结果，降级使用 DuckDuckGo...")
            ddg_tool = DuckDuckGoSearchResults(max_results=5)
            for query in search_queries[:6]:
                try:
                    result = await _invoke_tool_with_retry(
                        ddg_tool,
                        {"query": query},
                        max_retries=1,
                        per_attempt_timeout=15.0,
                    )
                    result_str = str(result)
                    if result_str and len(result_str) > 20:
                        all_results.append(f"=== [DuckDuckGo] 搜索词: {query} ===\n{result_str}")
                        ddg_success_count += 1
                        print(f"  ✅ DuckDuckGo搜索成功: {query}")
                except Exception as e:
                    print(f"  ⚠️ DuckDuckGo搜索失败({query}): {e}")
            if ddg_success_count > 0:
                print(f"  ✅ DuckDuckGo 共获取 {ddg_success_count} 条结果")
        elif not all_results:
            print("  ⚠️ DuckDuckGo 未安装，无更多降级源")

        if not all_results:
            return {
                "raw_search_results": "",
                "errors": ["web_search_attractions: 所有搜索引擎均无结果"],
            }

        raw_results = "\n\n".join(all_results)
        print(f"🔍 搜索完成: 小红书{xhs_success_count}条, 必应{bing_success_count}条, 降级DDG{ddg_success_count}条, 共{len(all_results)}条结果")
        return {"raw_search_results": raw_results}
    except NonRetryableError as e:
        print(f"❌ web_search_attractions_node 不可重试错误: {e}")
        return {
            "raw_search_results": "",
            "errors": [f"web_search_attractions: 不可重试错误 - {str(e)[:200]}"],
        }
    except Exception as e:
        print(f"❌ web_search_attractions_node 异常: {e}")
        return {
            "raw_search_results": "",
            "errors": [f"web_search_attractions: 搜索失败 - {str(e)[:200]}"],
        }


async def extract_attractions_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🧠 执行节点: extract_attractions_node")
    raw_results = state.get("raw_search_results", "")
    request = state["request"]

    if not raw_results:
        print("⚠️ extract_attractions: 搜索结果为空，降级到高德搜索")
        try:
            service = get_langchain_amap_service()
            search_tool = await service.get_tool("maps_text_search")
            if search_tool:
                keywords = request.preferences[0] if request.preferences else "景点"
                fallback_result = await _invoke_tool_with_retry(
                    search_tool,
                    {"keywords": keywords, "city": request.city},
                    max_retries=2,
                    per_attempt_timeout=15.0,
                )
                return {
                    "selected_pois": [],
                    "attractions_info": str(fallback_result),
                }
        except Exception as e:
            print(f"⚠️ 降级高德搜索也失败: {e}")
        return {
            "selected_pois": [],
            "errors": ["extract_attractions: 搜索结果为空且降级搜索失败"],
        }

    try:
        llm = get_llm()
        travel_days = request.travel_days
        max_count = travel_days * 3
        preferences = request.preferences or []
        pref_hint = f"\n用户偏好: {', '.join(preferences)}" if preferences else "\n用户无特殊偏好（按通用景点提取）"

        prompt = f"旅行天数: {travel_days}天，最多提取{max_count}个景点（但只提取搜索结果中明确提到的，不要凑数）。{pref_hint}\n\n以下是搜索结果:\n{raw_results[:15000]}"
        response = await _invoke_llm_with_retry(
            llm,
            [SystemMessage(content=EXTRACT_ATTRACTIONS_PROMPT), HumanMessage(content=prompt)],
            max_retries=2,
            per_attempt_timeout=30.0,
        )

        content = response.content.strip()
        pois = []

        from ..utils.parsing import _extract_json_from_llm_response
        json_str = _extract_json_from_llm_response(content)

        pois = json.loads(json_str)
        if not isinstance(pois, list):
            pois = []

        valid_pois = []
        for poi in pois:
            if isinstance(poi, dict) and poi.get("name"):
                valid_pois.append({
                    "name": poi["name"],
                    "description": poi.get("description", ""),
                })

        if not valid_pois:
            print("⚠️ extract_attractions: LLM未提取到有效景点，降级到高德搜索")
            try:
                service = get_langchain_amap_service()
                search_tool = await service.get_tool("maps_text_search")
                if search_tool:
                    keywords = request.preferences[0] if request.preferences else "景点"
                    fallback_result = await _invoke_tool_with_retry(
                        search_tool,
                        {"keywords": keywords, "city": request.city},
                        max_retries=2,
                        per_attempt_timeout=15.0,
                    )
                    return {
                        "selected_pois": [],
                        "attractions_info": str(fallback_result),
                    }
            except Exception as e:
                print(f"⚠️ 降级高德搜索也失败: {e}")

        print(f"🧠 LLM提取到 {len(valid_pois)} 个核心景点: {[p['name'] for p in valid_pois]}")

        # 自动补充：如果提取到的景点数量不足，用高德搜索补充
        min_attractions = travel_days * 2
        if len(valid_pois) < min_attractions:
            print(f"⚠️ 景点数量不足({len(valid_pois)} < {min_attractions})，尝试用高德搜索补充...")
            try:
                service = get_langchain_amap_service()
                search_tool = await service.get_tool("maps_text_search")
                if search_tool:
                    keywords = request.preferences[0] if request.preferences else "景点"
                    fallback_result = await _invoke_tool_with_retry(
                        search_tool,
                        {"keywords": keywords, "city": request.city},
                        max_retries=2,
                        per_attempt_timeout=15.0,
                    )
                    fallback_str = str(fallback_result)
                    from ..utils.parsing import _extract_poi_names
                    extra_pois = _extract_poi_names(fallback_str)
                    existing_names = {p["name"] for p in valid_pois}
                    added = 0
                    for poi in extra_pois:
                        if poi.get("name") and poi["name"] not in existing_names:
                            valid_pois.append({
                                "name": poi["name"],
                                "description": poi.get("address", "") or "高德推荐景点",
                            })
                            existing_names.add(poi["name"])
                            added += 1
                            if len(valid_pois) >= min_attractions:
                                break
                    if added > 0:
                        print(f"  ✅ 高德补充了 {added} 个景点，现在共 {len(valid_pois)} 个")
            except Exception as e:
                print(f"  ⚠️ 高德补充搜索失败: {e}")

        return {"selected_pois": valid_pois}
    except NonRetryableError as e:
        print(f"❌ extract_attractions_node 不可重试错误: {e}")
        return {
            "selected_pois": [],
            "errors": [f"extract_attractions: 不可重试错误 - {str(e)[:200]}"],
        }
    except Exception as e:
        print(f"❌ extract_attractions_node 异常: {e}")
        return {
            "selected_pois": [],
            "errors": [f"extract_attractions: 提取失败 - {str(e)[:200]}"],
        }


async def geocode_attractions_node(state: TripPlannerState) -> Dict[str, Any]:
    print("📍 执行节点: geocode_attractions_node")
    selected_pois = state.get("selected_pois", [])
    request = state["request"]

    if state.get("attractions_info"):
        print("  ⏭️ 已有attractions_info（降级搜索结果），跳过地理编码")
        return {}

    if not selected_pois:
        return {
            "attractions_info": "",
            "errors": ["geocode_attractions: 无景点需要地理编码"],
        }

    try:
        service = get_langchain_amap_service()
        search_tool = await service.get_tool("maps_text_search")
        detail_tool = await service.get_tool("maps_search_detail")

        results = []
        failed_pois = []

        for poi in selected_pois:
            name = poi["name"]
            found = False

            for attempt_name in [name, re.sub(r'(风景名胜区|风景区|景区|旅游区|度假区|步行街|商业街)$', '', name)]:
                if not attempt_name or (attempt_name == name and found):
                    continue
                try:
                    search_result = await _invoke_tool_with_retry(
                        search_tool,
                        {"keywords": attempt_name, "city": request.city},
                        max_retries=2,
                        per_attempt_timeout=15.0,
                    )
                    result_str = str(search_result)
                    poi_list = _extract_poi_names(result_str)

                    if poi_list:
                        best_poi = poi_list[0]
                        if detail_tool and best_poi.get("id"):
                            try:
                                detail_result = await _invoke_tool_with_retry(
                                    detail_tool,
                                    {"id": best_poi["id"]},
                                    max_retries=1,
                                    per_attempt_timeout=10.0,
                                )
                                detail_str = str(detail_result)
                                if len(detail_str) > 20:
                                    results.append(detail_str)
                                    print(f"  ✅ maps_search_detail获取坐标: {name} (id={best_poi['id']})")
                                    found = True
                                    break
                            except Exception as e:
                                print(f"  ⚠️ maps_search_detail失败({name}): {e}")

                        results.append(result_str)
                        print(f"  ✅ 高德搜索到景点: {name}")
                        found = True
                        break
                    elif len(result_str) > 20 and "没有找到" not in result_str:
                        results.append(result_str)
                        print(f"  ✅ 高德搜索到景点(未解析POI): {name}")
                        found = True
                        break
                except Exception as e:
                    print(f"  ⚠️ 搜索景点{attempt_name}失败: {e}")

            if not found:
                failed_pois.append(name)

        if failed_pois:
            print(f"⚠️ 以下景点未在高德中找到: {failed_pois}")

        if not results:
            return {
                "attractions_info": "",
                "errors": ["geocode_attractions: 所有景点高德搜索失败"],
            }

        attractions_info = "\n".join(results)
        print(f"📍 高德搜索完成: {len(results)}/{len(selected_pois)} 个景点成功搜索到")
        return {"attractions_info": attractions_info}
    except NonRetryableError as e:
        print(f"❌ geocode_attractions_node 不可重试错误: {e}")
        return {
            "attractions_info": "",
            "errors": [f"geocode_attractions: 不可重试错误 - {str(e)[:200]}"],
        }
    except Exception as e:
        print(f"❌ geocode_attractions_node 异常: {e}")
        return {
            "attractions_info": "",
            "errors": [f"geocode_attractions: 地理编码失败 - {str(e)[:200]}"],
        }


async def search_weather_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🌤️  执行节点: search_weather_node")
    request = state["request"]

    try:
        service = get_langchain_amap_service()
        weather_tool = await service.get_tool("maps_weather")
        if weather_tool is None:
            return {
                "weather_info": "",
                "errors": ["search_weather: maps_weather 工具不可用"],
            }
        llm = get_llm()
        llm_with_tools = llm.bind_tools([weather_tool])

        prompt = WEATHER_AGENT_PROMPT + f"\n请查询城市: {request.city} 的天气。" + _get_preference_hint(state)
        response = await _invoke_llm_with_retry(llm_with_tools, [SystemMessage(content=WEATHER_AGENT_PROMPT), HumanMessage(content=prompt)])

        results = []
        if response.tool_calls:
            for tool_call in response.tool_calls:
                try:
                    tool_result = await _invoke_tool_with_retry(weather_tool, tool_call["args"])
                    results.append(str(tool_result))
                except NonRetryableError as e:
                    print(f"⚠️ search_weather 工具调用不可重试: {e}")
                    return {
                        "weather_info": "",
                        "errors": [f"search_weather: 工具调用不可重试 - {str(e)[:200]}"],
                    }
                except Exception as e:
                    print(f"⚠️ search_weather 工具调用失败: {e}")
                    results.append(f"[工具调用失败: {str(e)[:100]}]")

        if not results:
            print("⚠️ search_weather_node: LLM未调用工具，直接查询天气...")
            try:
                direct_result = await _invoke_tool_with_retry(
                    weather_tool,
                    {"city": request.city},
                    max_retries=2,
                    per_attempt_timeout=15.0,
                )
                results.append(str(direct_result))
                print(f"  ✅ 直接查询天气成功")
            except Exception as e:
                print(f"⚠️ search_weather 直接查询也失败: {e}")
                return {
                    "weather_info": "",
                    "errors": ["search_weather: LLM未调用工具且直接查询也失败"],
                }

        return {"weather_info": "\n".join(results)}
    except NonRetryableError as e:
        print(f"❌ search_weather_node 不可重试错误: {e}")
        return {
            "weather_info": "",
            "errors": [f"search_weather: 不可重试错误 - {str(e)[:200]}"],
        }
    except Exception as e:
        print(f"❌ search_weather_node 异常: {e}")
        return {
            "weather_info": "",
            "errors": [f"search_weather: 查询失败 - {str(e)[:200]}"],
        }


def _accommodation_to_star_ratings(accommodation: str) -> list:
    if "经济" in accommodation:
        return [2, 3]
    elif "舒适" in accommodation:
        return [3, 4]
    elif "豪华" in accommodation:
        return [4, 5]
    return []


async def search_hotel_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🏨 执行节点: search_hotel_node")
    request = state["request"]

    try:
        from ....services.aigohotel_mcp_service import get_aigohotel_service
        aigohotel_service = get_aigohotel_service()
        if not aigohotel_service:
            return {
                "hotels_info": "",
                "errors": ["search_hotel: AIGoHotel 服务未配置"],
            }

        try:
            await aigohotel_service.get_tools()
            search_tool = await aigohotel_service.get_tool("SearchHotels")
            if not search_tool:
                search_tool = await aigohotel_service.get_tool("find-hotels")
            if not search_tool:
                return {
                    "hotels_info": "",
                    "errors": ["search_hotel: AIGoHotel SearchHotels 工具不可用"],
                }
            print("  ✅ AIGoHotel 搜索工具已加载")
        except Exception as e:
            print(f"  ❌ AIGoHotel 初始化失败: {e}")
            return {
                "hotels_info": "",
                "errors": [f"search_hotel: AIGoHotel 初始化失败 - {str(e)[:200]}"],
            }

        llm = get_llm()
        llm_with_tools = llm.bind_tools([search_tool])

        origin_query = f"搜索{request.city}的酒店"
        if request.accommodation:
            origin_query = f"搜索{request.city}{request.accommodation}酒店"

        star_ratings = _accommodation_to_star_ratings(request.accommodation or "")

        hotel_hint = f"\n请搜索城市: {request.city}, 关键词: {request.accommodation} 酒店"
        if request.start_date:
            hotel_hint += f", 入住日期: {request.start_date}"
        if request.travel_days:
            hotel_hint += f", 住宿天数: {request.travel_days}晚"
        if star_ratings:
            hotel_hint += f", 请务必设置 starRatings={star_ratings}"
        hotel_hint += _get_preference_hint(state)

        prompt = HOTEL_AGENT_PROMPT + hotel_hint
        response = await _invoke_llm_with_retry(llm_with_tools, [SystemMessage(content=HOTEL_AGENT_PROMPT), HumanMessage(content=prompt)])

        results = []
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                try:
                    tool_result = await _invoke_tool_with_retry(search_tool, tool_call["args"])
                    results.append(str(tool_result))
                    print(f"  ✅ AIGoHotel 工具调用成功: {tool_name}")
                except NonRetryableError as e:
                    print(f"  ⚠️ AIGoHotel 工具调用不可重试: {e}")
                except Exception as e:
                    print(f"  ⚠️ AIGoHotel 工具调用失败: {e}")

        if not results:
            print("⚠️ search_hotel_node: LLM未调用工具，直接搜索...")
            try:
                aigohotel_args: Dict[str, Any] = {
                    "place": request.city,
                    "placeType": "城市",
                    "originQuery": origin_query,
                    "size": 5,
                    "withHotelAmenities": True,
                    "withRoomAmenities": True,
                }
                # 新版 MCP Schema: checkInParam + filterOptions
                check_in_param: Dict[str, Any] = {}
                if request.start_date:
                    check_in_param["checkInDate"] = request.start_date
                if request.travel_days:
                    check_in_param["stayNights"] = request.travel_days
                if check_in_param:
                    aigohotel_args["checkInParam"] = check_in_param
                if star_ratings:
                    aigohotel_args["filterOptions"] = {"starRatings": star_ratings}
                direct_result = await _invoke_tool_with_retry(
                    search_tool,
                    aigohotel_args,
                    max_retries=2,
                    per_attempt_timeout=30.0,
                )
                results.append(str(direct_result))
                print("  ✅ AIGoHotel 直接搜索成功")
            except Exception as e:
                print(f"  ⚠️ AIGoHotel 直接搜索失败: {e}")

        analysis = await analyze_free_text(request.free_text_input or "")
        must_attractions = analysis.get("attractions", [])
        if must_attractions:
            print(f"🏨 搜索用户指定景点附近酒店: {must_attractions}")
            for attr_name in must_attractions[:3]:
                try:
                    nearby_args: Dict[str, Any] = {
                        "place": attr_name,
                        "placeType": "景点",
                        "originQuery": f"搜索{attr_name}附近的酒店",
                        "size": 3,
                        "withHotelAmenities": True,
                        "withRoomAmenities": True,
                    }
                    nearby_filter: Dict[str, Any] = {}
                    if star_ratings:
                        nearby_filter["starRatings"] = star_ratings
                    if nearby_filter:
                        nearby_args["filterOptions"] = nearby_filter
                    nearby_checkin: Dict[str, Any] = {}
                    if request.start_date:
                        nearby_checkin["checkInDate"] = request.start_date
                    if request.travel_days:
                        nearby_checkin["stayNights"] = request.travel_days
                    if nearby_checkin:
                        nearby_args["checkInParam"] = nearby_checkin
                    nearby_result = await _invoke_tool_with_retry(
                        search_tool,
                        nearby_args,
                        max_retries=2,
                        per_attempt_timeout=30.0,
                    )
                    results.append(str(nearby_result))
                    print(f"  ✅ 搜索到{attr_name}附近酒店")
                except Exception as e:
                    print(f"  ⚠️ 搜索{attr_name}附近酒店失败: {e}")

        if not results:
            return {
                "hotels_info": "",
                "errors": ["search_hotel: 酒店搜索无结果"],
            }

        hotels_info = "\n".join(results)
        print(f"🏨 酒店搜索完成: AIGoHotel {len(results)}条结果")
        return {
            "hotels_info": hotels_info,
            "aigohotel_raw_results": hotels_info,
        }
    except NonRetryableError as e:
        print(f"❌ search_hotel_node 不可重试错误: {e}")
        return {
            "hotels_info": "",
            "errors": [f"search_hotel: 不可重试错误 - {str(e)[:200]}"],
        }
    except Exception as e:
        print(f"❌ search_hotel_node 异常: {e}")
        return {
            "hotels_info": "",
            "errors": [f"search_hotel: 搜索失败 - {str(e)[:200]}"],
        }


async def gather_search_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🔗 执行节点: gather_search_node (搜索结果汇总)")
    errors = state.get("errors", [])
    attractions = state.get("attractions_info", "")
    weather = state.get("weather_info", "")
    hotels = state.get("hotels_info", "")

    if not attractions:
        print("⚠️ gather_search: 景点搜索结果为空")
    if not weather:
        print("⚠️ gather_search: 天气查询结果为空")
    if not hotels:
        print("⚠️ gather_search: 酒店搜索结果为空")

    if errors:
        print(f"🚨 gather_search: 汇总时检测到 {len(errors)} 个错误")
        for err in errors[-5:]:
            print(f"   - {err[:200]}")

    return {}


# ============ 骨架阶段: 行程区域酒店候选（支持多城市按 Segment 搜索） ============

from html.parser import HTMLParser


class _HotelDescriptionTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments: List[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.fragments.append(text)


def _clean_hotel_description(description: Any) -> str:
    parser = _HotelDescriptionTextParser()
    parser.feed(str(description))
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.fragments)).strip()


def _unwrap_mcp_payload(raw: Any) -> Any:
    """剥离 MCP 工具返回的多层包裹（text wrapper → JSON 字符串 → dict）。"""
    import ast
    data = raw
    for _ in range(4):
        if isinstance(data, str):
            stripped = data.strip()
            if not stripped:
                return data
            try:
                data = json.loads(stripped)
                continue
            except (json.JSONDecodeError, TypeError):
                try:
                    data = ast.literal_eval(stripped)
                    continue
                except (ValueError, SyntaxError):
                    return data
        if isinstance(data, list) and data and isinstance(data[0], dict) and "text" in data[0]:
            inner = data[0]["text"]
            if isinstance(inner, str):
                data = inner
                continue
        break
    return data


def _parse_aigohotel_hotels(raw: Any) -> List[Dict[str, Any]]:
    """从 AIGoHotel SearchHotels 返回中尽力提取酒店字段，输出 Hotel 兼容 dict 列表。"""
    data = _unwrap_mcp_payload(raw)
    hotels_raw: List[Any] = []
    if isinstance(data, dict):
        for key in ("hotels", "data", "result", "results", "items"):
            val = data.get(key)
            if isinstance(val, list) and val:
                hotels_raw = val
                break
            if isinstance(val, dict):
                inner = val.get("hotels") or val.get("items") or val.get("list")
                if isinstance(inner, list):
                    hotels_raw = inner
                    break
        if not hotels_raw:
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    hotels_raw = v
                    break
    elif isinstance(data, list):
        hotels_raw = data

    parsed: List[Dict[str, Any]] = []
    for h in hotels_raw:
        if not isinstance(h, dict):
            continue
        name = h.get("name") or h.get("hotelName") or h.get("title") or h.get("hotel_name")
        if not name:
            continue
        item: Dict[str, Any] = {"name": str(name)}

        address = h.get("address") or h.get("addr") or h.get("location_desc")
        if address:
            item["address"] = str(address)

        lon = lat = None
        loc = h.get("location") or h.get("position") or h.get("coordinate") or h.get("coordinates")
        if isinstance(loc, dict):
            lon = loc.get("longitude") or loc.get("lng") or loc.get("lon")
            lat = loc.get("latitude") or loc.get("lat")
        elif isinstance(loc, str) and "," in loc:
            parts = loc.split(",")
            if len(parts) >= 2:
                lon, lat = parts[0], parts[1]
        if lon is None:
            lon = h.get("longitude") or h.get("lng") or h.get("lon")
            lat = h.get("latitude") or h.get("lat")
        if lon is not None and lat is not None:
            try:
                lon_f = float(lon)
                lat_f = float(lat)
                if 73 < lon_f < 136 and 3 < lat_f < 54:
                    item["location"] = {"longitude": lon_f, "latitude": lat_f}
            except (TypeError, ValueError):
                pass

        star = h.get("starRating") or h.get("star") or h.get("stars") or h.get("star_rating")
        if star is not None:
            try:
                item["star_rating"] = float(star)
            except (TypeError, ValueError):
                pass

        hotel_id = h.get("hotelId") or h.get("hotel_id") or h.get("id")
        if hotel_id is not None:
            item["hotel_id"] = hotel_id

        price_obj = h.get("price")
        if isinstance(price_obj, dict):
            current_price = price_obj.get("lowestPrice") or price_obj.get("price")
            if price_obj.get("hasPrice", current_price is not None) and current_price is not None:
                try:
                    item["price"] = float(current_price)
                except (TypeError, ValueError):
                    pass
            currency = price_obj.get("currency")
            if currency:
                item["currency"] = str(currency)

        for src_key, dst_key in (("price", "price"), ("totalPrice", "price"), ("originalPrice", "original_price")):
            v = h.get(src_key)
            if isinstance(v, dict):
                continue
            if v is not None and dst_key not in item:
                try:
                    item[dst_key] = float(v)
                except (TypeError, ValueError):
                    pass

        item.setdefault("currency", str(h.get("currency") or "CNY"))

        ham = h.get("hotelAmenities") or h.get("hotel_amenities") or h.get("amenities")
        if isinstance(ham, list):
            item["hotel_amenities"] = [str(a) for a in ham if a]
        ram = h.get("roomAmenities") or h.get("room_amenities")
        if isinstance(ram, list):
            item["room_amenities"] = [str(a) for a in ram if a]

        desc = h.get("description") or h.get("intro") or h.get("summary")
        if desc:
            cleaned_desc = _clean_hotel_description(desc)
            if cleaned_desc:
                item["description"] = cleaned_desc[:500]

        img = h.get("imageUrl") or h.get("image") or h.get("photo") or h.get("mainImage")
        if img:
            item["image_url"] = str(img)
        durl = h.get("bookingUrl") or h.get("detailUrl") or h.get("url") or h.get("link")
        if durl:
            item["detail_url"] = str(durl)

        dim = h.get("distanceInMeter") or h.get("distanceInMeters") or h.get("distance_in_meters")
        if dim is not None:
            try:
                item["distance_in_meters"] = int(float(dim))
            except (TypeError, ValueError):
                pass

        rating = h.get("rating") or h.get("score") or h.get("commentScore") or h.get("comment_score")
        if rating is not None:
            item["rating"] = str(rating)

        hotel_type = h.get("type") or h.get("hotelType") or h.get("category")
        if hotel_type:
            item["type"] = str(hotel_type)

        if "price" in item and item.get("price"):
            try:
                item["estimated_cost"] = int(float(item["price"]))
            except (TypeError, ValueError):
                pass
        if "estimated_cost" not in item:
            star = item.get("star_rating")
            if star and star > 0:
                item["estimated_cost"] = int(star * 200)
            else:
                item["estimated_cost"] = 500

        parsed.append(item)
    return parsed


def _hotels_cluster_centroid(cluster: List[Dict[str, Any]]) -> Optional[tuple]:
    """计算坐标算术平均质心 (lon, lat)，无有效坐标返回 None。"""
    coords = [
        (c.get("longitude"), c.get("latitude"))
        for c in cluster
        if isinstance(c.get("longitude"), (int, float))
        and isinstance(c.get("latitude"), (int, float))
        and 73 < c["longitude"] < 136 and 3 < c["latitude"] < 54
    ]
    if not coords:
        return None
    return (
        sum(lon for lon, _ in coords) / len(coords),
        sum(lat for _, lat in coords) / len(coords),
    )


def _cluster_outer_radius_km(cluster: List[Dict[str, Any]], centroid: tuple) -> float:
    from ..utils.geo import _haversine_distance
    lon_c, lat_c = centroid
    max_d = 0.0
    for c in cluster:
        if isinstance(c.get("longitude"), (int, float)) and isinstance(c.get("latitude"), (int, float)):
            d = _haversine_distance(lat_c, lon_c, c["latitude"], c["longitude"])
            max_d = max(max_d, d)
    return max_d


def _enrich_hotels_with_distance(hotels: List[Dict[str, Any]], centroid: tuple) -> None:
    """给每家酒店补上"到当日质心"的真实距离（如果有坐标）。"""
    from ..utils.geo import _haversine_distance
    lon_c, lat_c = centroid
    for h in hotels:
        loc = h.get("location")
        if isinstance(loc, dict) and loc.get("longitude") and loc.get("latitude"):
            d_km = _haversine_distance(lat_c, lon_c, loc["latitude"], loc["longitude"])
            h["_centroid_distance_km"] = d_km
            h["distance_in_meters"] = int(d_km * 1000)
            h["distance"] = f"距当日中心 {d_km:.1f} 公里"


def _rank_day_hotels(hotels: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """按 (有星级, 星级 desc, 距离 asc) 排序，去重保留 top_n。"""
    def sort_key(h: Dict[str, Any]):
        star = h.get("star_rating")
        dist = h.get("_centroid_distance_km", 999.0)
        return (
            0 if star is not None else 1,
            -(star or 0),
            dist,
        )
    seen_names: set = set()
    deduped = []
    for h in sorted(hotels, key=sort_key):
        name = h.get("name", "").strip()
        if name and name not in seen_names:
            seen_names.add(name)
            deduped.append(h)
    return deduped[:top_n]


def _format_hotels_by_day_text(hotels_by_day: List[List[Dict[str, Any]]]) -> str:
    """把酒店候选格式化为给 macro_planner 看的文本。

    所有天共享同一份候选时（行程级搜索的常态），只打印一次，避免重复噪声。
    """
    if not hotels_by_day:
        return ""

    def _names_sig(day_hotels: List[Dict[str, Any]]) -> tuple:
        return tuple(h.get("name", "") for h in day_hotels)

    sigs = {_names_sig(d) for d in hotels_by_day}
    shared = len(sigs) == 1 and hotels_by_day[0]

    lines: List[str] = []

    def _format_one_block(day_hotels: List[Dict[str, Any]], header: str) -> None:
        lines.append(header)
        if not day_hotels:
            lines.append("  （无候选）")
            return
        for j, h in enumerate(day_hotels, 1):
            star = h.get("star_rating")
            price = h.get("price")
            dist = h.get("distance") or ""
            addr = h.get("address") or ""
            loc = h.get("location") or {}
            loc_str = ""
            if isinstance(loc, dict) and loc.get("longitude"):
                loc_str = f" 坐标({loc['longitude']:.5f},{loc['latitude']:.5f})"
            parts = [f"  {j}. {h['name']}"]
            if star is not None:
                parts.append(f"{star}星")
            if price is not None:
                parts.append(f"¥{int(price)}")
            if dist:
                parts.append(dist)
            if addr:
                parts.append(addr)
            lines.append(" | ".join(parts) + loc_str)

    if shared:
        _format_one_block(hotels_by_day[0], f"=== 候选酒店（全程 {len(hotels_by_day)} 天共用同一份候选） ===")
    else:
        last_city = None
        for i, day_hotels in enumerate(hotels_by_day):
            header = f"=== 第{i + 1}天候选酒店 ==="
            _format_one_block(day_hotels, header)
    return "\n".join(lines)


async def _aigohotel_search_segment(
    search_tool: Any,
    rep_name: str,
    city: str,
    accommodation: str,
    centroid: tuple,
    radius_km: float,
    star_ratings: list,
    check_in: Optional[str],
) -> List[Dict[str, Any]]:
    """对一个城市 Segment 调一次 AIGoHotel SearchHotels（景点级），返回已解析酒店列表。"""
    distance_m = int(max(radius_km + 2.0, 2.0) * 1000)
    distance_m = min(distance_m, 20000)
    args: Dict[str, Any] = {
        "place": rep_name,
        "placeType": "景点",
        "originQuery": f"搜索{city}{rep_name}附近的{accommodation or ''}酒店".strip(),
        "size": 8,
        "withHotelAmenities": True,
        "withRoomAmenities": True,
        "filterOptions": {"distanceInMeter": distance_m},
    }
    if star_ratings:
        args["filterOptions"]["starRatings"] = star_ratings
    if check_in:
        args["checkInParam"] = {"checkInDate": check_in, "stayNights": 1}

    try:
        raw = await _invoke_tool_with_retry(search_tool, args, max_retries=1, per_attempt_timeout=30.0)
    except Exception as e:
        print(f"  ⚠️ AIGoHotel 景点搜索失败 [{rep_name}]: {str(e)[:120]}")
        return []

    hotels = _parse_aigohotel_hotels(raw)
    _enrich_hotels_with_distance(hotels, centroid)
    return hotels


async def _aigohotel_city_fallback(
    search_tool: Any,
    city: str,
    accommodation: str,
    star_ratings: list,
    check_in: Optional[str],
    stay_nights: int,
) -> List[Dict[str, Any]]:
    """城市级兜底搜索，用于 Segment 无坐标或景点搜索失败时。"""
    args: Dict[str, Any] = {
        "place": city,
        "placeType": "城市",
        "originQuery": f"搜索{city}{accommodation or ''}酒店".strip(),
        "size": 8,
        "withHotelAmenities": True,
        "withRoomAmenities": True,
    }
    if star_ratings:
        args["filterOptions"] = {"starRatings": star_ratings}
    if check_in:
        args["checkInParam"] = {"checkInDate": check_in, "stayNights": stay_nights}

    try:
        raw = await _invoke_tool_with_retry(search_tool, args, max_retries=2, per_attempt_timeout=30.0)
    except Exception as e:
        print(f"  ⚠️ AIGoHotel 城市级兜底失败 [{city}]: {str(e)[:120]}")
        return []
    return _parse_aigohotel_hotels(raw)


def _day_city_list(request) -> List[str]:
    """把多城市行程展开成 day -> city 列表；单城市时所有天同城。"""
    cities = getattr(request, "cities", None) or []
    travel_days = request.travel_days
    if not cities:
        return [request.city] * travel_days
    out: List[str] = []
    for cs in cities:
        out.extend([cs.city] * max(cs.days, 0))
    if len(out) < travel_days:
        out.extend([cities[-1].city] * (travel_days - len(out)))
    return out[:travel_days]


async def search_hotels_by_day_node(state: TripPlannerState) -> Dict[str, Any]:
    """按连续城市 Segment 搜索行程区域酒店，写入 hotels_by_day + hotels_info。

    多城市升级点（相对"整趟旅程只搜一次"）：
    - 北京 Day1-Day2 → 北京景点质心 → 北京酒店候选 A
    - 西安 Day3-Day5 → 西安景点质心 → 西安酒店候选 B
    每个 Segment 内：质心 + 覆盖半径 → 景点级搜索 → 城市级兜底。
    """
    print("🏨 执行节点: search_hotels_by_day_node (按城市 Segment)")
    request = state["request"]
    clusters: List[List[Dict[str, Any]]] = state.get("clusters_data") or []
    travel_days = request.travel_days

    from ....services.aigohotel_mcp_service import get_aigohotel_service
    aigohotel_service = get_aigohotel_service()
    if not aigohotel_service:
        return {
            "hotels_info": "",
            "hotels_by_day": [[] for _ in range(travel_days)],
            "errors": ["search_hotels_by_day: AIGoHotel 服务未配置"],
        }

    try:
        await aigohotel_service.get_tools()
        search_tool = await aigohotel_service.get_tool("SearchHotels")
        if not search_tool:
            search_tool = await aigohotel_service.get_tool("find-hotels")
        if not search_tool:
            return {
                "hotels_info": "",
                "hotels_by_day": [[] for _ in range(travel_days)],
                "errors": ["search_hotels_by_day: SearchHotels 工具不可用"],
            }
    except Exception as e:
        return {
            "hotels_info": "",
            "hotels_by_day": [[] for _ in range(travel_days)],
            "errors": [f"search_hotels_by_day: AIGoHotel 初始化失败 - {str(e)[:200]}"],
        }

    accommodation = request.accommodation or ""
    star_ratings = _accommodation_to_star_ratings(accommodation)

    while len(clusters) < travel_days:
        clusters.append([])

    day_city = _day_city_list(request)

    # 按连续相同城市切 Segment
    segments: List[Dict[str, Any]] = []  # [{city, days: [day_idx,...]}]
    for idx, city in enumerate(day_city):
        if segments and segments[-1]["city"] == city:
            segments[-1]["days"].append(idx)
        else:
            segments.append({"city": city, "days": [idx]})

    hotels_by_day: List[List[Dict[str, Any]]] = [[] for _ in range(travel_days)]
    info_blocks: List[str] = []

    for seg in segments:
        city = seg["city"]
        seg_days = seg["days"]
        seg_attrs: List[Dict[str, Any]] = []
        for d in seg_days:
            seg_attrs.extend(clusters[d] if d < len(clusters) else [])

        centroid = _hotels_cluster_centroid(seg_attrs) if seg_attrs else None
        ranked: List[Dict[str, Any]] = []

        if centroid and seg_attrs:
            from ..utils.geo import _haversine_distance
            best_poi = min(
                seg_attrs,
                key=lambda p: _haversine_distance(centroid[1], centroid[0], p.get("latitude", 0), p.get("longitude", 0)) if isinstance(p.get("longitude"), (int, float)) else 999,
            )
            rep_name = best_poi.get("name", city)

            max_radius_km = _cluster_outer_radius_km(seg_attrs, centroid)
            distance_m = int(max(max_radius_km + 2.0, 3.0) * 1000)
            distance_m = min(distance_m, 20000)

            print(f" 🔎 [{city}] 行程质心: ({centroid[0]:.4f}, {centroid[1]:.4f}), 锚点景点: '{rep_name}', 搜索半径: {distance_m}m")

            hotels = await _aigohotel_search_segment(
                search_tool, rep_name, city, accommodation,
                centroid, max_radius_km, star_ratings,
                request.start_date,
            )
            if hotels:
                _enrich_hotels_with_distance(hotels, centroid)
                ranked = _rank_day_hotels(hotels, top_n=5)

        if not ranked:
            print(f" ⚠️ [{city}] 景点级搜索无结果，使用城市级兜底")
            city_hotels = await _aigohotel_city_fallback(
                search_tool, city, accommodation, star_ratings,
                request.start_date, max(len(seg_days), 1),
            )
            if city_hotels and centroid:
                _enrich_hotels_with_distance(city_hotels, centroid)
            ranked = _rank_day_hotels(city_hotels, top_n=5) if city_hotels else []

        for d in seg_days:
            hotels_by_day[d] = list(ranked)

        if len(segments) > 1 or len(seg_days) < travel_days:
            header = f"=== {city} 第{seg_days[0] + 1}-{seg_days[-1] + 1}天候选酒店 ==="
            lines = [header]
            for j, h in enumerate(ranked, 1):
                star = h.get("star_rating")
                price = h.get("price")
                dist = h.get("distance") or ""
                parts = [f"  {j}. {h['name']}"]
                if star is not None:
                    parts.append(f"{star}星")
                if price is not None:
                    parts.append(f"¥{int(price)}")
                if dist:
                    parts.append(dist)
                if h.get("address"):
                    parts.append(h["address"])
                lines.append(" | ".join(parts))
            info_blocks.append("\n".join(lines))
        else:
            info_blocks.append(_format_hotels_by_day_text(hotels_by_day))

        print(f" ✅ [{city}] Segment 完成: {len(ranked)} 家候选, 分配给 {len(seg_days)} 天")

    hotels_info = "\n".join(b for b in info_blocks if b)
    print(f"✅ 按城市 Segment 酒店搜索完成: {len(segments)} 个 Segment")

    return {
        "hotels_info": hotels_info,
        "hotels_by_day": hotels_by_day,
        "aigohotel_raw_results": hotels_info,
    }

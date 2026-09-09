from typing import Dict, Any, List, Optional

import asyncio

from langchain_core.messages import SystemMessage, HumanMessage

from ..exceptions import _invoke_tool_with_retry, _invoke_llm_with_retry
from ..prompts import FOOD_AGENT_PROMPT
from ..state import TripPlannerState, DayPlanLocalState
from ....services.langchain_amap_tools import get_langchain_amap_service
from ....services.llm_service import get_llm
from ....services.preferences_service import format_preference_hint
from ....models.schemas import DiningCategory


CITY_FOOD_MAP = {
    "北京": {"cuisine": "京菜", "keywords": ["烤鸭", "涮羊肉", "炸酱面", "京菜"]},
    "上海": {"cuisine": "本帮菜", "keywords": ["本帮菜", "小笼包", "生煎", "上海菜"]},
    "成都": {"cuisine": "川菜", "keywords": ["火锅", "川菜", "串串", "担担面"]},
    "重庆": {"cuisine": "渝菜", "keywords": ["火锅", "小面", "渝菜", "酸辣粉"]},
    "广州": {"cuisine": "粤菜", "keywords": ["早茶", "粤菜", "煲仔饭", "肠粉"]},
    "深圳": {"cuisine": "粤菜", "keywords": ["粤菜", "潮汕菜", "海鲜", "早茶"]},
    "西安": {"cuisine": "陕菜", "keywords": ["肉夹馍", "羊肉泡馍", "凉皮", "陕菜"]},
    "杭州": {"cuisine": "杭帮菜", "keywords": ["杭帮菜", "西湖醋鱼", "龙井虾仁", "东坡肉"]},
    "南京": {"cuisine": "金陵菜", "keywords": ["盐水鸭", "鸭血粉丝", "金陵菜", "小笼包"]},
    "长沙": {"cuisine": "湘菜", "keywords": ["臭豆腐", "湘菜", "剁椒鱼头", "茶颜悦色"]},
    "武汉": {"cuisine": "鄂菜", "keywords": ["热干面", "豆皮", "鄂菜", "武昌鱼"]},
    "厦门": {"cuisine": "闽南菜", "keywords": ["沙茶面", "海蛎煎", "闽南菜", "海鲜"]},
    "昆明": {"cuisine": "滇菜", "keywords": ["过桥米线", "滇菜", "汽锅鸡", "鲜花饼"]},
    "大理": {"cuisine": "滇菜", "keywords": ["白族菜", "饵丝", "滇菜", "酸辣鱼"]},
    "丽江": {"cuisine": "滇菜", "keywords": ["纳西菜", "滇菜", "腊排骨", "鸡豆凉粉"]},
    "苏州": {"cuisine": "苏帮菜", "keywords": ["苏帮菜", "松鼠桂鱼", "阳春面", "苏式汤面"]},
    "天津": {"cuisine": "津菜", "keywords": ["狗不理", "煎饼果子", "津菜", "麻花"]},
    "青岛": {"cuisine": "鲁菜", "keywords": ["海鲜", "啤酒", "鲁菜", "烧烤"]},
    "哈尔滨": {"cuisine": "东北菜", "keywords": ["锅包肉", "东北菜", "红肠", "杀猪菜"]},
    "拉萨": {"cuisine": "藏餐", "keywords": ["酥油茶", "藏餐", "糌粑", "牦牛肉"]},
    "乌鲁木齐": {"cuisine": "新疆菜", "keywords": ["大盘鸡", "烤羊肉", "新疆菜", "手抓饭"]},
}


def _get_food_keywords(city: str, food_preference: str) -> list:
    city_info = CITY_FOOD_MAP.get(city, {"cuisine": "本地菜", "keywords": ["特色菜", "美食"]})
    if food_preference == "本地特色" or food_preference == "无特殊要求":
        return city_info["keywords"][:2]
    preference_keywords = {
        "川菜": ["川菜", "火锅", "麻辣"],
        "粤菜": ["粤菜", "早茶", "海鲜"],
        "日料": ["日料", "寿司", "拉面"],
        "西餐": ["西餐", "牛排", "意面"],
        "小吃": ["小吃", "特色小吃", "路边摊"],
        "火锅": ["火锅", "涮锅"],
        "烧烤": ["烧烤", "烤肉"],
        "海鲜": ["海鲜", "大排档"],
    }
    return preference_keywords.get(food_preference, [food_preference])


async def search_food_node(state: TripPlannerState) -> Dict[str, Any]:
    print("🍜 执行节点: search_food_node")
    request = state["request"]
    attractions_info = state.get("attractions_info", "")

    service = get_langchain_amap_service()
    around_tool = await service.get_tool("maps_around_search")
    search_tool = await service.get_tool("maps_text_search")
    llm = get_llm()
    llm_with_tools = llm.bind_tools([around_tool, search_tool])

    food_keywords = _get_food_keywords(request.city, request.food_preference)
    city_info = CITY_FOOD_MAP.get(request.city, {"cuisine": "本地菜"})

    preferences = state.get("user_preferences")
    pref_hint = ""
    if preferences:
        pref_hint = "\n\n" + format_preference_hint(preferences)

    prompt = FOOD_AGENT_PROMPT + f"""
请搜索城市: {request.city} 的餐厅信息。

**用户美食偏好:** {request.food_preference}
**城市特色菜系:** {city_info.get("cuisine", "本地菜")}
**推荐搜索关键词:** {', '.join(food_keywords)}

**景点信息（用于周边搜索）:**
{attractions_info[:2000]}

请执行以下搜索:
1. 使用 maps_around_search 搜索景点周边的餐厅（从景点信息中提取坐标）
2. 使用 maps_text_search 搜索城市热门餐厅（关键词: {food_keywords[0]})
""" + pref_hint
    response = await _invoke_llm_with_retry(llm_with_tools, [SystemMessage(content=FOOD_AGENT_PROMPT), HumanMessage(content=prompt)])

    food_results = []
    for tool_call in response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        tool = await service.get_tool(tool_name)
        if tool:
            tool_result = await _invoke_tool_with_retry(tool, tool_args)
            food_results.append(f"[{tool_name}]: {str(tool_result)}")

    if food_results:
        return {"food_info": "\n".join(food_results)}

    print("⚠️ search_food_node: LLM未调用工具，返回空数据")
    return {"food_info": ""}


def _find_coord_fuzzy(name: str, coords_list: List[Dict]) -> Optional[Dict]:
    for c in coords_list:
        if c["name"] == name:
            return c
    for c in coords_list:
        if name in c["name"] or c["name"] in name:
            return c
    suffixes = ["景区", "风景区", "风景名胜区", "公园", "博物馆", "博物院", "纪念馆", "遗址"]
    stripped = name
    for s in suffixes:
        stripped = stripped.replace(s, "")
    if stripped and stripped != name:
        for c in coords_list:
            c_stripped = c["name"]
            for s in suffixes:
                c_stripped = c_stripped.replace(s, "")
            if stripped in c_stripped or c_stripped in stripped:
                return c
    return None


async def day_food_search_node(state: DayPlanLocalState) -> Dict[str, Any]:
    """单日子图中为当天景点搜索周边餐厅，直接调用工具不经过 LLM"""
    from ..utils.geo import _extract_coordinates_regex

    day_index = state["day_index"]
    attraction_names = state["attraction_names"]
    city = state["city"]
    food_preference = state.get("food_preference", "本地特色")

    print(f"🍜 单日美食搜索: 第{day_index + 1}天, 景点: {attraction_names}")

    service = get_langchain_amap_service()
    around_tool = await service.get_tool("maps_around_search")
    search_tool = await service.get_tool("maps_text_search")

    food_keywords = _get_food_keywords(city, food_preference)
    attractions_info = state.get("attractions_info", "")
    all_coords = _extract_coordinates_regex(attractions_info)

    food_results = []

    searched_locations = set()
    for attr_name in attraction_names[:3]:
        coord = _find_coord_fuzzy(attr_name, all_coords)
        if not coord:
            continue
        location_str = f"{coord['longitude']},{coord['latitude']}"
        if location_str in searched_locations:
            continue
        searched_locations.add(location_str)

        for keyword in food_keywords[:2]:
            try:
                result = await _invoke_tool_with_retry(around_tool, {
                    "keywords": keyword,
                    "location": location_str,
                    "radius": "2000",
                })
                food_results.append(f"[maps_around_search {attr_name} {keyword}]: {str(result)}")
            except Exception as e:
                print(f"  ⚠️ 周边搜索失败 ({attr_name}, {keyword}): {str(e)[:80]}")

    city_info = CITY_FOOD_MAP.get(city, {"cuisine": "本地菜", "keywords": ["特色菜"]})
    try:
        dinner_keyword = f"{city}{city_info.get('cuisine', '美食')}"
        result = await _invoke_tool_with_retry(search_tool, {
            "keywords": dinner_keyword,
            "city": city,
        })
        food_results.append(f"[maps_text_search {dinner_keyword}]: {str(result)}")
    except Exception as e:
        print(f"  ⚠️ 城市美食搜索失败: {str(e)[:80]}")

    day_food_info = "\n".join(food_results) if food_results else ""
    print(f"  ✅ 第{day_index + 1}天美食搜索完成: {len(food_results)}条结果")
    return {"day_food_info": day_food_info}


# ============ 多类别餐饮候选池（骨架阶段） ============

def _parse_amap_poi_list(raw: Any) -> List[Dict[str, Any]]:
    """从高德工具返回中提取 POI 列表（含 id, location, biz_ext.rating 等）。"""
    import json as _json
    import ast
    data = raw
    for _ in range(3):
        if isinstance(data, str):
            try:
                data = _json.loads(data)
                continue
            except (_json.JSONDecodeError, TypeError):
                try:
                    data = ast.literal_eval(data)
                    continue
                except (ValueError, SyntaxError):
                    break
        if isinstance(data, list) and data and isinstance(data[0], dict) and "text" in data[0]:
            inner = data[0]["text"]
            if isinstance(inner, str):
                data = inner
                continue
        break

    pois = []
    if isinstance(data, dict):
        pois = data.get("pois") or []
        if not pois:
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    pois = v
                    break
    elif isinstance(data, list):
        pois = data

    result = []
    for p in pois or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        if not name:
            continue
        item: Dict[str, Any] = {"name": str(name)}
        poi_id = p.get("id") or p.get("poi_id")
        if poi_id:
            item["poi_id"] = str(poi_id)
        addr = p.get("address")
        if addr:
            item["address"] = str(addr)
        loc_str = p.get("location")
        if isinstance(loc_str, str) and "," in loc_str:
            parts = loc_str.split(",")
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                if 73 < lon < 136 and 3 < lat < 54:
                    item["longitude"] = lon
                    item["latitude"] = lat
            except (ValueError, IndexError):
                pass
        biz = p.get("biz_ext") or p.get("business") or {}
        if isinstance(biz, dict):
            rating = biz.get("rating") or biz.get("score")
            if rating:
                try:
                    item["rating"] = float(rating)
                except (TypeError, ValueError):
                    pass
            cost = biz.get("cost")
            if cost:
                try:
                    item["avg_cost"] = int(float(cost))
                except (TypeError, ValueError):
                    pass
            opentime = biz.get("opentime_today") or biz.get("opentime_week")
            if opentime:
                item["open_hours"] = str(opentime)
            tel = biz.get("tel") or p.get("tel")
            if tel:
                item["tel"] = str(tel)
        item["type"] = str(p.get("type") or "")
        result.append(item)
    return result


def _rank_food_pois(
    pois: List[Dict[str, Any]],
    center_lon: Optional[float],
    center_lat: Optional[float],
    used_names: set,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """按 (有评分, rating desc, 距离 asc) 排序，去重 used_names，取 top_n。"""
    from ..utils.geo import _haversine_distance

    scored = []
    for p in pois:
        name = p.get("name", "").strip()
        if not name or name in used_names:
            continue
        rating = p.get("rating")
        dist_km = 99.0
        if center_lon is not None and p.get("longitude") and p.get("latitude"):
            dist_km = _haversine_distance(center_lat, center_lon, p["latitude"], p["longitude"])
            p["_dist_km"] = dist_km
        scored.append((
            0 if rating is not None else 1,
            -(rating or 0.0),
            dist_km,
            p,
        ))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [s[3] for s in scored[:top_n]]


_DINING_KEYWORDS = {
    DiningCategory.MAIN: ("餐厅 美食", 6),
    DiningCategory.SNACK: ("小吃 街边小吃", 4),
    DiningCategory.DESSERT: ("甜品 蛋糕 茶饮", 4),
    DiningCategory.CAFE: ("咖啡馆", 4),
    DiningCategory.LATE_NIGHT: ("夜宵 烧烤 大排档", 4),
}


def _day_center(day_cluster: List[Dict[str, Any]]) -> Optional[tuple]:
    """计算当日景点经纬度算术平均；无有效坐标返回 None"""
    coords = [
        (c["longitude"], c["latitude"])
        for c in (day_cluster or [])
        if isinstance(c.get("longitude"), (int, float))
        and isinstance(c.get("latitude"), (int, float))
        and 73 < c["longitude"] < 136 and 3 < c["latitude"] < 54
    ]
    if not coords:
        return None
    return (
        sum(x for x, _ in coords) / len(coords),
        sum(y for _, y in coords) / len(coords),
    )


async def _search_dining_category(
    category: DiningCategory,
    center: Optional[tuple],
    city: str,
) -> List[Dict[str, Any]]:
    """跑一次 amap POI 搜索；center 为 None 时走城市文本搜索"""
    keyword, _top_n = _DINING_KEYWORDS[category]
    service = get_langchain_amap_service()

    if center is not None:
        tool = await service.get_tool("maps_around_search")
        if tool is None:
            return []
        try:
            raw = await _invoke_tool_with_retry(
                tool,
                {"keywords": keyword, "location": f"{center[0]},{center[1]}", "radius": "1500"},
                max_retries=1, per_attempt_timeout=15.0,
            )
        except Exception as e:
            print(f" ⚠️ dining[{category.value}] around 失败: {str(e)[:80]}")
            return []
    else:
        tool = await service.get_tool("maps_text_search")
        if tool is None:
            return []
        try:
            raw = await _invoke_tool_with_retry(
                tool, {"keywords": keyword, "city": city},
                max_retries=1, per_attempt_timeout=15.0,
            )
        except Exception as e:
            print(f" ⚠️ dining[{category.value}] text 失败: {str(e)[:80]}")
            return []

    return _parse_amap_poi_list(raw)


def _poi_to_dining_candidate(
    p: Dict[str, Any], category: DiningCategory, source: str
) -> Dict[str, Any]:
    """把 _parse_amap_poi_list 的 POI dict 转成 DiningCandidate dict"""
    cand: Dict[str, Any] = {
        "name": p.get("name", ""),
        "category": category.value,
        "source": source,
    }
    if p.get("address"):
        cand["address"] = p["address"]
    if p.get("longitude") and p.get("latitude"):
        cand["location"] = {"longitude": p["longitude"], "latitude": p["latitude"]}
    if p.get("rating") is not None:
        cand["rating"] = round(float(p["rating"]), 2)
    if p.get("avg_cost") is not None:
        cand["avg_cost"] = int(p["avg_cost"])
    if p.get("open_hours"):
        cand["open_hours"] = p["open_hours"]
    if p.get("tel"):
        cand["tel"] = p["tel"]
    if p.get("poi_id"):
        cand["poi_id"] = p["poi_id"]
    cuisine_tag = (p.get("type") or "").split(";")[0].strip()
    if cuisine_tag:
        cand["cuisine"] = cuisine_tag
    return cand


async def search_dining_pool_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """骨架阶段：按 5 类并发搜索每日餐饮候选池，返回 List[DiningPoolDay-shape dict]

    Agent 不再直接决定"午饭去某餐厅"，而是先给用户每类候选，
    之后由 AI/用户在草稿页组合 —— 候选空间来自真实工具，避免模型编造餐厅。
    """
    print("🍴 执行节点: search_dining_pool_node")
    request = state["request"]
    clusters_data: List[List[Dict[str, Any]]] = state.get("clusters_data", []) or []
    travel_days = request.travel_days

    while len(clusters_data) < travel_days:
        clusters_data.append([])

    pools: List[Dict[str, Any]] = []
    for day_idx in range(travel_days):
        day_cluster = clusters_data[day_idx] if day_idx < len(clusters_data) else []
        center = _day_center(day_cluster)
        source = "nearby" if center is not None else "popular"

        tasks = [
            _search_dining_category(cat, center, request.city)
            for cat in DiningCategory
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        pool: Dict[str, List[Dict[str, Any]]] = {}
        for cat, res in zip(DiningCategory, results):
            if isinstance(res, Exception):
                print(f" ⚠️ dining[{cat.value}] 异常: {res}")
                pool[cat.value] = []
                continue
            _, top_n = _DINING_KEYWORDS[cat]
            ranked = _rank_food_pois(res, None, None, set(), top_n=top_n)
            pool[cat.value] = [
                _poi_to_dining_candidate(p, cat, source) for p in ranked
            ]
        pools.append(pool)
        total = sum(len(v) for v in pool.values())
        print(f" ✅ 第{day_idx + 1}天餐饮候选池: 共 {total} 家")

    return {"dining_pool": pools}

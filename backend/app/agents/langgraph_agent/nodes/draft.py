"""草稿写入节点（骨架图的最后一站）"""
import json
import re
from typing import Dict, Any, List, Optional

from ..state import TripPlannerState
from ....services import trip_draft_service
from ....models.schemas import WeatherInfo


def _coerce_json_list(text: str) -> Optional[List[Any]]:
    """从 LLM 工具原始文本中尽力提取 JSON 列表（兼容外层包装/前后杂文本）"""
    if not text or not text.strip():
        return None
    candidates = [text.strip()]
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    m2 = re.search(r"\{.*\}", text, re.DOTALL)
    if m2:
        candidates.append(m2.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
            inner = data.get("text")
            if isinstance(inner, str):
                inner_list = _coerce_json_list(inner)
                if inner_list is not None:
                    return inner_list
    return None


def _weather_field(d: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return ""


def _normalize_weather_info(raw: Any, travel_days: int) -> List[Dict[str, Any]]:
    """把天气节点输出（字符串/列表/None）规范化为 List[WeatherInfo dict]

    amap 天气工具的预报字段为 dayweather/nightweather/daytemp/nighttemp/
    daywind/daypower 等别名，这里统一映射到 WeatherInfo 字段。
    """
    items: List[Any] = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        parsed = _coerce_json_list(raw)
        items = parsed or []

    result: List[Dict[str, Any]] = []
    for w in items:
        if isinstance(w, WeatherInfo):
            result.append(w.model_dump(mode="json"))
            continue
        if not isinstance(w, dict) or not w.get("date"):
            continue
        result.append({
            "date": str(w["date"])[:10],
            "city": str(_weather_field(w, "city") or ""),
            "day_weather": str(_weather_field(w, "day_weather", "dayweather", "weather") or ""),
            "night_weather": str(_weather_field(w, "night_weather", "nightweather") or ""),
            "day_temp": _weather_field(w, "day_temp", "daytemp") or 0,
            "night_temp": _weather_field(w, "night_temp", "nighttemp") or 0,
            "wind_direction": str(_weather_field(w, "wind_direction", "daywind", "wind") or ""),
            "wind_power": str(_weather_field(w, "wind_power", "daypower", "power") or ""),
        })

    if len(result) > travel_days:
        result = result[:travel_days]
    return result


async def save_draft_node(state: TripPlannerState) -> Dict[str, Any]:
    print("💾 执行节点: save_draft_node")
    request = state["request"]
    user_id = state.get("user_id", "default")
    macro_plan = state.get("macro_plan")
    if macro_plan is None:
        raise RuntimeError("save_draft_node: macro_plan 缺失，无法保存草稿")

    weather_list = _normalize_weather_info(
        state.get("weather_info", ""), request.travel_days
    )
    if weather_list:
        print(f"✅ 天气信息已规范化: {len(weather_list)} 天")

    draft_id = await trip_draft_service.create_draft(
        user_id=user_id,
        request=request,
        selected_attractions=state.get("user_selected_attractions", []) or [],
        macro_plan=macro_plan,
        clusters_data=state.get("clusters_data", []) or [],
        hotels_by_day=state.get("hotels_by_day", []) or [],
        dining_pool=state.get("dining_pool", []) or [],
        weather_info=weather_list,
    )
    print(f"✅ 草稿已保存: draft_id={draft_id}")
    return {"draft_id": draft_id}

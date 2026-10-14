from typing import Dict, Any
from datetime import datetime

from langchain_core.messages import SystemMessage

from ..state import TripPlannerState
from ....services.preferences_service import (
    load_preferences,
    save_preferences,
    merge_preferences,
    format_preference_hint,
)
from ....models.schemas import UserPreference


async def load_user_preferences_node(state: TripPlannerState) -> Dict[str, Any]:
    print("📋 执行节点: load_user_preferences_node")
    user_id = state.get("user_id", "default")

    preferences = await load_preferences(user_id)

    if preferences:
        print(f"  ✅ 已加载用户偏好: 酒店={preferences.preferred_hotel_types}, "
              f"美食={preferences.preferred_cuisines}, "
              f"历史出行{preferences.total_trips}次")
        preference_hint = format_preference_hint(preferences)
        return {
            "messages": [SystemMessage(content=preference_hint)],
            "user_preferences": preferences,
        }

    print("  [INFO]️ 无历史偏好数据，将使用默认策略")
    return {"user_preferences": None}


async def extract_preferences_node(state: TripPlannerState) -> Dict[str, Any]:
    print("📊 执行节点: extract_preferences_node")
    # Learn only explicit request fields, never preferences invented by generated plans.
    request = state.get("request")
    if not request:
        return {"extracted_preferences": None}
    preferences = {}
    if request.preferences:
        preferences["preferred_attraction_categories"] = request.preferences
    if request.food_preference and request.food_preference != "本地特色":
        preferences["preferred_cuisines"] = [request.food_preference]
    return {"extracted_preferences": preferences or None}


async def save_preferences_node(state: TripPlannerState) -> Dict[str, Any]:
    print("💾 执行节点: save_preferences_node")
    extracted = state.get("extracted_preferences")
    if not extracted:
        print("  [INFO]️ 无偏好数据需要保存")
        return {}

    user_id = state.get("user_id", "default")
    existing = await load_preferences(user_id)

    if existing:
        merged = merge_preferences(existing, extracted)
    else:
        merged = UserPreference(user_id=user_id, **extracted)

    request = state.get("request")
    merged.total_trips += 1
    if request and request.city not in merged.cities_visited:
        merged.cities_visited.append(request.city)
    merged.last_updated = datetime.utcnow().isoformat()

    await save_preferences(user_id, merged, source="explicit", confidence=1.0)
    print(f"  ✅ 已保存用户偏好 (累计{merged.total_trips}次出行)")

    return {}

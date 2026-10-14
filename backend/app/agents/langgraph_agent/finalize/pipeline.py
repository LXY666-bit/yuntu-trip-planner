"""定稿流水线：草稿 → 规则校验 → 全局综合 → 原子保存 trip_history。"""
import json
import re
from typing import Tuple, Optional

from ....models.schemas import (
    TripRequest, MacroPlan, TripPlan, DayPlan, DayDetail, DraftDayContext,
    DiningPoolDay, Attraction, Hotel, Budget, WeatherInfo, Location,
)
from ....services import trip_draft_service
from ....services.trip_history_service import save_trip
from ....database import async_session
from ....models.db_models import TripDraft
from sqlalchemy import update
from datetime import datetime
from ....services.plan_validation import city_for_day, priced_days, validate_plan
from ..assemble.timeline import rule_assemble_day_timeline
from ..assemble.route import compute_day_route
from ..assemble.budget import compute_day_budget
from ....models.reservation import reservation_fields


async def _run_global_synthesizer(trip_plan: TripPlan, free_text: str) -> Tuple[str, str, str]:
    """复用旧 global_synthesizer_node 的核心 LLM 调用，返回 (tagline, suggestions, summary)"""
    from ..nodes.generate import global_synthesizer_node, _generate_weather_summary_fallback
    state = {
        "trip_plan": trip_plan,
        "request": _make_pseudo_request(trip_plan, free_text),
        "weather_info": "",
    }
    try:
        result = await global_synthesizer_node(state)
        plan = result.get("trip_plan") or trip_plan
        return plan.trip_tagline, plan.overall_suggestions, plan.weather_summary
    except Exception as e:
        print(f"⚠️ global_synthesizer 失败，使用兜底: {e}")
        return "", "", _generate_weather_summary_fallback(trip_plan)


def _parse_ticket_price(val) -> int:
    """把发现页门票字段转成 int 元。

    "60"->60, "免费"->0, "￥80起"->80, None/""/无数字 ->0, 数字原样取整。
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else 0


def _make_pseudo_request(plan: TripPlan, free_text: str):
    return TripRequest(
        city=plan.city,
        start_date=plan.start_date,
        end_date=plan.end_date,
        travel_days=len(plan.days),
        transportation="公共交通",
        accommodation="经济型酒店",
        free_text_input=free_text,
    )


async def _run_extract_and_save_preferences(trip_plan: TripPlan, user_id: str) -> None:
    """复用旧 extract_preferences_node + save_preferences_node"""
    from ..nodes.preferences import extract_preferences_node, save_preferences_node
    state = {"trip_plan": trip_plan, "user_id": user_id, "extracted_preferences": None}
    state.update(await extract_preferences_node(state))
    await save_preferences_node(state)


def _day_detail_to_day_plan(detail: DayDetail, transportation: str, accommodation: str) -> DayPlan:
    return DayPlan(
        date=detail.date,
        city=detail.city,
        day_index=detail.day_index,
        description=detail.description,
        transportation=transportation,
        accommodation=accommodation,
        hotel=detail.hotel,
        attractions=detail.attractions,
        meals=detail.meals,
        route_segments=detail.route_segments,
        timeline_order=detail.timeline_order,
        day_start_time=detail.day_start_time,
    )


def _build_day_context(
    day_idx: int,
    macro_plan: MacroPlan,
    clusters_data: list,
    hotels_by_day: list,
    dining_pool: list,
    weather_info: list,
    default_day_start_time: str,
) -> DraftDayContext:
    day_skeleton = macro_plan.days[day_idx]
    cluster = clusters_data[day_idx] if day_idx < len(clusters_data) else []
    attractions = []
    for c in cluster:
        loc = c.get("location")
        if c.get("longitude") is not None and c.get("latitude") is not None:
            loc = Location(longitude=c["longitude"], latitude=c["latitude"])
        attractions.append(Attraction(
            **reservation_fields(c),
            name=c["name"],
            address=c.get("address") or "",
            visit_duration=c.get("visit_minutes") or c.get("visit_duration") or 120,
            description=c.get("description") or "",
            category=c.get("category") or "景点",
            rating=c.get("rating"),
            ticket_price=_parse_ticket_price(c.get("ticket_price")),
            price_status=c.get("price_status") or ("estimated" if re.search(r"\d", str(c.get("ticket_price"))) or c.get("ticket_price") == "免费" else "unknown"),
            source=c.get("source") or ("amap" if c.get("poi_id") else None),
            fetched_at=c.get("fetched_at"),
            indoor=c.get("indoor"),
            image_url=c.get("image_url"),
            poi_id=c.get("poi_id") or "",
            open_hours=c.get("open_hours"),
            tel=c.get("tel"),
            location=loc,
        ))
    hotel: Optional[Hotel] = None
    if day_idx < len(hotels_by_day) and hotels_by_day[day_idx]:
        h = hotels_by_day[day_idx][0]
        hotel_kwargs = {k: h[k] for k in h.keys() if k in Hotel.model_fields}
        if h.get("location") and isinstance(h["location"], dict):
            hotel_kwargs["location"] = Location(**h["location"])
        hotel = Hotel(**hotel_kwargs)

    pool = DiningPoolDay()
    if day_idx < len(dining_pool):
        pool = DiningPoolDay.model_validate(dining_pool[day_idx])

    weather_obj = None
    if day_idx < len(weather_info):
        w = weather_info[day_idx]
        if isinstance(w, dict):
            weather_obj = WeatherInfo.model_validate(w)

    return DraftDayContext(
        day_index=day_idx,
        date=day_skeleton.date,
        attraction_names=day_skeleton.attraction_names,
        attractions=attractions,
        hotel=hotel,
        dining_pool=pool,
        weather=weather_obj,
        day_start_time=default_day_start_time,
    )


async def finalize_draft(draft_id: str, *, user_id: str) -> Tuple[TripPlan, int]:
    record = await trip_draft_service.get_draft(draft_id)
    if record is None:
        raise ValueError(f"draft {draft_id} 不存在")
    if record.status == "finalized":
        raise ValueError(f"draft {draft_id} 已 finalized")

    request = TripRequest.model_validate_json(record.request_json)
    macro_plan = MacroPlan.model_validate_json(record.macro_plan_json)
    clusters_data = json.loads(record.clusters_data_json)
    hotels_by_day = json.loads(record.hotels_by_day_json)
    dining_pool = json.loads(record.dining_pool_json)
    weather_info = json.loads(record.weather_info_json)
    days_detail_raw = json.loads(record.days_detail_json)

    day_plans = []
    validation_days = []
    total_budget = Budget()
    for idx in range(request.travel_days):
        existing = days_detail_raw[idx] if idx < len(days_detail_raw) else None
        if existing is not None:
            detail = DayDetail.model_validate(existing)
            if not detail.route_segments:
                detail.route_segments = await compute_day_route(
                    detail, city_for_day(request, idx), request.transportation
                )
            if detail.day_budget is None:
                detail.day_budget = compute_day_budget(detail)
        else:
            ctx = _build_day_context(
                idx, macro_plan, clusters_data, hotels_by_day, dining_pool,
                weather_info, request.default_day_start_time,
            )
            detail = rule_assemble_day_timeline(ctx, overrides=None)
            detail.route_segments = await compute_day_route(
                detail, city_for_day(request, idx), request.transportation
            )
            detail.day_budget = compute_day_budget(detail)

        day_plans.append(_day_detail_to_day_plan(
            detail, request.transportation, request.accommodation
        ))
        detail.city = city_for_day(request, idx)
        day_plans[-1].city = detail.city
        detail.day_budget = priced_days([detail], request)[0].day_budget
        validation_days.append(detail)
        b = detail.day_budget
        total_budget = Budget(
            total_attractions=total_budget.total_attractions + b.total_attractions,
            total_hotels=total_budget.total_hotels + b.total_hotels,
            total_meals=total_budget.total_meals + b.total_meals,
            total_transportation=total_budget.total_transportation + b.total_transportation,
            total=total_budget.total + b.total,
            unknown_items=total_budget.unknown_items + b.unknown_items,
            notes=b.notes,
            pricing_status="incomplete" if total_budget.unknown_items or b.unknown_items else "estimated",
            budget_limit=request.budget,
        )

    weather_list = [WeatherInfo.model_validate(w) for w in weather_info if isinstance(w, dict)]

    trip_plan = TripPlan(
        city=request.city,
        cities=[c.city for c in request.cities],
        start_date=request.start_date,
        end_date=request.end_date,
        days=day_plans,
        weather_info=weather_list,
        overall_suggestions="",
        budget=total_budget,
        companions=request.companions,
    )

    report = validate_plan(request, validation_days)
    if not report.valid:
        raise ValueError("行程存在冲突，请先校验修复：" + "；".join(v.message for v in report.violations if v.severity == "error"))
    trip_plan.budget.is_within_budget = (report.total_cost <= request.budget) if request.budget is not None and report.pricing_status != "incomplete" else None
    tagline, suggestions, summary = await _run_global_synthesizer(
        trip_plan, request.free_text_input or ""
    )
    trip_plan.trip_tagline = tagline
    trip_plan.overall_suggestions = suggestions
    trip_plan.weather_summary = summary

    # Claim and persist in one transaction. Concurrent finalizers cannot create two trips.
    async with async_session() as session:
        result = await session.execute(update(TripDraft).where(
            TripDraft.id == draft_id, TripDraft.status != "finalized",
            TripDraft.days_detail_json == record.days_detail_json,
            TripDraft.request_json == record.request_json,
        ).values(status="finalized"))
        if result.rowcount != 1:
            raise ValueError("草稿已变化或已 finalized，请刷新后重试")
        trip_record = await save_trip(trip_plan, request=request, session=session)
        await session.execute(update(TripDraft).where(TripDraft.id == draft_id).values(
            finalized_trip_id=trip_record.id, finalized_at=datetime.utcnow(),
            trip_tagline=tagline, overall_suggestions=suggestions, weather_summary=summary,
        ))
        await session.commit()

    return trip_plan, trip_record.id

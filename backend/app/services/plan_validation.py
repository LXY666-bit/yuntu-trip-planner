"""Deterministic itinerary checks. Unknown evidence remains a warning, never a fact."""
import math
import re
from datetime import date, timedelta
from ..models.schemas import TripRequest, DayDetail
from ..models.planning import Violation, ValidationReport
from ..agents.langgraph_agent.assemble.budget import compute_day_budget


def minutes(text: str | None) -> int | None:
    if not text:
        return None
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text.strip())
    return int(match[1]) * 60 + int(match[2]) if match else None


def duration_minutes(text: str) -> int | None:
    hours = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|hours?|h)", text, re.I)
    mins = re.search(r"(\d+(?:\.\d+)?)\s*(?:分钟|分|minutes?|mins?)", text, re.I)
    if not hours and not mins:
        return None
    return math.ceil((float(hours[1]) * 60 if hours else 0) + (float(mins[1]) if mins else 0))


def opening_windows(text: str | None, visit_date: str) -> list[tuple[int, int]] | None:
    """Only accept simple time windows; seasonal/holiday conditions need confirmation."""
    if not text:
        return None
    weekday = date.fromisoformat(visit_date).weekday()
    day_label = "[日天]" if weekday == 6 else "一二三四五六"[weekday]
    if re.search(rf"(?:周|星期){day_label}.{{0,3}}(?:闭馆|休息|不开放)", text):
        return []
    if any(x in text for x in ("节假日", "旺季", "淡季", "预约", "另行", "周", "星期")):
        return None
    if any(x in text for x in ("全天", "24小时")):
        return [(0, 1440)]
    pairs = re.findall(r"(\d{1,2}:\d{2})\s*[-—–~至]\s*(\d{1,2}:\d{2})", text)
    windows = []
    for start, end in pairs:
        a, b = minutes(start), minutes(end)
        if a is None or b is None or b <= a:
            return None
        windows.append((a, b))
    return windows or None


def city_for_day(request: TripRequest, index: int) -> str:
    cities = [stay.city for stay in request.cities for _ in range(stay.days)]
    return cities[index] if index < len(cities) else request.city


def priced_days(days: list[DayDetail], request: TripRequest) -> list[DayDetail]:
    result = []
    people = request.companions.count if request.companions else 1
    for day in days:
        copy = day.model_copy(deep=True)
        copy.day_budget = compute_day_budget(
            copy, people=people, rooms=math.ceil(people / 2),
            include_hotel=copy.day_index < request.travel_days - 1,
        )
        result.append(copy)
    return result


def validate_plan(request: TripRequest, days: list[DayDetail]) -> ValidationReport:
    issues: list[Violation] = []
    def add(code, message, day=None, subject=None, severity="error"):
        issues.append(Violation(code=code, severity=severity, message=message,
                                day_index=day, subject=subject))

    indexed = {d.day_index: d for d in days}
    if len(indexed) != len(days):
        add("duplicate_day", "存在重复的行程日期索引")
    expected_start = date.fromisoformat(request.start_date)
    for i in range(request.travel_days):
        if i not in indexed:
            add("missing_day", f"缺少第 {i + 1} 天", i)
        elif indexed[i].date != (expected_start + timedelta(days=i)).isoformat():
            add("date_mismatch", f"第 {i + 1} 天日期与请求不一致", i)
    if any(i < 0 or i >= request.travel_days for i in indexed):
        add("unexpected_day", "包含请求范围以外的日期")

    names = {a.name for d in days for a in d.attractions}
    all_names = [a.name for d in days for a in d.attractions]
    if len(all_names) != len(set(all_names)):
        add("repeated_visit", "不同日期出现重复景点，请确认是否有意重复游览", severity="warning")
    for name in request.must_visit:
        if name not in names:
            add("missing_must_visit", f"必去景点“{name}”尚未安排", subject=name)

    elapsed_by_day = {}
    verified = 0
    attraction_count = 0
    for day in days:
        i = day.day_index
        start = minutes(day.day_start_time or request.default_day_start_time)
        if start is None:
            add("invalid_start_time", "开始时间格式不正确", i)
            start = 480
        clock = start
        by_name = {a.name: a for a in day.attractions}
        meals = {m.name: m for m in day.meals}
        if len(by_name) != len(day.attractions):
            add("duplicate_attraction", "同一天安排了重复景点", i)
        if not day.attractions:
            add("empty_day", "当天没有安排景点", i, severity="warning")
        for a in day.attractions:
            if a.reservation.status == 'conflicting':
                add('reservation_conflicting', f'{a.name} 预约规则有冲突，请核实来源', i, a.name, 'warning')
            elif a.reservation.status == 'required' and a.reservation_booked_for != date.fromisoformat(day.date):
                add('reservation_pending', f'{a.name} 需要关注预约，尚未确认该日期已预约', i, a.name, 'warning')
            attraction_count += 1
            valid_location = a.location and -180 <= a.location.longitude <= 180 and -90 <= a.location.latitude <= 90
            verified += bool(a.poi_id and valid_location)
            if not a.poi_id or not valid_location:
                add("unverified_poi", f"{a.name} 缺少可核验的 POI 标识或坐标", i, a.name, "warning")
        route_map = {(r.from_name, r.to_name): r for r in day.route_segments}
        timeline = day.timeline_order or [{"kind": "attraction", "ref_name": a.name} for a in day.attractions]
        visits = [x.get("ref_name") for x in timeline if x.get("kind") == "attraction"]
        if sorted(visits) != sorted(by_name):
            add("timeline_mismatch", "时间轴与景点列表不一致", i)
        previous = None
        for item in timeline:
            name, kind = item.get("ref_name", ""), item.get("kind")
            if previous and previous != name:
                route = route_map.get((previous, name))
                duration = duration_minutes(route.duration) if route else None
                if route and any(word in route.detail for word in ("估算", "降级", "直线")):
                    add("estimated_route_time", f"{previous} → {name} 使用估算路线，需核实", i, name, "warning")
                if duration is None:
                    duration = 30
                    add("unknown_route_time", f"{previous} → {name} 缺少有效路线耗时，暂按 30 分钟估算", i, name, "warning")
                clock += duration
            if kind == "attraction" and name in by_name:
                attraction = by_name[name]
                length = attraction.visit_duration
                if length <= 0:
                    add("invalid_visit_duration", f"{name} 游览时长无效", i, name)
                    length = 120
                windows = opening_windows(attraction.open_hours, day.date)
                if windows is None:
                    add("unknown_open_hours", f"{name} 开放时间需人工确认", i, name, "warning")
                else:
                    fitting = [(a, b) for a, b in windows if max(clock, a) + length <= b]
                    if not fitting:
                        add("opening_conflict", f"{name} 在预计到达时段无法完成游览或当天闭馆", i, name)
                    else:
                        clock = max(clock, fitting[0][0])
                clock += length
            elif kind == "meal" and name in meals:
                clock += 60
            previous = name
        elapsed_by_day[i] = clock - start
        if clock - start > request.max_day_minutes:
            add("day_overloaded", f"第 {i + 1} 天预计 {clock - start} 分钟，超过上限 {request.max_day_minutes} 分钟", i)
        end_limit = minutes(request.day_end_time)
        if clock > (end_limit if end_limit is not None else 1320):
            add("day_ends_late", f"第 {i + 1} 天预计结束时间超过 {request.day_end_time}", i)
        if i > 0 and city_for_day(request, i) != city_for_day(request, i - 1):
            add("transfer_unverified", "跨城交通时间与费用尚未核验，请预留交通时段", i, severity="warning")

    budgets = [d.day_budget for d in priced_days(days, request)]
    total = sum(b.total for b in budgets)
    unknowns = [x for b in budgets for x in b.unknown_items]
    for value in sorted(set(unknowns)):
        add("unknown_price", f"{value} 费用未知，未计入已知费用小计", subject=value, severity="warning")
    if request.budget is not None and total > request.budget:
        add("budget_exceeded", f"费用估算 {total} 元超过预算 {request.budget} 元")
    return ValidationReport(valid=not any(v.severity == "error" for v in issues),
                            violations=issues, total_cost=total,
                            pricing_status="incomplete" if unknowns else "estimated",
                            day_minutes=elapsed_by_day,
                            poi_verifiable_rate=verified / attraction_count if attraction_count else 0)

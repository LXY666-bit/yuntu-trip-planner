"""单日预算计算"""
from ....models.schemas import Budget, DayDetail


_DAILY_TRANSPORT_DEFAULT = 50  # 元/天，与旧 reduce_assemble_node 保持一致


def compute_day_budget(day_detail: DayDetail, *, people: int = 1, rooms: int = 1,
                       include_hotel: bool = True) -> Budget:
    total_attractions = sum(a.ticket_price for a in day_detail.attractions) * people
    total_meals = sum(m.estimated_cost for m in day_detail.meals) * people
    total_hotels = day_detail.hotel.estimated_cost if (
        day_detail.hotel and day_detail.hotel.estimated_cost
    ) else 0
    total_hotels = total_hotels * rooms if include_hotel else 0
    # 空日（无任何景点/餐饮/酒店）不计交通费；否则按日固定默认值
    has_content = bool(day_detail.attractions) or bool(day_detail.meals) or bool(day_detail.hotel)
    total_transportation = _DAILY_TRANSPORT_DEFAULT if has_content else 0
    total_transportation *= people
    unknown = [a.name for a in day_detail.attractions if a.price_status == "unknown" and not a.ticket_price]
    unknown += [m.name for m in day_detail.meals if not m.estimated_cost]
    if include_hotel and day_detail.hotel and not total_hotels:
        unknown.append(day_detail.hotel.name)
    return Budget(
        total_attractions=total_attractions,
        total_hotels=total_hotels,
        total_meals=total_meals,
        total_transportation=total_transportation,
        total=total_attractions + total_meals + total_hotels + total_transportation,
        pricing_status="incomplete" if unknown else "estimated",
        unknown_items=unknown,
        notes=["交通暂按每人每天50元估算；门票和餐饮按人数计算",
               f"住宿按{rooms}间房估算，末日不计住宿" if not include_hotel else f"住宿按{rooms}间房估算"],
    )

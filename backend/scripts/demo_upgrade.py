"""Isolated offline demo: synthetic model/POI/route responses, never production data.

From backend: python scripts/demo_upgrade.py
API: http://127.0.0.1:18001 ; draft ID is printed at startup.
"""
import asyncio
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_demo_storage = tempfile.TemporaryDirectory(prefix="yuntu-demo-", ignore_cleanup_errors=True)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + (Path(_demo_storage.name)/"demo.db").as_posix()
os.environ["RUN_METRICS_PATH"] = str(Path(_demo_storage.name)/"runs.jsonl")

from app.api.main import app
from app.database import init_db
from app.models.schemas import TripRequest, MacroPlan, DaySkeleton, DayDetail, Attraction, Hotel, Location, RouteSegment
from app.services import planning_assistant as assistant, trip_draft_service as drafts
from app.api.routes import trip_draft
from app.agents.langgraph_agent.finalize import pipeline
from fastapi.responses import JSONResponse


@app.middleware("http")
async def offline_only(request, call_next):
    """Do not let result-page photos or unrelated UI actions contact real providers."""
    path = request.url.path
    if path == "/api/poi/photo":
        return JSONResponse({"success": True, "message": "离线演示不请求图片",
                             "data": {"name": request.query_params.get("name", ""), "photo_url": None}})
    draft_route = re.fullmatch(r"/api/trip/draft/[^/]+(?:/(?:validation|constraints|proposals(?:/[^/]+(?:/confirm)?)?|finalize))?", path)
    history_read = request.method == "GET" and (path == "/api/trips" or path.startswith("/api/trips/"))
    reservation_route = re.fullmatch(r'/api/reservations/(draft|trip)/[^/]+(?:/[^/]+)?', path)
    if path.startswith("/api/") and not (draft_route or history_read or reservation_route):
        return JSONResponse(status_code=503, content={"detail": "离线演示仅开放校验、提案、确认与定稿；此操作需启动正式后端"})
    return await call_next(request)


def attr(name, ident, indoor=False):
    reservation = {'status': 'unknown'}
    if indoor or ident == 'demo-bund':
        reservation = {'status': 'required', 'advance_days': 7, 'release_time': '20:00',
                       'channel': '演示预约渠道（非真实服务）', 'source_title': '固定离线演示攻略',
                       'evidence': f'{name}需提前7天预约，每天20:00放票。', 'tips': '这是合成规则，仅供功能演示。'}
    return Attraction(name=name, poi_id=ident, address="离线演示地址", description="此内容为固定演示数据",
                      reservation=reservation,
                      location=Location(longitude=121.47, latitude=31.23), visit_duration=90,
                      ticket_price=30, price_status="estimated", open_hours="09:00-18:00", indoor=indoor)


async def candidates(city):
    return [attr("演示博物馆", "demo-museum", True), attr("演示美术馆", "demo-art", True)]


async def model_reply(system, payload):
    await asyncio.sleep(.2)
    if "day" not in payload:
        message = payload["message"]
        match = re.search(r"第([一二三123])天", message)
        if not match:
            return {"unsupported": True}
        number = "一二三".find(match[1]) if match[1] in "一二三" else int(match[1])-1
        return {"day_index": number, "instruction": message, "indoor_only": "室内" in message}
    pool = payload["candidates"]
    key = next((key for key, value in pool.items() if value.get("indoor")), next(iter(pool)))
    return {"day_index": payload["day"]["day_index"], "attraction_ids": [key], "reason": "离线固定模型回复"}


async def routes(day, *args):
    order = day.timeline_order
    return [RouteSegment(from_name=a["ref_name"], to_name=b["ref_name"], duration="15分钟", distance="2公里", mode="公共交通", detail="离线演示估算") for a,b in zip(order, order[1:])]


async def narrative(*args, **kwargs):
    return "离线演示的当日行程说明。"


async def synthesize(*args):
    return "离线演示行程", "这是固定工具与模型响应的演示，不代表实时旅游信息。", "演示天气"


assistant.retrieve_candidates = candidates
assistant.model_json = model_reply
assistant.compute_day_route = routes
trip_draft.compute_day_route = routes
trip_draft.write_day_narrative_llm = narrative
pipeline.compute_day_route = routes
pipeline._run_global_synthesizer = synthesize


async def setup():
    await init_db()
    from app.services.reservations import CHINA
    start = datetime.now(CHINA).date() + timedelta(days=14)
    req = TripRequest(city="上海（离线演示）", start_date=start.isoformat(), end_date=(start + timedelta(days=2)).isoformat(), travel_days=3,
                      transportation="公共交通", accommodation="经济型酒店", budget=2000)
    attractions = [attr("演示外滩", "demo-bund"), attr("演示公园", "demo-park"), attr("演示老街", "demo-street")]
    macro = MacroPlan(city=req.city, total_days=3, days=[DaySkeleton(day_index=i, date=(start + timedelta(days=i)).isoformat(), attraction_names=[a.name]) for i,a in enumerate(attractions)])
    hotel = Hotel(name="保持不变的演示酒店", estimated_cost=200, location=Location(longitude=121.48, latitude=31.24))
    ident = await drafts.create_draft(user_id="offline-demo", request=req, selected_attractions=[], macro_plan=macro,
                                    clusters_data=[[a.model_dump()] for a in attractions], hotels_by_day=[[hotel.model_dump()]]*3, dining_pool=[{}]*3, weather_info=[])
    for i, a in enumerate(attractions):
        d = DayDetail(day_index=i, date=macro.days[i].date, attractions=[a], hotel=hotel,
                      timeline_order=[{"kind":"attraction", "ref_name":a.name}], day_start_time="09:00", is_assembled=True)
        await drafts.patch_day_detail(ident,i,d)
    print(f"OFFLINE DEMO draft: {ident}", flush=True)
    output = Path(__file__).parents[1].joinpath("evals/results/demo-id.txt")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(ident, encoding="utf-8")


app.router.on_startup.clear()
app.router.on_startup.append(setup)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18001, log_level="warning")

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from app.api.main import app
from app.api.routes.sse_utils import heartbeat_wrapper
from app.database import init_db, async_session
from app.models.db_models import TripDraft, TripRecord, UserPreferenceRecord
from app.models.schemas import TripRequest, DayDetail, Attraction, Hotel, Location, MacroPlan, DaySkeleton
from app.models.planning import ProposalRequest, DayPatch
from app.services import planning_assistant as service, trip_draft_service as drafts
from app.services.plan_validation import validate_plan, opening_windows, priced_days


def attraction(name="公园", **values):
    return Attraction(name=name, address="测试地址", visit_duration=90, description="固定测试数据",
                      location=Location(longitude=121.47, latitude=31.23), poi_id=name,
                      **{"ticket_price": 20, "price_status": "estimated", "open_hours": "08:00-22:00", **values})


def request(**values):
    return TripRequest(**{"city": "上海", "start_date": "2026-10-13", "end_date": "2026-10-15",
                          "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店", **values})


def test_weekday_closure_and_midnight_deadline():
    assert opening_windows("星期天闭馆 09:00-17:00", "2026-10-18") == []
    assert opening_windows("星期天闭馆 09:00-17:00", "2026-10-13") is None
    day = DayDetail(day_index=0, date="2026-10-13", attractions=[attraction()])
    report = validate_plan(request(travel_days=1, end_date="2026-10-13", day_end_time="00:00"), [day])
    assert any(v.code == "day_ends_late" for v in report.violations)


@pytest_asyncio.fixture
async def seeded():
    await init_db()
    req = request()
    days = [DayDetail(day_index=i, date=f"2026-10-{13+i}", attractions=[attraction(f"公园{i}")],
                      hotel=Hotel(name="保留酒店", estimated_cost=200), is_assembled=True,
                      day_start_time="08:00", timeline_order=[{"kind": "attraction", "ref_name": f"公园{i}"}]) for i in range(3)]
    ident = await drafts.create_draft(user_id=uuid.uuid4().hex, request=req, selected_attractions=[],
                                     macro_plan=MacroPlan(city="上海", total_days=3, days=[DaySkeleton(day_index=i, date=d.date, attraction_names=[d.attractions[0].name]) for i, d in enumerate(days)]),
                                     clusters_data=[[]]*3, hotels_by_day=[[]]*3, dining_pool=[{}]*3, weather_info=[])
    for i, day in enumerate(days):
        await drafts.patch_day_detail(ident, i, day)
    return ident


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest_asyncio.fixture
async def fake_tools(monkeypatch):
    museum = attraction("测试博物馆", indoor=True)
    monkeypatch.setattr(service, "retrieve_candidates", AsyncMock(return_value=[museum]))
    monkeypatch.setattr(service, "propose_patch", AsyncMock(return_value=DayPatch(day_index=1, attraction_ids=[museum.poi_id])))
    monkeypatch.setattr(service, "compute_day_route", AsyncMock(return_value=[]))


async def proposal(ident):
    return await service.create_proposal(ident, ProposalRequest(message="第二天改成室内景点，酒店不变", day_index=1))


async def test_proposal_does_not_mutate_until_confirmation_and_only_changes_day_two(seeded, fake_tools):
    old = await drafts.get_draft(seeded)
    result = await proposal(seeded)
    assert result.status == "pending"
    assert (await drafts.get_draft(seeded)).days_detail_json == old.days_detail_json
    await service.confirm_proposal(seeded, result.proposal_id)
    before = json.loads(old.days_detail_json)
    after = json.loads((await drafts.get_draft(seeded)).days_detail_json)
    assert before[0] == after[0] and before[2] == after[2]
    assert before[1]["hotel"] == after[1]["hotel"]
    assert after[1]["attractions"][0]["name"] == "测试博物馆"
    assert after[1]["day_budget"] is not None


async def test_confirmation_idempotent_and_remember_requires_opt_in(seeded, fake_tools):
    result = await proposal(seeded)
    await service.confirm_proposal(seeded, result.proposal_id, remember=True)
    first = (await drafts.get_draft(seeded)).days_detail_json
    assert (await service.confirm_proposal(seeded, result.proposal_id, remember=True)).status == "applied"
    assert (await drafts.get_draft(seeded)).days_detail_json == first
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(UserPreferenceRecord).where(UserPreferenceRecord.user_id == (await drafts.get_draft(seeded)).user_id))
        assert count == 1


async def test_stale_and_cancelled_proposals_cannot_apply(seeded, fake_tools):
    result = await proposal(seeded)
    old = json.loads((await drafts.get_draft(seeded)).days_detail_json)
    change = DayDetail.model_validate(old[0]); change.description = "人工编辑"
    await drafts.patch_day_detail(seeded, 0, change)
    with pytest.raises(service.PlanConflict, match="变化"):
        await service.confirm_proposal(seeded, result.proposal_id)
    fresh = await proposal(seeded)
    await service.cancel_proposal(seeded, fresh.proposal_id)
    with pytest.raises(service.PlanConflict):
        await service.confirm_proposal(seeded, fresh.proposal_id)


async def test_unknown_proposal_wrong_draft_and_explicit_confirmation(client, seeded, fake_tools):
    result = await proposal(seeded)
    url = f"/api/trip/draft/{seeded}/proposals/{result.proposal_id}/confirm"
    assert (await client.post(url, json={})).status_code == 422
    assert (await client.post(url, json={"confirmed": False})).status_code == 422
    assert (await client.post(url.replace(seeded, "another"), json={"confirmed": True})).status_code == 404
    assert (await client.post(url, json={"confirmed": True})).status_code == 200


async def test_failed_retrieval_never_fabricates_indoor_candidates(seeded, monkeypatch):
    monkeypatch.setattr(service, "retrieve_candidates", AsyncMock(side_effect=TimeoutError))
    model = AsyncMock()
    monkeypatch.setattr(service, "propose_patch", model)
    result = await proposal(seeded)
    assert result.status == "blocked" and result.after == {}
    model.assert_not_awaited()


async def test_invalid_model_poi_ids_rejected():
    with patch.object(service, "model_json", AsyncMock(return_value={"day_index": 1, "attraction_ids": ["fake"]})):
        with pytest.raises(ValueError, match="候选池"):
            await service.propose_patch(DayDetail(day_index=1, date="2026-10-14"), {}, "替换", [], request())


async def test_repair_is_bounded_and_unresolved_conflict_blocks_confirmation(seeded, fake_tools):
    async with async_session() as session:
        row = await session.get(TripDraft, seeded)
        req = TripRequest.model_validate_json(row.request_json); req.budget = 1
        row.request_json = req.model_dump_json(); await session.commit()
    result = await service.create_proposal(seeded, ProposalRequest(repair=True, day_index=1))
    assert result.rounds == 2 and result.status == "blocked"
    with pytest.raises(service.PlanConflict):
        await service.confirm_proposal(seeded, result.proposal_id)


async def test_parallel_day_writes_preserve_both_and_same_day_conflicts(seeded):
    before = json.loads((await drafts.get_draft(seeded)).days_detail_json)
    first, second = DayDetail.model_validate(before[0]), DayDetail.model_validate(before[1])
    first.description, second.description = "第一天新内容", "第二天新内容"
    await asyncio.gather(drafts.patch_day_detail(seeded, 0, first, expected_day=before[0]),
                         drafts.patch_day_detail(seeded, 1, second, expected_day=before[1]))
    after = json.loads((await drafts.get_draft(seeded)).days_detail_json)
    assert after[0]["description"] == first.description and after[1]["description"] == second.description
    with pytest.raises(drafts.DraftConflict):
        await drafts.patch_day_detail(seeded, 0, first, expected_day=before[0])


async def test_finalization_atomic_under_concurrent_calls(seeded):
    from app.agents.langgraph_agent.finalize import pipeline
    with patch.object(pipeline, "_run_global_synthesizer", AsyncMock(return_value=("", "", ""))), patch.object(pipeline, "compute_day_route", AsyncMock(return_value=[])):
        outputs = await asyncio.gather(pipeline.finalize_draft(seeded, user_id="test"), pipeline.finalize_draft(seeded, user_id="test"), return_exceptions=True)
    assert sum(isinstance(item, tuple) for item in outputs) == 1
    row = await drafts.get_draft(seeded)
    async with async_session() as session:
        assert await session.get(TripRecord, row.finalized_trip_id) is not None


async def test_heartbeats_while_waiting_and_source_closed_on_cancel():
    closed = asyncio.Event()
    async def source():
        try:
            await asyncio.sleep(10)
            yield "complete"
        finally:
            closed.set()
    stream = heartbeat_wrapper(source, .005)
    assert await asyncio.wait_for(anext(stream), .1) == ": heartbeat\n\n"
    await stream.aclose()
    assert closed.is_set()


async def test_heartbeat_stream_finishes_at_eof():
    async def source():
        yield "data: complete\n\n"
    assert [item async for item in heartbeat_wrapper(source, .005)] == ["data: complete\n\n"]


def test_validation_reports_hard_constraints_and_unknowns():
    req = request(must_visit=["必去"], budget=1, max_day_minutes=60)
    days = [DayDetail(day_index=i, date=f"2026-10-{13+i}", attractions=[attraction(f"公园{i}", open_hours="09:00-09:30", ticket_price=0, price_status="unknown")]) for i in range(3)]
    report = validate_plan(req, days)
    codes = {v.code for v in report.violations}
    assert {"missing_must_visit", "budget_exceeded", "day_overloaded", "opening_conflict", "unknown_price"} <= codes
    assert not report.valid and report.pricing_status == "incomplete"


def test_open_hours_weekday_and_unknown_schedule():
    assert opening_windows("周一闭馆", "2026-10-12") == []
    assert opening_windows("08:00-12:00;13:00-18:00", "2026-10-13") == [(480, 720), (780, 1080)]
    assert opening_windows("旺季08:00-18:00", "2026-10-13") is None


def test_budget_party_size_nights_and_unknown_free_are_distinct():
    req = request(companions={"count": 3, "type": "family"})
    days = [DayDetail(day_index=i, date=f"2026-10-{13+i}", hotel=Hotel(name="酒店", estimated_cost=200), attractions=[attraction()]) for i in range(3)]
    result = priced_days(days, req)
    assert result[0].day_budget.total_hotels == 400
    assert result[2].day_budget.total_hotels == 0
    assert result[0].day_budget.total_attractions == 60


async def test_generated_trip_does_not_become_a_preference():
    from app.agents.langgraph_agent.nodes.preferences import extract_preferences_node
    assert (await extract_preferences_node({"request": request(), "trip_plan": {"hotel": "invented"}}))["extracted_preferences"] is None


async def test_parallel_graph_failure_reaches_fallback(monkeypatch):
    from app.agents.langgraph_agent import graph
    async def preferences(state): return {"user_preferences": None}
    async def failure(state): return {"errors": ["upstream failed"]}
    async def noop(state): return {}
    monkeypatch.setattr(graph, "load_user_preferences_node", preferences)
    for name in ("web_search_attractions_node", "search_weather_node", "search_hotel_node"):
        monkeypatch.setattr(graph, name, failure)
    for name in ("extract_attractions_node", "geocode_attractions_node", "gather_search_node", "cluster_attractions_node", "search_food_node", "plan_route_node", "macro_planner_node"):
        monkeypatch.setattr(graph, name, noop)
    result = await graph.create_trip_planner_graph().ainvoke({"errors": [], "macro_plan": None})
    assert len(result["errors"]) == 3

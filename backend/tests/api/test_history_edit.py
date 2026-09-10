import pytest
from httpx import ASGITransport, AsyncClient
from app.api.main import app
from app.database import init_db


@pytest.mark.asyncio
async def test_edit_history_persists_plan_and_retains_status():
    await init_db()
    plan = {"city": "西安", "start_date": "2026-09-18", "end_date": "2026-09-18",
            "days": [], "weather_info": [], "overall_suggestions": "原建议"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.post("/api/trips", json={"plan": plan})
        assert saved.status_code == 200
        trip_id = saved.json()["data"]["id"]
        await client.patch(f"/api/trips/{trip_id}/status", json={"status": "favorite"})
        plan["overall_suggestions"] = "修改后仍保留的建议"
        updated = await client.put(f"/api/trips/{trip_id}/plan", json=plan)
        assert updated.status_code == 200
        reloaded = (await client.get(f"/api/trips/{trip_id}")).json()["data"]
        assert reloaded["plan"]["overall_suggestions"] == plan["overall_suggestions"]
        assert reloaded["status"] == "favorite"


@pytest.mark.asyncio
async def test_edit_missing_history_returns_404():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/trips/999999/plan", json={
            "city": "西安", "start_date": "2026-09-18", "end_date": "2026-09-18", "days": [], "overall_suggestions": "",
        })
        assert response.status_code == 404

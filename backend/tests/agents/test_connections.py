"""Opt-in smoke tests against the configured providers; failures must stay visible."""
import asyncio
import pytest
from app.services.llm_service import get_llm
from app.services.langchain_amap_tools import get_langchain_amap_service

pytestmark = [pytest.mark.smoke, pytest.mark.asyncio]

async def test_llm_connection():
    response = await asyncio.wait_for(get_llm().ainvoke("回复 OK 即可"), timeout=45)
    assert response.content

@pytest.mark.parametrize("tool_name,arguments", [
    ("maps_weather", {"city": "北京"}),
    ("maps_text_search", {"keywords": "故宫", "city": "北京"}),
    ("maps_direction_walking", {"origin": "116.397,39.918", "destination": "116.397,39.909"}),
])
async def test_amap_connection(tool_name, arguments):
    from app.agents.langgraph_agent.exceptions import _invoke_tool_with_retry
    service = get_langchain_amap_service()
    tool = await service.get_tool(tool_name)
    assert tool is not None
    result = await _invoke_tool_with_retry(tool, arguments, max_retries=1)
    assert result
    assert "API 调用失败" not in str(result)

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.langgraph_agent.utils.llm_json import parse_json_answer
from app.agents.langgraph_agent.utils.parsing import _extract_poi_names
from app.agents.langgraph_agent.utils.duration import estimate_durations_batch
from app.agents.langgraph_agent.utils.strategy_extract import pick_attractions_from_pool
from app.agents.langgraph_agent import graph as graph_module
from app.agents.langgraph_agent.exceptions import _invoke_tool_with_retry
from app.agents.langgraph_agent.nodes.discovery import geocode_batch_node
from app.agents.langgraph_agent.nodes.generate import global_synthesizer_node


def test_json_blocks_nested_arrays_and_reasoning():
    response = SimpleNamespace(content=[
        {"type": "reasoning", "text": '{"wrong": true}'},
        {"type": "text", "text": '<think>{"wrong": true}</think>答案：```json\n'
         '{"must": [{"poi_id": "1", "tags": ["古迹"]}], "optional": []}\n```'},
    ])
    assert parse_json_answer(response)["must"][0]["tags"] == ["古迹"]


@pytest.mark.parametrize("text", ["", "没有结果", "{broken"])
def test_invalid_answer_is_rejected(text):
    with pytest.raises(ValueError):
        parse_json_answer(text)


@pytest.mark.asyncio
async def test_empty_ai_answer_retries_and_deduplicates():
    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=[
        SimpleNamespace(content=""),
        SimpleNamespace(content='{"must":[{"poi_id":"1"},{"poi_id":"1"}],"optional":[]}'),
    ]))
    target = "app.agents.langgraph_agent.utils.strategy_extract."
    with patch(target + "get_llm", return_value=llm), \
         patch(target + "is_structured_output_supported", return_value=False), \
         patch(target + "estimate_durations_batch", new=AsyncMock(return_value={"A": 90})):
        result = await pick_attractions_from_pool("西安", 1, [{"poi_id": "1", "name": "A"}])
    assert result["must_ids"] == ["1"]
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_known_durations_skip_llm():
    with patch("app.agents.langgraph_agent.utils.duration.get_llm") as llm:
        assert await estimate_durations_batch([{"name": "A", "visit_minutes": 180}]) == {"A": 180}
        llm.assert_not_called()


def test_single_poi_detail_and_separate_coordinates():
    result = _extract_poi_names(json.dumps([{"type": "text", "text": json.dumps({
        "name": "钟楼", "longitude": 108.94, "latitude": 34.26,
    })}]))
    assert result[0]["location"] == "108.94,34.26"


@pytest.mark.asyncio
@pytest.mark.parametrize("weather_delay", [0, 0.03])
async def test_discovery_gathers_once_after_both_branches(weather_delay):
    async def weather(state):
        await asyncio.sleep(weather_delay)
        return {"weather_info": "晴"}

    async def geocode(state):
        await asyncio.sleep(0.01)
        batches = state["_geocode_batches"]
        return {"discovered_attractions": batches[0], "_geocode_batches": batches[1:]}

    gathered = []
    async def gather(state):
        gathered.append((len(state["discovered_attractions"]), state["weather_info"]))
        return {}

    with patch.multiple(graph_module,
        web_search_attractions_node=AsyncMock(return_value={}),
        extract_attractions_expanded_node=AsyncMock(return_value={}),
        geocode_dispatch_node=AsyncMock(return_value={"_geocode_batches": [[{"name": "A"}], [{"name": "B"}]]}),
        geocode_batch_node=geocode, search_weather_node=weather, gather_discovery_node=gather,
    ):
        graph = graph_module.create_discovery_graph()
        await graph.ainvoke({"discovered_attractions": [], "weather_info": ""})
    assert gathered == [(2, "晴")]


@pytest.mark.asyncio
async def test_amap_qps_limit_retries_even_with_one_generic_attempt():
    tool = SimpleNamespace(name="maps_text_search", ainvoke=AsyncMock(side_effect=[
        RuntimeError("CUQPS_HAS_EXCEEDED_THE_LIMIT"), {"pois": []},
    ]))
    with patch("app.agents.langgraph_agent.exceptions.asyncio.sleep", new=AsyncMock()):
        assert await _invoke_tool_with_retry(tool, {}, max_retries=1) == {"pois": []}
    assert tool.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_missing_poi_location_uses_address_geocode():
    service = SimpleNamespace(get_tool=AsyncMock(side_effect=lambda name: SimpleNamespace(name=name)))
    async def invoke(tool, args, **kwargs):
        if tool.name == "maps_geo":
            assert args["city"] == "西安"
            return {"geocodes": [{"location": "108.94,34.26", "level": "兴趣点"}]}
        return json.dumps({"pois": [{"id": "1", "name": "钟楼"}]})
    target = "app.agents.langgraph_agent.nodes.discovery."
    with patch(target + "get_langchain_amap_service", return_value=service), \
         patch(target + "_invoke_tool_with_retry", new=invoke):
        result = await geocode_batch_node({
            "request": SimpleNamespace(city="西安"),
            "_geocode_batches": [[{"name": "钟楼"}]],
        })
    assert result["discovered_attractions"][0]["location"] == {"longitude": 108.94, "latitude": 34.26}


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "请提前预约景点", '答案：{"overall_suggestions":"提前预约","trip_tagline":"古都之旅"}'])
async def test_global_suggestions_does_not_repeat_same_failed_request(content):
    plan = SimpleNamespace(city="西安", days=[], budget=None, weather_info=[])
    invoke = AsyncMock(return_value=SimpleNamespace(content=content))
    target = "app.agents.langgraph_agent.nodes.generate."
    with patch(target + "get_llm"), patch(target + "_invoke_llm_with_retry", new=invoke):
        result = await global_synthesizer_node({"trip_plan": plan})
    assert result["global_narrative"]
    assert invoke.await_count == 1

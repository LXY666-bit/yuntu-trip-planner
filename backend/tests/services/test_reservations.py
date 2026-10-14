import json
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.api.main import app
from app.database import init_db
from app.models.schemas import Attraction, DiscoveredAttraction, DayDetail, TripRequest, MacroPlan, DaySkeleton
from app.models.reservation import ReservationInfo, reservation_fields
from app.services.reservation_extraction import extract_reservation
from app.services.reservations import reservation_tasks, calendar, set_booked, load_scope, CHINA
from app.services import trip_draft_service as drafts
from app.services.planning_assistant import current_days, candidate_from_dict
from app.agents.langgraph_agent.nodes.cluster import _selection_to_cluster_dict
from app.agents.langgraph_agent.finalize import pipeline

EVIDENCE = '测试博物馆需提前7天预约，每天20:00放票，预约渠道为官方小程序。'
INFO = {'status': 'required', 'advance_days': 7, 'release_time': '20:00', 'channel': '官方小程序',
        'tips': '请提前关注预约', 'evidence': EVIDENCE, 'source_url': 'https://example.com/note', 'source_title': '合成攻略'}
NOW = datetime(2030, 10, 1, 9, tzinfo=CHINA)


def attraction(**kwargs):
    return Attraction(**{'name': '测试博物馆', 'address': '测试地址', 'description': '测试', 'visit_duration': 60,
                         'poi_id': 'museum', 'open_hours': '08:00-22:00', 'reservation': INFO, **kwargs})


def days(**kwargs):
    return [DayDetail(day_index=0, date='2030-10-10', attractions=[attraction(**kwargs)])]


@pytest.mark.parametrize('old,expected', [({}, 'unknown'), ({'reservation_required': False}, 'unknown'),
                                        ({'reservation_required': True, 'reservation_tips': None}, 'required')])
def test_legacy_absence_is_not_no_reservation(old, expected):
    attr = Attraction(name='old', address='', description='', visit_duration=90, **old)
    assert attr.reservation.status == expected


def test_extract_requires_source_and_does_not_invent_days_or_booking():
    raw = EVIDENCE + '\nhttps://example.com/note'
    good = extract_reservation({'reservation': INFO, 'reservation_booked_for': '2030-10-10'}, raw)
    assert good['reservation']['advance_days'] == 7
    assert good['reservation_booked_for'] is None
    assert extract_reservation({'reservation': INFO}, '没有预约内容')['reservation']['status'] == 'unknown'
    altered = {**INFO, 'advance_days': 30, 'release_time': '10:00', 'source_url': 'https://invented.test'}
    result = extract_reservation({'reservation': altered}, raw)['reservation']
    assert result['advance_days'] is None and result['release_time'] is None and result['source_url'] is None
    assert ReservationInfo(source_url='javascript:alert(1)').source_url is None


@pytest.mark.parametrize('status', ['unknown', 'not_required', 'conflicting'])
def test_no_computed_reminder_for_unconfirmed_or_conflicting_rules(status):
    task = reservation_tasks(days(reservation={**INFO, 'status': status}), NOW)[0]
    assert task['status'] == status and task['remind_at'] is None and not task['calendar_eligible']


def test_reminder_dates_booking_and_time_boundaries():
    task = reservation_tasks(days(), NOW)[0]
    assert task['remind_at'] == '2030-10-03T20:00:00+08:00' and task['status'] == 'upcoming'
    assert reservation_tasks(days(), datetime(2030, 10, 3, 20, tzinfo=CHINA))[0]['status'] == 'due'
    assert reservation_tasks(days(), datetime(2030, 10, 11, tzinfo=CHINA))[0]['status'] == 'past_visit'
    assert reservation_tasks(days(reservation_booked_for='2030-10-10'), NOW)[0]['status'] == 'booked'
    assert reservation_tasks(days(reservation_booked_for='2030-10-09'), NOW)[0]['status'] == 'upcoming'
    default = reservation_tasks(days(reservation={**INFO, 'release_time': None}), NOW)[0]
    assert default['default_reminder_time'] and 'T09:00:' in default['remind_at']
    assert reservation_tasks(days(reservation={**INFO, 'advance_days': None}), NOW)[0]['status'] == 'needs_check'


def test_calendar_utc_folding_escaping_and_no_past_or_booked_events():
    tasks = reservation_tasks(days(name='馆,;\\\nBEGIN:VEVENT', reservation={**INFO, 'tips': '中文' * 100}), NOW)
    content = calendar(tasks, 'draft:test', NOW)
    assert 'DTSTART:20301003T120000Z' in content
    assert 'BEGIN:VALARM\r\nTRIGGER:PT0M' in content
    assert '\\,\\;\\\\\\nBEGIN:VEVENT' in content
    assert all(len(line.encode()) <= 75 for line in content.split('\r\n'))
    assert content.split('\r\n').count('BEGIN:VEVENT') == 1
    assert 'BEGIN:VEVENT' not in calendar(reservation_tasks(days(reservation_booked_for='2030-10-10'), NOW), 'draft:test', NOW)
    assert 'BEGIN:VEVENT' not in calendar(reservation_tasks(days(), datetime(2030, 10, 4, tzinfo=CHINA)), 'draft:test', NOW)


@pytest_asyncio.fixture
async def draft_id():
    await init_db()
    request = TripRequest(city='测试', start_date='2030-10-10', end_date='2030-10-11', travel_days=2,
                          transportation='公共交通', accommodation='经济型酒店')
    selected = DiscoveredAttraction(name='测试博物馆', location={'longitude': 121.4, 'latitude': 31.2},
                                   poi_id='museum', visit_minutes=60, open_hours='08:00-22:00', reservation=INFO)
    cluster = _selection_to_cluster_dict(selected.model_dump(mode='json'))
    macro = MacroPlan(city='测试', total_days=2, days=[DaySkeleton(day_index=i, date=f'2030-10-{10+i}', attraction_names=['测试博物馆']) for i in range(2)])
    return await drafts.create_draft(user_id='reservation-test', request=request, selected_attractions=[selected],
                                    macro_plan=macro, clusters_data=[[cluster], [cluster]], hotels_by_day=[[], []],
                                    dining_pool=[{}, {}], weather_info=[])


async def test_discovery_cluster_draft_candidate_finalize_preserves_reservations(draft_id):
    record = await drafts.get_draft(draft_id)
    _, initial = current_days(record)
    assert initial[0].attractions[0].reservation.advance_days == 7
    candidate = candidate_from_dict(initial[0].attractions[0].model_dump(mode='json'))
    assert candidate.reservation.source_url == INFO['source_url']
    task = reservation_tasks(initial, NOW)[0]
    await set_booked('draft', draft_id, task['id'], True)
    before = await drafts.get_draft(draft_id)
    assert json.loads(before.days_detail_json)[1] is None
    with patch.object(pipeline, 'compute_day_route', AsyncMock(return_value=[])), patch.object(pipeline, '_run_global_synthesizer', AsyncMock(return_value=('', '', ''))):
        plan, trip_id = await pipeline.finalize_draft(draft_id, user_id='reservation-test')
    assert plan.days[0].attractions[0].reservation_booked_for == date(2030, 10, 10)
    _, saved = await load_scope('trip', str(trip_id))
    assert reservation_tasks(saved, NOW)[0]['booked']
    await set_booked('trip', str(trip_id), task['id'], False)
    _, saved = await load_scope('trip', str(trip_id))
    assert not reservation_tasks(saved, NOW)[0]['booked']
    assert saved[1].attractions[0].reservation == initial[1].attractions[0].reservation


async def test_booking_api_requires_boolean_and_scope_and_produces_calendar(draft_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        base = f'/api/reservations/draft/{draft_id}'
        response = await client.get(base)
        assert response.status_code == 200
        key = response.json()['tasks'][0]['id']
        assert (await client.patch(base + '/' + key, json={'booked': 'false'})).status_code == 422
        assert (await client.patch(base + '/stale-key', json={'booked': True})).status_code == 409
        marked = await client.patch(base + '/' + key, json={'booked': True})
        assert marked.status_code == 200 and marked.json()['tasks'][0]['booked']
        assert (await client.get('/api/reservations/trip/not-an-id')).status_code == 404
        exported = await client.get(base + '/calendar.ics')
        assert exported.status_code == 200 and 'text/calendar' in exported.headers['content-type']
        assert 'BEGIN:VCALENDAR' in exported.text


def test_xhs_extract_keeps_real_note_url_and_quote(monkeypatch):
    from app.services import xhs_service as xhs, llm_service
    from langchain_core.messages import AIMessage
    client = Mock()
    client.search_notes.return_value = {'data': {'items': [{'model_type': 'note', 'id': 'test-note', 'note_card': {'display_title': '合成攻略'}}]}}
    client.get_note_detail.return_value = {'data': {'items': [{'note_card': {'desc': EVIDENCE}}]}}
    info = {**INFO, 'source_url': 'https://www.xiaohongshu.com/explore/test-note'}
    llm = Mock()
    llm.invoke.return_value = AIMessage(content=json.dumps([{'name': '测试博物馆', 'reservation': info}], ensure_ascii=False))
    monkeypatch.setattr(xhs, '_XHS_SIGN_AVAILABLE', True)
    monkeypatch.setattr(xhs, 'get_xhs_client', lambda: client)
    monkeypatch.setattr(xhs, '_geocode_amap_raw', lambda *args: '121.4,31.2')
    monkeypatch.setattr(llm_service, 'get_llm', lambda: llm)
    raw, count = xhs.search_xhs_attractions('测试', '旅游攻略')
    item = json.loads(raw.splitlines()[-1])
    assert count == 1 and item['reservation']['source_url'] == info['source_url']
    assert item['reservation']['evidence'] == EVIDENCE and item['reservation']['advance_days'] == 7
    assert '未提及' in llm.invoke.call_args[0][0]


async def test_discovery_extraction_and_geocoding_keep_reservation(monkeypatch):
    from app.agents.langgraph_agent.nodes import discovery
    from langchain_core.messages import AIMessage
    item = {'name': '测试博物馆', 'description': '测试', 'reservation': INFO}
    raw = EVIDENCE + '\nhttps://example.com/note'
    req = TripRequest(city='测试', start_date='2030-10-10', end_date='2030-10-10', travel_days=1,
                      transportation='公共交通', accommodation='经济型酒店')
    tool_service = Mock()
    tool_service.get_tool = AsyncMock(return_value=None)
    monkeypatch.setattr(discovery, 'get_llm', lambda: Mock())
    monkeypatch.setattr(discovery, '_invoke_llm_with_retry', AsyncMock(return_value=AIMessage(content=json.dumps([item], ensure_ascii=False))))
    monkeypatch.setattr(discovery, 'get_langchain_amap_service', lambda: tool_service)
    extracted = await discovery.extract_attractions_expanded_node({'request': req, 'raw_search_results': raw})
    assert extracted['extracted_pois'][0]['reservation']['advance_days'] == 7
    monkeypatch.setattr(discovery, '_invoke_tool_with_retry', AsyncMock(return_value='{}'))
    monkeypatch.setattr(discovery, '_extract_poi_names', lambda _: [{'name': '测试博物馆', 'id': 'museum', 'location': '121.4,31.2'}])
    result = await discovery.geocode_batch_node({'request': req, '_geocode_batches': [extracted['extracted_pois']]})
    assert result['discovered_attractions'][0]['reservation']['source_url'] == INFO['source_url']


async def test_assignment_preview_keeps_reservation(monkeypatch):
    from app.api.routes import trip_lg
    monkeypatch.setattr(trip_lg, 'estimate_durations_batch', AsyncMock(return_value={'测试博物馆': 60}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        result = await client.post('/api/trip/plan/preview-day-assignment', json={
            'travel_days': 1, 'selected_attractions': [{'name': '测试博物馆', 'reservation': INFO}],
        })
        assert result.status_code == 200
        assert result.json()['day_assignments'][0][0]['reservation']['advance_days'] == 7

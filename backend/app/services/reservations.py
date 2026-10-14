"""Reservation checklist and calendar export, with no booking or push side effects."""
import hashlib
import json
from datetime import datetime, date, time, timedelta, timezone
from sqlalchemy import update
from ..database import async_session
from ..models.db_models import TripDraft, TripRecord
from ..models.schemas import TripPlan
from .planning_assistant import PlanConflict, DraftNotFound, current_days

CHINA = timezone(timedelta(hours=8))


def task_key(visit_date, attraction):
    return hashlib.sha256(f'{visit_date}|{attraction.poi_id or attraction.name}'.encode()).hexdigest()[:24]


def reservation_tasks(days, now=None):
    now = now or datetime.now(CHINA)
    now = now.astimezone(CHINA)
    tasks, seen = [], set()
    for day in days:
        for attraction in day.attractions:
            key = task_key(day.date, attraction)
            if key in seen:
                continue
            seen.add(key)
            info = attraction.reservation
            visit = date.fromisoformat(day.date)
            booked = attraction.reservation_booked_for == visit
            reminder = None
            if info.status == 'required' and info.advance_days is not None:
                opening = visit - timedelta(days=info.advance_days)
                reminder = datetime.combine(opening, time.fromisoformat(info.release_time or '09:00'), CHINA)
            if booked:
                status = 'booked'
            elif visit < now.date():
                status = 'past_visit'
            elif info.status in ('unknown', 'conflicting', 'not_required'):
                status = info.status
            elif reminder is None:
                status = 'needs_check'
            else:
                status = 'upcoming' if reminder > now else 'due'
            tasks.append({'id': key, 'day_index': day.day_index, 'visit_date': day.date,
                          'name': attraction.name, 'poi_id': attraction.poi_id,
                          'status': status, 'booked': booked, 'reservation': info.model_dump(mode='json'),
                          'remind_at': reminder.isoformat() if reminder else None,
                          'default_reminder_time': bool(reminder and not info.release_time),
                          'calendar_eligible': bool(reminder and reminder > now and not booked and visit >= now.date())})
    return tasks


async def load_scope(kind, ident):
    async with async_session() as session:
        if kind == 'draft':
            record = await session.get(TripDraft, ident)
            if record is None:
                raise DraftNotFound('草稿不存在')
            _, days = current_days(record)
        else:
            if not str(ident).isdigit():
                raise DraftNotFound('行程不存在')
            record = await session.get(TripRecord, int(ident))
            if record is None:
                raise DraftNotFound('行程不存在')
            days = TripPlan.model_validate_json(record.plan_data).days
        return record, days


async def set_booked(kind, ident, key, booked):
    record, days = await load_scope(kind, ident)
    target_day = None
    for day in days:
        for attraction in day.attractions:
            if task_key(day.date, attraction) == key:
                attraction.reservation_booked_for = date.fromisoformat(day.date) if booked else None
                target_day = day
    if target_day is None:
        raise PlanConflict('该景点或游览日期已变化，请刷新预约清单')
    async with async_session() as session:
        if kind == 'draft':
            raw = json.loads(record.days_detail_json)
            raw[target_day.day_index] = target_day.model_dump(mode='json')
            result = await session.execute(update(TripDraft).where(
                TripDraft.id == ident, TripDraft.status != 'finalized',
                TripDraft.days_detail_json == record.days_detail_json,
                TripDraft.request_json == record.request_json,
            ).values(days_detail_json=json.dumps(raw, ensure_ascii=False)))
        else:
            raw = json.loads(record.plan_data)
            # Change booking state only, keeping unrelated fields and dates intact.
            for day in raw['days']:
                for attraction in day.get('attractions', []):
                    if day['date'] == target_day.date and (attraction.get('poi_id') or attraction['name']) == next(
                        a.poi_id or a.name for a in target_day.attractions if task_key(target_day.date, a) == key
                    ):
                        attraction['reservation_booked_for'] = target_day.date if booked else None
            result = await session.execute(update(TripRecord).where(
                TripRecord.id == int(ident), TripRecord.plan_data == record.plan_data,
            ).values(plan_data=json.dumps(raw, ensure_ascii=False)))
        if result.rowcount != 1:
            raise PlanConflict('行程已变化或已定稿，请刷新后重试')
        await session.commit()
    return reservation_tasks(days)


def _ics_text(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def _fold(line):
    lines, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            lines.append(current)
            current = ' '
        current += char
    return '\r\n'.join(lines + [current])


def calendar(tasks, scope, now=None):
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//YunTu//Reservation reminders//ZH', 'CALSCALE:GREGORIAN']
    for task in tasks:
        if not task['calendar_eligible']:
            continue
        info = task['reservation']
        start = datetime.fromisoformat(task['remind_at']).astimezone(timezone.utc)
        description = f"游览日期：{task['visit_date']}。攻略预约线索，未经官方核验，请确认规则与余票。\n{info['tips']}\n渠道：{info['channel']}\n来源：{info['source_url'] or info['source_title'] or '未提供链接'}"
        if task['default_reminder_time']:
            description += '\n09:00为默认提醒时间，不是景点放票时间。'
        lines += ['BEGIN:VEVENT', f"UID:{hashlib.sha256((scope + task['id']).encode()).hexdigest()}@yuntu.local",
                  f'DTSTAMP:{stamp}', f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTEND:{(start + timedelta(minutes=15)).strftime('%Y%m%dT%H%M%SZ')}",
                  'SUMMARY:' + _ics_text('核实并预约：' + task['name']), 'DESCRIPTION:' + _ics_text(description),
                  'BEGIN:VALARM', 'TRIGGER:PT0M', 'ACTION:DISPLAY', 'DESCRIPTION:' + _ics_text('核实并预约：' + task['name']),
                  'END:VALARM', 'END:VEVENT']
    return '\r\n'.join(_fold(line) for line in lines + ['END:VCALENDAR']) + '\r\n'

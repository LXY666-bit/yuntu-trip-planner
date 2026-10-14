from typing import Literal
from fastapi import APIRouter, Response
from pydantic import BaseModel, StrictBool
from ...services import reservations as service

router = APIRouter(prefix='/reservations', tags=['预约待办'])


class BookingUpdate(BaseModel):
    booked: StrictBool


@router.get('/{kind}/{ident}')
async def checklist(kind: Literal['draft', 'trip'], ident: str):
    _, days = await service.load_scope(kind, ident)
    return {'tasks': service.reservation_tasks(days), 'timezone': 'Asia/Shanghai'}


@router.patch('/{kind}/{ident}/{key}')
async def mark_booked(kind: Literal['draft', 'trip'], ident: str, key: str, body: BookingUpdate):
    tasks = await service.set_booked(kind, ident, key, body.booked)
    return {'tasks': tasks, 'timezone': 'Asia/Shanghai'}


@router.get('/{kind}/{ident}/calendar.ics')
async def export_calendar(kind: Literal['draft', 'trip'], ident: str):
    _, days = await service.load_scope(kind, ident)
    return Response(service.calendar(service.reservation_tasks(days), f'{kind}:{ident}'),
                    media_type='text/calendar; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="yuntu-reservations.ics"'})

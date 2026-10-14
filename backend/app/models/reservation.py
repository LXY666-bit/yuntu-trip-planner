"""Reservation evidence is advisory; absence is never evidence of no reservation."""
from datetime import date
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator


class ReservationInfo(BaseModel):
    status: Literal['required', 'not_required', 'unknown', 'conflicting'] = 'unknown'
    advance_days: int | None = Field(default=None, ge=0, le=365)
    release_time: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    channel: str = Field(default='', max_length=500)
    tips: str = Field(default='', max_length=2000)
    evidence: str = Field(default='', max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_title: str = Field(default='', max_length=300)
    captured_at: str | None = None

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, value):
        if not value:
            return None
        parsed = urlparse(value)
        return value if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username else None


class ReservationFields(BaseModel):
    reservation: ReservationInfo = Field(default_factory=ReservationInfo)
    reservation_required: bool | None = None
    reservation_tips: str = ''
    reservation_booked_for: date | None = None

    @model_validator(mode='before')
    @classmethod
    def legacy_reservation(cls, data):
        if isinstance(data, dict) and data.get('reservation_tips') is None:
            data = {**data, 'reservation_tips': ''}
        if isinstance(data, dict) and not data.get('reservation'):
            data = dict(data)
            # Old false defaults did not mean verified "not required".
            data['reservation'] = {'status': 'required' if data.get('reservation_required') is True else 'unknown',
                                   'tips': data.get('reservation_tips') or ''}
        return data

    @model_validator(mode='after')
    def compatibility_fields(self):
        self.reservation_required = {'required': True, 'not_required': False}.get(self.reservation.status)
        self.reservation_tips = self.reservation.tips
        return self


def reservation_fields(data: dict) -> dict:
    """Copy only reservation fields through existing POI conversion boundaries."""
    return ReservationFields.model_validate(data).model_dump(mode='json')

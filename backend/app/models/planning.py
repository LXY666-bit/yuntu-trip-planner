"""Validation and human-confirmed edit contracts. No free-form executable operations."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from .schemas import DayDetail


class Violation(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    day_index: int | None = None
    subject: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    violations: list[Violation] = Field(default_factory=list)
    total_cost: int = 0
    pricing_status: str = "estimated"
    day_minutes: dict[int, int] = Field(default_factory=dict)
    poi_verifiable_rate: float = 0.0


class EditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_index: int = Field(ge=0, le=29)
    instruction: str = Field(min_length=1, max_length=1500)
    indoor_only: bool = False


class DayPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_index: int = Field(ge=0, le=29)
    attraction_ids: list[str] = Field(min_length=1, max_length=12)
    day_start_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    reason: str = Field(default="", max_length=1000)


class ProposalRequest(BaseModel):
    message: str = Field(default="", max_length=1500)
    day_index: int | None = Field(default=None, ge=0, le=29)
    repair: bool = False


class EditProposal(BaseModel):
    proposal_id: str
    draft_id: str
    status: str
    before: dict[int, DayDetail]
    after: dict[int, DayDetail]
    validation_before: ValidationReport
    validation_after: ValidationReport
    changes: list[str]
    rounds: int
    message: str
    run_id: str | None = None


class ConfirmProposal(BaseModel):
    confirmed: Literal[True]
    remember_preferences: bool = False

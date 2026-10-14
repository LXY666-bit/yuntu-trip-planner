from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from ...database import async_session
from ...models.db_models import TripDraft
from ...models.schemas import TripRequest
from ...models.planning import ProposalRequest, EditProposal, ConfirmProposal, ValidationReport
from ...services import planning_assistant as assistant
from ...services.plan_validation import validate_plan

router = APIRouter(prefix="/trip/draft", tags=["规划校验与对话编辑"])


@router.get("/{draft_id}/validation", response_model=ValidationReport)
async def validation(draft_id: str):
    record = await assistant.require_draft(draft_id)
    request, days = assistant.current_days(record)
    return validate_plan(request, days)


class ConstraintsRequest(BaseModel):
    must_visit: list[str] = Field(default_factory=list, max_length=30)
    max_day_minutes: int = Field(default=600, ge=60, le=960)
    budget: int | None = Field(default=None, ge=0)
    day_end_time: str = Field(default="22:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@router.put("/{draft_id}/constraints")
async def constraints(draft_id: str, command: ConstraintsRequest):
    record = await assistant.require_draft(draft_id)
    request = TripRequest.model_validate_json(record.request_json)
    request = TripRequest.model_validate({**request.model_dump(), **command.model_dump()})
    async with async_session() as session:
        result = await session.execute(update(TripDraft).where(
            TripDraft.id == draft_id, TripDraft.status != "finalized",
            TripDraft.request_json == record.request_json,
        ).values(request_json=request.model_dump_json()))
        if result.rowcount != 1:
            raise HTTPException(409, "行程要求已变化，请刷新")
        await session.commit()
    return request


@router.post("/{draft_id}/proposals", response_model=EditProposal)
async def propose(draft_id: str, command: ProposalRequest):
    try:
        return await assistant.create_proposal(draft_id, command)
    except assistant.PlanConflict:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{draft_id}/proposals/{proposal_id}", response_model=EditProposal)
async def read(draft_id: str, proposal_id: str):
    return await assistant.get_proposal(draft_id, proposal_id)


@router.post("/{draft_id}/proposals/{proposal_id}/confirm", response_model=EditProposal)
async def confirm(draft_id: str, proposal_id: str, command: ConfirmProposal):
    return await assistant.confirm_proposal(draft_id, proposal_id, command.remember_preferences)


@router.delete("/{draft_id}/proposals/{proposal_id}")
async def cancel(draft_id: str, proposal_id: str):
    await assistant.cancel_proposal(draft_id, proposal_id)
    return {"success": True}

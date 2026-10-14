import json
from pathlib import Path
import pytest
from app.models.schemas import TripRequest, DayDetail
from app.services.plan_validation import validate_plan

CASES = json.loads((Path(__file__).parents[2]/"evals/cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_frozen_case_exposes_expected_baseline_problem(case):
    report = validate_plan(TripRequest.model_validate(case["request"]),
                           [DayDetail.model_validate(day) for day in case["synthetic_direct_response"]["days"]])
    assert set(case["expected_baseline_codes"]) <= {v.code for v in report.violations}
    if case["id"].startswith("normal"):
        assert report.valid

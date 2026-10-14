"""Offline fixture regression or opt-in live-model ablation on frozen tool data.

Run from backend: python -m evals.run_eval --mode fixture --output evals/results/fixture.json
Fixture replies are synthetic test doubles, NOT captured production/model responses.
"""
import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch


async def evaluate_case(case, mode):
    from langchain_core.messages import AIMessage
    from app.database import init_db
    from app.models.schemas import TripRequest, DayDetail, MacroPlan
    from app.models.planning import ProposalRequest
    from app.services import trip_draft_service as drafts, planning_assistant as assistant
    from app.services.plan_validation import validate_plan
    from app.services.run_metrics import RunMetrics, current_run
    from app.agents.langgraph_agent.nodes import generate
    from app.agents.langgraph_agent.assemble.timeline import rule_assemble_day_timeline
    from app.agents.langgraph_agent.finalize.pipeline import _build_day_context

    await init_db()
    request = TripRequest.model_validate(case["request"])
    frozen_days = [DayDetail.model_validate(d) for d in case["synthetic_direct_response"]["days"]]
    candidates = [assistant.candidate_from_dict(d) for d in case["frozen_candidates"]]
    clusters = [[{**a.model_dump(mode="json"), "longitude": a.location.longitude if a.location else None,
                   "latitude": a.location.latitude if a.location else None, "visit_minutes": a.visit_duration}
                 for a in d.attractions] for d in frozen_days]
    macro_data = {"city": request.city, "total_days": request.travel_days,
                  "days": [{"day_index": d.day_index, "date": d.date,
                            "attraction_names": [a.name for a in d.attractions]} for d in frozen_days]}
    outputs = []
    for variant in ("direct", "workflow", "validated"):
        metrics = RunMetrics()
        token = current_run.set(metrics)
        started = time.perf_counter()
        failure = None
        rounds, degraded = 0, False
        first_editable_ms = None
        try:
            if variant == "direct":
                if mode == "live":
                    response = await assistant.model_json(
                        "根据请求和候选生成完整行程，输出JSON对象days数组，使用给定DayDetail schema。不要编造候选。",
                        {"request": request.model_dump(), "candidates": case["frozen_candidates"],
                         "schema": DayDetail.model_json_schema()},
                    )
                    days = [DayDetail.model_validate(d) for d in response["days"]]
                else:
                    days = frozen_days
            else:
                state = {"request": request, "cluster_info": json.dumps(clusters, ensure_ascii=False), "hotels_info": "", "user_preferences": None}
                if mode == "fixture":
                    fake_llm = AsyncMock()
                    fake_llm.ainvoke.return_value = AIMessage(content=json.dumps(macro_data, ensure_ascii=False))
                    with patch.object(generate, "get_llm", return_value=fake_llm), patch.object(generate, "is_structured_output_supported", return_value=False):
                        macro = (await generate.macro_planner_node(state))["macro_plan"]
                else:
                    macro = (await generate.macro_planner_node(state))["macro_plan"]
                hotels = [[d.hotel.model_dump()] if d.hotel else [] for d in frozen_days]
                days = [rule_assemble_day_timeline(_build_day_context(i, macro, clusters, hotels,
                        [{}]*request.travel_days, [], request.default_day_start_time)) for i in range(request.travel_days)]
                # Frozen route outputs are identical across all variants.
                for d, frozen in zip(days, frozen_days):
                    d.route_segments = frozen.route_segments
                first_editable_ms = round((time.perf_counter() - started) * 1000, 2)
                if variant == "validated":
                    ident = await drafts.create_draft(user_id="evaluation", request=request,
                        selected_attractions=[], macro_plan=macro, clusters_data=clusters,
                        hotels_by_day=hotels, dining_pool=[{}]*request.travel_days, weather_info=[])
                    for i, d in enumerate(days):
                        await drafts.patch_day_detail(ident, i, d)
                    if not validate_plan(request, days).valid:
                        async def fixed_route(day, *args):
                            return case.get("frozen_routes", [])
                        retrieval = AsyncMock(return_value=candidates)
                        if case.get("fault") == "retrieval_timeout":
                            retrieval.side_effect = TimeoutError("fixture fault")
                            degraded = True
                        with contextlib.ExitStack() as stack:
                            stack.enter_context(patch.object(assistant, "retrieve_candidates", retrieval))
                            stack.enter_context(patch.object(assistant, "compute_day_route", fixed_route))
                            if mode == "fixture":
                                async def fixture_reply(system, payload):
                                    index = payload["day"]["day_index"]
                                    return {"day_index": index, "attraction_ids": case["synthetic_repair_ids"], "reason": "synthetic fixture response"}
                                stack.enter_context(patch.object(assistant, "model_json", fixture_reply))
                            result = await assistant.create_proposal(ident, ProposalRequest(repair=True))
                        rounds = result.rounds
                        if result.status == "pending":
                            # Score the proposal without claiming it was user approved.
                            for i, day in result.after.items():
                                days[i] = day
                        elif result.validation_after.valid:
                            degraded = True
            report = validate_plan(request, days)
        except Exception as exc:
            failure = type(exc).__name__
            report = None
        finally:
            current_run.reset(token)
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        cost = None
        if metrics.token_usage_known and os.getenv("LLM_INPUT_CNY_PER_MILLION") and os.getenv("LLM_OUTPUT_CNY_PER_MILLION"):
            cost = (metrics.input_tokens * float(os.environ["LLM_INPUT_CNY_PER_MILLION"]) + metrics.output_tokens * float(os.environ["LLM_OUTPUT_CNY_PER_MILLION"])) / 1e6
        outputs.append({"case_id": case["id"], "variant": variant, "mode": mode,
                        "constraint_pass": bool(report and report.valid),
                        "violations": [v.model_dump() for v in report.violations] if report else [],
                        "poi_verifiable_rate": report.poi_verifiable_rate if report else 0,
                        "elapsed_ms": elapsed, "first_editable_ms": first_editable_ms if first_editable_ms is not None else elapsed,
                        "llm_calls": metrics.llm_calls if mode == "live" else None,
                        "input_tokens": metrics.input_tokens if metrics.token_usage_known else None,
                        "output_tokens": metrics.output_tokens if metrics.token_usage_known else None,
                        "estimated_llm_cost_cny": cost, "repair_rounds": rounds,
                        "injected_fault": case.get("fault"), "degraded": degraded, "failure": failure})
    return outputs


async def run(args):
    cases = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[:args.limit]
    all_results = []
    for repeat in range(args.repeat):
        for case in cases:
            # Keep verbose legacy node output out of the evaluation summary.
            with contextlib.redirect_stdout(io.StringIO()):
                results = await evaluate_case(case, args.mode)
            for result in results:
                result["repeat"] = repeat
            all_results.extend(results)
            print(f"{case['id']}: " + ", ".join(f"{r['variant']}={r['constraint_pass']}" for r in results))
    summary = {}
    for variant in ("direct", "workflow", "validated"):
        rows = [r for r in all_results if r["variant"] == variant]
        times = sorted(r["elapsed_ms"] for r in rows)
        summary[variant] = {"cases": len(rows), "constraint_pass_rate": sum(r["constraint_pass"] for r in rows)/len(rows),
                            "poi_verifiable_rate": statistics.mean(r["poi_verifiable_rate"] for r in rows),
                            "p50_ms": statistics.median(times), "p95_ms": times[min(len(times)-1, int(len(times)*.95))],
                            "system_failures": sum(bool(r["failure"]) for r in rows)}
    document = {"mode": args.mode, "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),
                "planner_source_sha256": hashlib.sha256((Path(__file__).parents[1]/"app/agents/langgraph_agent/nodes/generate.py").read_bytes()).hexdigest(),
                "scope": "Frozen tool inputs; skeleton/assembly/validation comparison, not full discovery latency.",
                "warning": "Synthetic fixture replies validate engineering only; not measured model quality or cost." if args.mode == "fixture" else "Live model, frozen external data; not real-time provider availability.",
                "summary": summary, "results": all_results}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    parser.add_argument("--dataset", default=str(Path(__file__).with_name("cases.json")))
    parser.add_argument("--output", default="evals/results/fixture.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1 or args.limit is not None and args.limit < 1:
        parser.error("repeat and limit must be positive")
    with tempfile.TemporaryDirectory(prefix="yuntu-eval-", ignore_cleanup_errors=True) as temp:
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + (Path(temp)/"eval.db").as_posix()
        os.environ["RUN_METRICS_PATH"] = str(Path(temp)/"metrics.jsonl")
        asyncio.run(run(args))

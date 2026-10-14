"""Per-run metadata, without prompts, credentials or model reasoning."""
import asyncio
import json
import os
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from pathlib import Path
from langchain_core.callbacks import BaseCallbackHandler


@dataclass
class RunMetrics:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    tool_calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_known: bool = False
    degraded: bool = False
    first_usable_ms: float | None = None
    events: list[dict] = field(default_factory=list)


current_run: ContextVar[RunMetrics | None] = ContextVar("planning_run", default=None)


def mark_tool(retry=False):
    run = current_run.get()
    if run:
        run.tool_calls += 1
        run.retries += int(retry)


class MetricsCallback(BaseCallbackHandler):
    run_inline = True

    def on_tool_start(self, serialized, input_str, **kwargs):
        mark_tool()

    def on_tool_error(self, error, **kwargs):
        run = current_run.get()
        if run:
            run.degraded = True

    def on_chat_model_start(self, serialized, messages, **kwargs):
        run = current_run.get()
        if run:
            run.llm_calls += 1

    def on_llm_end(self, response, **kwargs):
        run = current_run.get()
        if not run:
            return
        usage = (response.llm_output or {}).get("token_usage") or {}
        if not usage and response.generations:
            usage = getattr(response.generations[0][0].message, "usage_metadata", None) or {}
        if usage:
            run.token_usage_known = True
            run.input_tokens += usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
            run.output_tokens += usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0

    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kwargs):
        run = current_run.get()
        if run and metadata and metadata.get("langgraph_node"):
            run.events.append({"id": str(run_id), "node": metadata["langgraph_node"], "start": time.monotonic()})

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        run = current_run.get()
        if run:
            for event in reversed(run.events):
                if event["id"] == str(run_id):
                    event["elapsed_ms"] = round((time.monotonic() - event.pop("start", time.monotonic())) * 1000, 2)
                    break
            if isinstance(outputs, dict) and outputs.get("errors"):
                run.degraded = True


METRICS_CALLBACK = MetricsCallback()


def _save(payload):
    path = Path(os.getenv("RUN_METRICS_PATH", str(Path(__file__).parents[2] / "data" / "run_metrics.jsonl")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


class RunMetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        run = RunMetrics()
        token = current_run.set(run)
        status = 500
        outcome = "completed"
        async def capture(message):
            nonlocal status, outcome
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = list(message.get("headers", [])) + [(b"x-run-id", run.run_id.encode())]
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    # SSE producer sends complete events as one frame in this application.
                    for line in body.splitlines():
                        if line.startswith(b"data:"):
                            try:
                                event = json.loads(line[5:])
                                if event.get("type") == "error":
                                    outcome = "failed"
                                if event.get("type") in ("attraction", "complete") and run.first_usable_ms is None:
                                    run.first_usable_ms = round((time.monotonic() - run.started) * 1000, 2)
                            except (ValueError, AttributeError):
                                pass
            await send(message)
        try:
            await self.app(scope, receive, capture)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            raise
        finally:
            payload = asdict(run)
            payload.pop("started")
            payload.update(path=scope["path"], status=status, outcome="failed" if status >= 400 else outcome,
                           elapsed_ms=round((time.monotonic() - run.started) * 1000, 2))
            # Prices are operator supplied; no made-up default price or unknown == zero.
            prices = (os.getenv("LLM_INPUT_CNY_PER_MILLION"), os.getenv("LLM_OUTPUT_CNY_PER_MILLION"))
            payload["estimated_llm_cost_cny"] = None
            try:
                if all(prices) and run.token_usage_known:
                    payload["estimated_llm_cost_cny"] = round((run.input_tokens * float(prices[0]) + run.output_tokens * float(prices[1])) / 1e6, 6)
                await asyncio.to_thread(_save, payload)
            except (OSError, ValueError):
                pass
            current_run.reset(token)

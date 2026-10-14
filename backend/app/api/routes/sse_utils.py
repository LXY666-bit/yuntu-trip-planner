"""SSE 流式响应工具"""

import asyncio
import json
from contextlib import suppress
from typing import AsyncGenerator, Callable, Any

from fastapi.responses import StreamingResponse


async def heartbeat_wrapper(
    event_generator: Callable[[], AsyncGenerator[str, None]],
    heartbeat_interval: float = 15.0,
) -> AsyncGenerator[str, None]:
    """等待业务事件期间保活；EOF、取消或断连时关闭生产者。"""
    source = event_generator()
    pending = None
    try:
        pending = asyncio.create_task(anext(source))
        while True:
            done, _ = await asyncio.wait({pending}, timeout=heartbeat_interval)
            if not done:
                yield ": heartbeat\n\n"
                continue
            try:
                chunk = pending.result()
            except StopAsyncIteration:
                return
            yield chunk
            pending = asyncio.create_task(anext(source))
    finally:
        if pending is not None:
            pending.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        await source.aclose()


def make_sse_response(
    event_gen_factory: Callable[[], AsyncGenerator[str, None]],
    heartbeat_interval: float = 15.0,
) -> StreamingResponse:
    """创建带心跳的 SSE StreamingResponse"""

    async def wrapped():
        async for chunk in heartbeat_wrapper(event_gen_factory, heartbeat_interval):
            yield chunk

    return StreamingResponse(
        wrapped(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


def sse_event(data: Any) -> str:
    """将数据序列化为 SSE 事件行"""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def sse_error(message: str, extra: dict = None) -> str:
    """构建 SSE 错误事件"""
    event = {"type": "error", "message": message, "progress": 0}
    if extra:
        event.update(extra)
    return sse_event(event)

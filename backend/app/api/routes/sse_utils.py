"""SSE 流式响应工具"""

import asyncio
import json
from typing import AsyncGenerator, Callable, Any

from fastapi.responses import StreamingResponse


async def heartbeat_wrapper(
    event_generator: Callable[[], AsyncGenerator[str, None]],
    heartbeat_interval: float = 15.0,
) -> AsyncGenerator[str, None]:
    """在 SSE 事件流末尾添加心跳注释，保持连接活跃"""
    async for chunk in event_generator():
        yield chunk
    while True:
        await asyncio.sleep(heartbeat_interval)
        yield ": heartbeat\n\n"


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

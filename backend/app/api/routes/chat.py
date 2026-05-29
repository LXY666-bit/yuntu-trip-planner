"""AI 行程问答路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ...services.chat_service import chat_with_trip_context

router = APIRouter(prefix="/chat", tags=["AI问答"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="角色: user / assistant")
    content: str = Field(..., description="消息内容")


class TripChatRequest(BaseModel):
    message: str = Field(..., description="用户提问内容")
    trip_plan: dict = Field(..., description="当前旅行计划(JSON对象)")
    history: Optional[List[ChatMessage]] = Field(default=[], description="历史对话记录")


class TripChatResponse(BaseModel):
    success: bool = Field(default=True, description="是否成功")
    reply: str = Field(..., description="AI回复内容")


@router.post(
    "/ask",
    response_model=TripChatResponse,
    summary="行程智能问答",
    description="根据当前旅行计划上下文,回答用户关于行程的问题"
)
async def ask_about_trip(request: TripChatRequest):
    """
    AI 行程问答

    Args:
        request: 包含用户提问、旅行计划上下文和历史对话

    Returns:
        AI 回复
    """
    try:
        print(f"\n💬 收到行程问答: {request.message[:50]}...")

        history = [{"role": m.role, "content": m.content} for m in (request.history or [])]

        reply = await chat_with_trip_context(
            message=request.message,
            trip_plan_dict=request.trip_plan,
            history=history,
        )

        print(f"✅ AI 回复: {reply[:80]}...")

        return TripChatResponse(
            success=True,
            reply=reply,
        )

    except Exception as e:
        print(f"❌ 行程问答失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"AI问答服务异常: {str(e)}"
        )

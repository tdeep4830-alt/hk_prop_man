"""POST /api/v1/chat — SSE streaming RAG chat endpoint."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.logger import logger
from app.core.security import get_current_user
from app.db.session import async_session_factory
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.security.auth_service import check_quota, increment_usage

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    """Stream a RAG-powered response via Server-Sent Events.

    The DB session from get_db would close before streaming finishes,
    so we create a dedicated session inside the generator that lives
    for the entire stream lifecycle.
    """
    # Pre-check: quota validation using the auth dependency's session
    # We need a quick session just for quota check + increment
    async with async_session_factory() as quota_db:
        await check_quota(user, quota_db)
        await increment_usage(user.id, quota_db)
        await quota_db.commit()

    async def event_generator() -> AsyncIterator[str]:
        # Import here to avoid circular imports at module level
        from app.services.ai.rag_chain import RAGChain

        async with async_session_factory() as stream_db:
            try:
                async for event in RAGChain.astream(
                    query=body.message,
                    user=user,
                    conv_id=body.conversation_id,
                    db=stream_db,
                ):
                    yield event
            except Exception as e:
                logger.error("Chat stream error", extra={"error": str(e), "user_id": str(user.id)})
                yield f"event: error\ndata: 系統錯誤，請稍後再試。\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

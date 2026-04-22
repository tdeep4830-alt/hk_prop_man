"""POST /api/v1/chat — SSE streaming RAG chat endpoint."""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.logger import logger
from app.core.security import get_current_user
from app.db.session import async_session_factory, get_db
from app.models.chat import Conversation, Message, MessageRole
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.security.auth_service import check_quota, increment_usage
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["chat"])


# ── Response schemas ───────────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list | None = None
    created_at: str


# ── GET /chat/conversations ────────────────────────────────────────────────────

@router.get("/chat/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's conversations, newest first.

    Title is derived from the first user message in each conversation.
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()

    out = []
    for conv in convs:
        # Fetch first user message for title
        msg_result = await db.execute(
            select(Message)
            .where(Message.conv_id == conv.id, Message.role == MessageRole.USER)
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        first_msg = msg_result.scalar_one_or_none()
        title = (first_msg.content[:28] + "…" if first_msg and len(first_msg.content) > 28
                 else first_msg.content if first_msg else "新對話")
        out.append(ConversationSummary(
            id=str(conv.id),
            title=title,
            created_at=conv.created_at.isoformat(),
        ))
    return out


# ── GET /chat/conversations/{conv_id}/messages ─────────────────────────────────

@router.get("/chat/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conv_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all messages for a conversation owned by the current user."""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conv_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    msgs = msg_result.scalars().all()
    return [
        MessageOut(
            id=str(m.id),
            role=m.role.value,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]


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

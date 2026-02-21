"""DB-backed conversation memory for multi-turn chat."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import Conversation, Message, MessageRole, Platform


class ConversationMemory:
    """Manage conversation sessions and message history."""

    @staticmethod
    async def get_or_create_conversation(
        user_id: uuid.UUID,
        conv_id: uuid.UUID | None,
        platform: str,
        db: AsyncSession,
    ) -> Conversation:
        if conv_id:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conv_id,
                    Conversation.user_id == user_id,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conv = Conversation(
            user_id=user_id,
            platform=Platform(platform) if platform in Platform._value2member_map_ else Platform.WEB,
        )
        db.add(conv)
        await db.flush()
        return conv

    @staticmethod
    async def save_user_message(
        conv_id: uuid.UUID,
        content: str,
        db: AsyncSession,
    ) -> Message:
        msg = Message(conv_id=conv_id, role=MessageRole.USER, content=content)
        db.add(msg)
        await db.flush()
        return msg

    @staticmethod
    async def save_assistant_message(
        conv_id: uuid.UUID,
        content: str,
        citations: list[dict] | None,
        db: AsyncSession,
    ) -> Message:
        msg = Message(
            conv_id=conv_id,
            role=MessageRole.ASSISTANT,
            content=content,
            citations=citations,
        )
        db.add(msg)
        await db.flush()
        return msg

    @staticmethod
    async def get_history(
        conv_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[Message]:
        max_messages = settings.RAG_MAX_HISTORY_TURNS * 2
        result = await db.execute(
            select(Message)
            .where(Message.conv_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    @staticmethod
    def format_history_for_prompt(messages: list[Message]) -> str:
        if not messages:
            return "（無先前對話記錄）"
        lines = []
        for msg in messages:
            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)

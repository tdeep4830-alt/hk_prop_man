"""Chat request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    platform: str = "web"


class CitationItem(BaseModel):
    parent_id: str
    doc_type: str
    title: str
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    """Non-streaming fallback response."""

    conversation_id: UUID
    intent: str
    content: str
    citations: list[CitationItem] = []
    disclaimer: str
    follow_ups: list[str] = []

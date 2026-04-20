"""Admin-only endpoints for RAG query log inspection."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import MembershipTier, User

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Admin guard dependency
# ---------------------------------------------------------------------------
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.membership_tier != MembershipTier.ENTERPRISE:
        raise AppException(403, "error.forbidden")
    return user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChunkDetail(BaseModel):
    child_id:       str | None
    parent_id:      str | None
    combined_score: float
    doc_type:       str


class QueryLogEntry(BaseModel):
    id:             UUID
    user_id:        UUID | None
    user_email:     str | None
    created_at:     datetime
    masked_query:   str | None
    original_query: str | None
    pii_types:      list[str]
    intent:         str | None
    complexity:     str | None
    category:       str | None
    latency_ms:     int | None
    llm_model:      str | None
    chunks:         list[ChunkDetail]
    chunk_count:    int


class QueryLogPage(BaseModel):
    total:   int
    page:    int
    limit:   int
    entries: list[QueryLogEntry]


# ---------------------------------------------------------------------------
# GET /api/v1/admin/query-logs
# ---------------------------------------------------------------------------
@router.get("/query-logs", response_model=QueryLogPage)
async def get_query_logs(
    page:        int = Query(1, ge=1),
    limit:       int = Query(20, ge=1, le=100),
    intent:      str | None = Query(None),
    min_latency: int | None = Query(None, description="Min latency in ms"),
    _admin:      User = Depends(require_admin),
    db:          AsyncSession = Depends(get_db),
):
    """Return paginated RAG query audit logs with chunk scores."""
    offset = (page - 1) * limit

    # Base filter: only rag_query events
    base_where = AuditLog.action == "rag_query"

    # Optional intent filter (JSONB ->> operator)
    filters = [base_where]
    if intent:
        filters.append(AuditLog.detail["intent"].astext == intent)
    if min_latency is not None:
        filters.append(
            AuditLog.detail["latency_ms"].astext.cast(type_=None).cast(
                type_=None
            ) != None  # noqa: E711 — just existence check handled below
        )

    # Count
    count_q = select(func.count()).select_from(AuditLog).where(*filters)
    total = (await db.execute(count_q)).scalar_one()

    # Fetch logs
    log_q = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = (await db.execute(log_q)).scalars().all()

    # Collect user IDs to batch-fetch emails
    user_ids = {log.user_id for log in logs if log.user_id}
    email_map: dict[UUID, str] = {}
    if user_ids:
        users_q = select(User.id, User.email).where(User.id.in_(user_ids))
        for row in (await db.execute(users_q)).all():
            email_map[row.id] = row.email

    entries: list[QueryLogEntry] = []
    for log in logs:
        d = log.detail or {}
        raw_chunks = d.get("chunks", [])
        chunks = [
            ChunkDetail(
                child_id=str(c.get("child_id", "")),
                parent_id=str(c.get("parent_id", "")),
                combined_score=float(c.get("combined_score", 0)),
                doc_type=c.get("doc_type", ""),
            )
            for c in raw_chunks
        ]
        entries.append(
            QueryLogEntry(
                id=log.id,
                user_id=log.user_id,
                user_email=email_map.get(log.user_id) if log.user_id else None,
                created_at=log.created_at,
                masked_query=d.get("masked_query"),
                original_query=d.get("original_query"),
                pii_types=d.get("pii_types", []),
                intent=d.get("intent"),
                complexity=d.get("complexity"),
                category=d.get("category"),
                latency_ms=d.get("latency_ms"),
                llm_model=d.get("llm_model"),
                chunks=chunks,
                chunk_count=len(chunks),
            )
        )

    return QueryLogPage(total=total, page=page, limit=limit, entries=entries)

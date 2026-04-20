"""Observability logger writing RAG query telemetry to the AuditLog table."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.audit import AuditLog
from app.services.ai.retriever import RetrievedChunk


class TelemetryLogger:
    """Log RAG query metadata to AuditLog for compliance and debugging."""

    @staticmethod
    async def log_query(
        user_id: uuid.UUID,
        original_query: str,
        masked_query: str,
        pii_found: list[dict],
        retrieved_chunks: list[RetrievedChunk],
        intent: str,
        token_usage: dict | None,
        latency_ms: int,
        llm_model: str,
        db: AsyncSession,
        complexity: str | None = None,
        category: str | None = None,
    ) -> None:
        # PDPO: only store original query if no PII detected
        detail = {
            "masked_query": masked_query,
            "pii_types": [p["type"] for p in pii_found] if pii_found else [],
            "chunks": [
                {
                    "child_id": str(c.child_id),
                    "parent_id": str(c.parent_id),
                    "combined_score": round(c.combined_score, 4),
                    "doc_type": c.doc_type,
                }
                for c in retrieved_chunks
            ],
            "intent": intent,
            "complexity": complexity,
            "category": category,
            "latency_ms": latency_ms,
            "llm_model": llm_model,
            "token_usage": token_usage,
        }

        if not pii_found:
            detail["original_query"] = original_query

        audit = AuditLog(
            user_id=user_id,
            action="rag_query",
            detail=detail,
        )
        db.add(audit)
        await db.flush()

        logger.info(
            "RAG query logged",
            extra={"user_id": str(user_id), "intent": intent, "latency_ms": latency_ms},
        )

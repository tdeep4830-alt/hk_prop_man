"""Hybrid retriever combining vector similarity and keyword search.

Uses a single SQL query with CTEs to fuse cosine similarity (pgvector)
and ts_rank (full-text search) results with weighted combination.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.services.ingestion.embedding import EmbeddingService


@dataclass
class RetrievedChunk:
    child_id: str
    parent_id: str
    parent_content: str
    child_search_text: str
    vector_score: float
    keyword_score: float
    combined_score: float
    doc_type: str
    metadata: dict


_embedding_service = EmbeddingService()

# Weights for score fusion
_W_VECTOR = 0.7
_W_KEYWORD = 0.3

_HYBRID_SQL = text("""\
WITH vector_results AS (
    SELECT
        cc.id AS child_id,
        cc.parent_id,
        cc.search_text,
        1 - (cc.embedding <=> :query_vector::vector) AS vec_score
    FROM child_chunks cc
    ORDER BY cc.embedding <=> :query_vector::vector
    LIMIT :fetch_limit
),
keyword_results AS (
    SELECT
        pd.id AS parent_id,
        ts_rank(pd.search_vector, plainto_tsquery('simple', :query_text)) AS kw_score
    FROM parent_docs pd
    WHERE pd.search_vector @@ plainto_tsquery('simple', :query_text)
    ORDER BY kw_score DESC
    LIMIT :fetch_limit
),
combined AS (
    SELECT
        vr.child_id,
        vr.parent_id,
        vr.search_text AS child_search_text,
        pd.content AS parent_content,
        pd.doc_type,
        pd.metadata AS parent_metadata,
        vr.vec_score,
        COALESCE(kr.kw_score, 0) AS kw_score,
        (:w_vector * vr.vec_score + :w_keyword * COALESCE(kr.kw_score, 0)) AS combined_score
    FROM vector_results vr
    JOIN parent_docs pd ON pd.id = vr.parent_id
    LEFT JOIN keyword_results kr ON kr.parent_id = vr.parent_id
)
SELECT *
FROM combined
ORDER BY combined_score DESC
LIMIT :top_k
""")


class HybridRetriever:
    """Retrieve relevant chunks using vector + keyword fusion."""

    @staticmethod
    async def retrieve(
        query: str,
        db: AsyncSession,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        top_k = top_k or settings.RAG_TOP_K
        score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
        fetch_limit = top_k * 3

        query_vector = await _embedding_service.embed_single(query)
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        result = await db.execute(
            _HYBRID_SQL,
            {
                "query_vector": vector_str,
                "query_text": query,
                "fetch_limit": fetch_limit,
                "top_k": top_k,
                "w_vector": _W_VECTOR,
                "w_keyword": _W_KEYWORD,
            },
        )
        rows = result.mappings().all()

        chunks = []
        for row in rows:
            score = float(row["combined_score"])
            if score < score_threshold:
                continue
            chunks.append(
                RetrievedChunk(
                    child_id=str(row["child_id"]),
                    parent_id=str(row["parent_id"]),
                    parent_content=row["parent_content"],
                    child_search_text=row["child_search_text"],
                    vector_score=float(row["vec_score"]),
                    keyword_score=float(row["kw_score"]),
                    combined_score=score,
                    doc_type=row["doc_type"],
                    metadata=row["parent_metadata"] or {},
                )
            )

        logger.info(
            "Hybrid retrieval complete",
            extra={"query_len": len(query), "chunks_found": len(chunks), "top_k": top_k},
        )
        return chunks

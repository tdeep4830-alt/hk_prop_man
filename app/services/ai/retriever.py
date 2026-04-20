"""Hybrid retriever combining vector similarity and keyword search.

Bilingual dual-vector search:
  63% of indexed chunks are English (legislation + court cases exist in both
  languages). A Chinese query gets poor vector scores against English chunks.
  We fix this by running TWO parallel vector searches:
    1. Chinese HyDE vector  → catches Chinese chunks
    2. English HyDE vector  → catches English chunks
  Results are merged by parent_id, keeping the best combined_score per parent.

HyDE (Hypothetical Document Embedding):
  Instead of embedding the raw user query, ask the router LLM to generate
  a short hypothetical document passage (zh + en), then embed both.
  Bridges the style gap between conversational queries and formal legal text.
"""

import asyncio
from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.services.ai.prompts import HYDE_PROMPT_EN, HYDE_PROMPT_ZH
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
_W_VECTOR  = 0.7
_W_KEYWORD = 0.3


async def _hyde_embed(prompt_template: str, query: str) -> list[float]:
    """Generate a hypothetical document with given prompt, then embed it.

    Falls back to embedding the raw query on any LLM failure.
    """
    try:
        from app.services.ai.llm_provider import build_router_llm
        llm = build_router_llm()
        llm.max_tokens = 200
        response = await llm.ainvoke(
            [HumanMessage(content=prompt_template.format(query=query))]
        )
        hypothetical_doc = response.content.strip()
        if hypothetical_doc:
            return await _embedding_service.embed_single(hypothetical_doc)
    except Exception as e:
        logger.warning("HyDE failed, using raw query", extra={"error": str(e)})
    return await _embedding_service.embed_single(query)


_HYBRID_SQL = text("""\
WITH vector_results AS (
    SELECT
        cc.id   AS child_id,
        cc.parent_id,
        cc.search_text,
        1 - (cc.embedding <=> :query_vector) AS vec_score
    FROM child_chunks cc
    ORDER BY cc.embedding <=> :query_vector
    LIMIT :fetch_limit
),
keyword_results AS (
    SELECT
        pd.id AS parent_id,
        -- Normalise ts_rank to 0-1 range.
        -- Raw ts_rank is ~0.001-0.1; without normalisation it contributes
        -- almost nothing to the weighted sum against vec_score (0-1).
        -- Flag 32 = divide by document length.
        1 - 1.0 / (1 + ts_rank(pd.search_vector,
                                plainto_tsquery('simple', :query_text), 32) * 10) AS kw_score
    FROM parent_docs pd
    WHERE pd.search_vector @@ plainto_tsquery('simple', :query_text)
    ORDER BY kw_score DESC
    LIMIT :fetch_limit
),
combined AS (
    SELECT
        vr.child_id,
        vr.parent_id,
        vr.search_text          AS child_search_text,
        pd.content              AS parent_content,
        pd.doc_type,
        pd.metadata             AS parent_metadata,
        vr.vec_score,
        COALESCE(kr.kw_score, 0) AS kw_score,
        (:w_vector  * vr.vec_score +
         :w_keyword * COALESCE(kr.kw_score, 0)) AS combined_score
    FROM vector_results vr
    JOIN  parent_docs pd ON pd.id = vr.parent_id
    LEFT JOIN keyword_results kr ON kr.parent_id = vr.parent_id
)
SELECT * FROM combined
ORDER BY combined_score DESC
LIMIT :top_k
""").bindparams(bindparam("query_vector", type_=Vector(1536)))


async def _run_search(
    query_vector: list[float],
    query_text: str,
    fetch_limit: int,
    top_k: int,
    db: AsyncSession,
) -> list[dict]:
    """Execute one hybrid SQL search and return raw row mappings."""
    result = await db.execute(
        _HYBRID_SQL,
        {
            "query_vector": query_vector,
            "query_text":   query_text,
            "fetch_limit":  fetch_limit,
            "top_k":        top_k,
            "w_vector":     _W_VECTOR,
            "w_keyword":    _W_KEYWORD,
        },
    )
    return result.mappings().all()


class HybridRetriever:
    """Retrieve relevant chunks using bilingual vector + keyword fusion."""

    @staticmethod
    async def retrieve(
        query: str,
        db: AsyncSession,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        top_k           = top_k or settings.RAG_TOP_K
        score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
        fetch_limit     = top_k * 5  # fetch more to allow bilingual merge

        # ── Step 1: generate bilingual HyDE vectors in parallel ──────────────
        # Chinese HyDE → finds zh_hk chunks (37% of index)
        # English HyDE → finds en chunks    (63% of index)
        zh_vec, en_vec = await asyncio.gather(
            _hyde_embed(HYDE_PROMPT_ZH, query),
            _hyde_embed(HYDE_PROMPT_EN, query),
        )

        # ── Step 2: run both searches in parallel ─────────────────────────────
        # keyword search uses the original query text for both passes;
        # ts_rank('simple') works for both zh and en tokens.
        zh_rows, en_rows = await asyncio.gather(
            _run_search(zh_vec, query, fetch_limit, top_k * 2, db),
            _run_search(en_vec, query, fetch_limit, top_k * 2, db),
        )

        # ── Step 3: merge — keep best combined_score per parent_id ───────────
        best: dict[str, dict] = {}
        for row in list(zh_rows) + list(en_rows):
            pid   = str(row["parent_id"])
            score = float(row["combined_score"])
            if pid not in best or score > float(best[pid]["combined_score"]):
                best[pid] = dict(row)

        # ── Step 4: sort, threshold, truncate ────────────────────────────────
        ranked = sorted(best.values(), key=lambda r: r["combined_score"], reverse=True)

        chunks: list[RetrievedChunk] = []
        for row in ranked[:top_k]:
            score = float(row["combined_score"])
            if score < score_threshold:
                continue
            chunks.append(RetrievedChunk(
                child_id          = str(row["child_id"]),
                parent_id         = str(row["parent_id"]),
                parent_content    = row["parent_content"],
                child_search_text = row["child_search_text"],
                vector_score      = float(row["vec_score"]),
                keyword_score     = float(row["kw_score"]),
                combined_score    = score,
                doc_type          = row["doc_type"],
                metadata          = row["parent_metadata"] or {},
            ))

        logger.info(
            "Bilingual hybrid retrieval complete",
            extra={
                "query_len":    len(query),
                "zh_hits":      len(zh_rows),
                "en_hits":      len(en_rows),
                "merged":       len(best),
                "after_threshold": len(chunks),
                "top_k":        top_k,
            },
        )
        return chunks

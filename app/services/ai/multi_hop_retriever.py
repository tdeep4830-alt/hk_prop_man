"""Multi-hop retriever for complex, multi-aspect queries.

Strategy:
  Hop 1 — retrieve with the original query
  Extraction — lightweight LLM identifies information gaps as sub-queries
  Hop 2 — retrieve in parallel for each sub-query
  Merge — deduplicate by parent_id, keep highest combined_score
"""

import asyncio

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.services.ai.llm_provider import build_router_llm
from app.services.ai.prompts import SUBQUERY_EXTRACTION_PROMPT
from app.services.ai.retriever import HybridRetriever, RetrievedChunk

_MAX_SUBQUERIES = 3

_extraction_prompt = PromptTemplate.from_template(SUBQUERY_EXTRACTION_PROMPT)
_extraction_chain = _extraction_prompt | build_router_llm() | StrOutputParser()


async def _extract_subqueries(
    query: str, initial_chunks: list[RetrievedChunk]
) -> list[str]:
    """Ask the router LLM what additional information is still needed."""
    context_summary = "\n".join(
        f"- {c.metadata.get('title', '文件')}: {c.parent_content[:300]}"
        for c in initial_chunks[:4]
    )
    try:
        raw = await _extraction_chain.ainvoke(
            {"query": query, "context_summary": context_summary}
        )
        lines = [
            line.strip()
            for line in raw.strip().splitlines()
            if line.strip() and line.strip().lower() != "無"
        ]
        subqueries = lines[:_MAX_SUBQUERIES]
        logger.info(
            "Sub-queries extracted",
            extra={"count": len(subqueries), "subqueries": subqueries},
        )
        return subqueries
    except Exception as e:
        logger.warning("Sub-query extraction failed", extra={"error": str(e)})
        return []


def _merge_chunks(
    *chunk_lists: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Deduplicate by parent_id, keeping the highest combined_score per parent."""
    best: dict[str, RetrievedChunk] = {}
    for chunks in chunk_lists:
        for chunk in chunks:
            existing = best.get(chunk.parent_id)
            if existing is None or chunk.combined_score > existing.combined_score:
                best[chunk.parent_id] = chunk
    return sorted(best.values(), key=lambda c: c.combined_score, reverse=True)


class MultiHopRetriever:
    """Two-hop retrieval for hard queries requiring multi-step reasoning."""

    @staticmethod
    async def retrieve(
        query: str,
        db: AsyncSession,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        # Hop 1: retrieve with the original query
        hop1_chunks = await HybridRetriever.retrieve(query, db, top_k=top_k)

        if not hop1_chunks:
            logger.info("Multi-hop: hop 1 returned no chunks, stopping early")
            return []

        # Extract sub-queries based on what's missing from hop 1 context
        subqueries = await _extract_subqueries(query, hop1_chunks)

        if not subqueries:
            logger.info("Multi-hop: no sub-queries identified, returning hop 1 results")
            return hop1_chunks

        # Hop 2: retrieve in parallel for each sub-query
        hop2_tasks = [
            asyncio.create_task(HybridRetriever.retrieve(sq, db, top_k=top_k))
            for sq in subqueries
        ]
        hop2_results = await asyncio.gather(*hop2_tasks, return_exceptions=True)

        valid_hop2: list[list[RetrievedChunk]] = [
            r for r in hop2_results if isinstance(r, list)
        ]

        merged = _merge_chunks(hop1_chunks, *valid_hop2)

        logger.info(
            "Multi-hop retrieval complete",
            extra={
                "hop1_chunks": len(hop1_chunks),
                "hop2_lists": len(valid_hop2),
                "merged_total": len(merged),
            },
        )
        return merged

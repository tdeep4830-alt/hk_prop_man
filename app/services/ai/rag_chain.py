"""Main RAG orchestrator tying PII masking, retrieval, routing, LLM, and memory together.

Yields SSE events for streaming to the client.
"""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.models.user import User
from app.services.ai.llm_provider import build_chat_llm
from app.services.ai.memory import ConversationMemory
from app.services.ai.pii_masking import PIIMaskingService
from app.services.ai.prompts import (
    CATEGORY_SUFFIX_MAP,
    FOLLOW_UPS,
    INTENT_SUFFIX_MAP,
    LEGAL_DISCLAIMER,
    NO_CONTEXT_MESSAGE,
    SIMPLE_SYSTEM_PROMPT,
    SYSTEM_PROMPT_BASE,
)
from app.core.observability import (
    LLM_TOKENS_TOTAL,
    RAG_CATEGORY_TOTAL,
    RAG_COMPLEXITY_TOTAL,
    RAG_LATENCY,
    RAG_QUERY_TOTAL,
)
from app.services.ai.category import CATEGORY_LABELS, Category, CategoryClassifier
from app.services.ai.complexity import Complexity, ComplexityClassifier
from app.services.ai.multi_hop_retriever import MultiHopRetriever
from app.services.ai.retriever import HybridRetriever, RetrievedChunk
from app.services.ai.router import Intent, SemanticRouter
from app.services.ai.telemetry import TelemetryLogger


def _sse_event(event: str, data: str | dict) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as context for the system prompt."""
    if not chunks:
        return "（無相關參考資料）"
    parts = []
    for i, c in enumerate(chunks, 1):
        title = c.metadata.get("title", c.metadata.get("source", f"文件 {i}"))
        parts.append(f"[{i}] {title} ({c.doc_type})\n{c.parent_content[:1500]}")
    return "\n\n---\n\n".join(parts)


def _build_citations(chunks: list[RetrievedChunk]) -> list[dict]:
    """Extract citation metadata from retrieved chunks."""
    return [
        {
            "parent_id": c.parent_id,
            "doc_type": c.doc_type,
            "title": c.metadata.get("title", c.metadata.get("source", "")),
            "excerpt": c.parent_content[:200],
            "score": round(c.combined_score, 4),
        }
        for c in chunks
    ]


class RAGChain:
    """Full RAG pipeline with SSE streaming output."""

    @staticmethod
    async def astream(
        query: str,
        user: User,
        conv_id: uuid.UUID | None,
        db: AsyncSession,
    ) -> AsyncIterator[str]:
        start_time = time.monotonic()

        # 1. PII masking
        mask_result = PIIMaskingService.mask(query)
        masked_query = mask_result.masked_text

        # 2. Get/create conversation & save user message
        conv = await ConversationMemory.get_or_create_conversation(
            user.id, conv_id, "web", db
        )
        await ConversationMemory.save_user_message(conv.id, masked_query, db)
        await db.flush()

        yield _sse_event("conversation_id", {"conversation_id": str(conv.id)})

        # 3. Classify intent, complexity and domain category — all concurrent
        # asyncio.wait_for caps each at 12s so a slow/hung SiliconFlow call
        # cannot freeze the entire pipeline; classifiers fall back to defaults on timeout.
        intent_task = asyncio.create_task(SemanticRouter.classify(masked_query))
        complexity_task = asyncio.create_task(ComplexityClassifier.classify(masked_query))
        category_task = asyncio.create_task(CategoryClassifier.classify(masked_query))

        try:
            intent, complexity, category = await asyncio.wait_for(
                asyncio.gather(intent_task, complexity_task, category_task),
                timeout=12,
            )
        except asyncio.TimeoutError:
            logger.warning("Classifier tasks timed out, using defaults")
            intent_task.cancel()
            complexity_task.cancel()
            category_task.cancel()
            intent = Intent.LEGAL_DEFINITION
            complexity = Complexity.MEDIUM
            category = Category.OTHER

        yield _sse_event("intent", {"intent": intent.value})
        yield _sse_event("complexity", {"complexity": complexity.value})
        yield _sse_event(
            "category",
            {
                "category": category.value,
                "category_label": CATEGORY_LABELS[category],
            },
        )

        # 4. Adaptive retrieval based on complexity tier
        chunks: list[RetrievedChunk]
        if complexity == Complexity.SIMPLE:
            # No retrieval — answer directly from LLM parametric knowledge
            chunks = []
        elif complexity == Complexity.HARD:
            # Multi-hop: two retrieval rounds with sub-query decomposition
            chunks = await MultiHopRetriever.retrieve(masked_query, db)
        else:
            # Medium (default): standard single-step hybrid retrieval
            chunks = await HybridRetriever.retrieve(masked_query, db)

        # 5. Build prompt
        history_messages = await ConversationMemory.get_history(conv.id, db)
        # Exclude the user message we just saved (last one)
        history_for_prompt = history_messages[:-1] if history_messages else []
        chat_history_text = ConversationMemory.format_history_for_prompt(history_for_prompt)
        intent_suffix = INTENT_SUFFIX_MAP.get(intent.value, "")
        category_suffix = CATEGORY_SUFFIX_MAP.get(category.value, "")

        if complexity == Complexity.SIMPLE:
            # Simple path: use lightweight prompt without context block
            system_content = SIMPLE_SYSTEM_PROMPT.format(
                intent_suffix=intent_suffix,
                category_suffix=category_suffix,
                chat_history=chat_history_text,
            )
        else:
            # Anti-hallucination gate: if retrieval returned nothing, surface graceful message
            if not chunks:
                yield _sse_event("content", NO_CONTEXT_MESSAGE)
                yield _sse_event("disclaimer", LEGAL_DISCLAIMER)
                yield _sse_event(
                    "follow_ups",
                    {"suggestions": FOLLOW_UPS.get(intent.value, FOLLOW_UPS["legal_definition"])},
                )
                yield _sse_event("done", "")

                await ConversationMemory.save_assistant_message(
                    conv.id, NO_CONTEXT_MESSAGE, None, db
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)
                await TelemetryLogger.log_query(
                    user_id=user.id,
                    original_query=query,
                    masked_query=masked_query,
                    pii_found=mask_result.pii_found,
                    retrieved_chunks=[],
                    intent=intent.value,
                    token_usage=None,
                    latency_ms=latency_ms,
                    llm_model="none",
                    db=db,
                    complexity=complexity.value,
                    category=category.value,
                )
                await db.commit()
                return

            context_text = _build_context(chunks)
            system_content = SYSTEM_PROMPT_BASE.format(
                intent_suffix=intent_suffix,
                category_suffix=category_suffix,
                context=context_text,
                chat_history=chat_history_text,
            )

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=masked_query),
        ]

        # 6. Stream LLM response
        llm = build_chat_llm(streaming=True)
        full_response = ""
        llm_model_name = settings.LLM_PRIMARY_MODEL

        try:
            async for chunk in llm.astream(messages):
                token = chunk.content
                if token:
                    full_response += token
                    yield _sse_event("content", token)
        except Exception as e:
            logger.error("LLM streaming error", extra={"error": str(e)})
            error_msg = "抱歉，生成回答時發生錯誤，請稍後再試。"
            yield _sse_event("content", error_msg)
            full_response = error_msg

        # 7. Post-stream: citations, disclaimer, follow-ups
        citations = _build_citations(chunks)
        yield _sse_event("citations", {"citations": citations})
        yield _sse_event("disclaimer", LEGAL_DISCLAIMER)
        yield _sse_event(
            "follow_ups",
            {"suggestions": FOLLOW_UPS.get(intent.value, FOLLOW_UPS["legal_definition"])},
        )
        yield _sse_event("done", "")

        # 8. Save assistant message & telemetry
        await ConversationMemory.save_assistant_message(
            conv.id, full_response, citations, db
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Record custom Prometheus metrics
        RAG_QUERY_TOTAL.labels(
            intent=intent.value,
            membership_tier=user.membership_tier.value,
        ).inc()
        RAG_COMPLEXITY_TOTAL.labels(complexity=complexity.value).inc()
        RAG_CATEGORY_TOTAL.labels(category=category.value).inc()
        RAG_LATENCY.observe(latency_ms / 1000)

        await TelemetryLogger.log_query(
            user_id=user.id,
            original_query=query,
            masked_query=masked_query,
            pii_found=mask_result.pii_found,
            retrieved_chunks=chunks,
            intent=intent.value,
            token_usage=None,
            latency_ms=latency_ms,
            llm_model=llm_model_name,
            db=db,
            complexity=complexity.value,
            category=category.value,
        )
        await db.commit()

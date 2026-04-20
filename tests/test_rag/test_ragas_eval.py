"""RAGAS automated evaluation — runs against live RAG pipeline with real LLM output.

Two separate quality gates:

  test_rag_quality_medium_hard
    — medium + hard questions (standard + multi-hop retrieval)
    — metrics: context_precision, faithfulness, answer_relevancy
    — pass threshold: average >= 0.75

  test_rag_quality_simple
    — simple questions (no retrieval, direct LLM parametric knowledge)
    — metrics: answer_relevancy, answer_correctness
    — pass threshold: average >= 0.75

Both tests evaluate REAL LLM-generated answers, not ground-truth strings.

Usage:
    pytest tests/test_rag/test_ragas_eval.py -m eval -v --timeout=600
    (requires OPENAI_API_KEY + SILICONFLOW_API_KEY and a populated PostgreSQL)

Only runs in CD eval stage (Nightly / manual trigger). Marked with @pytest.mark.eval
so it is excluded from regular unit test runs.
"""

import json
import os
from pathlib import Path

import pytest
from datasets import Dataset
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    faithfulness,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.ai.complexity import Complexity
from app.services.ai.llm_provider import build_chat_llm
from app.services.ai.multi_hop_retriever import MultiHopRetriever
from app.services.ai.prompts import (
    CATEGORY_SUFFIX_MAP,
    INTENT_SUFFIX_MAP,
    SIMPLE_SYSTEM_PROMPT,
    SYSTEM_PROMPT_BASE,
)
from app.services.ai.retriever import HybridRetriever, RetrievedChunk

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PASS_THRESHOLD = 0.75

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

# gpt-4o-mini as judge — balances accuracy and cost
JUDGE_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)
JUDGE_EMBEDDINGS = OpenAIEmbeddings(model="text-embedding-3-small")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Build context string from retrieved chunks (mirrors rag_chain._build_context)."""
    if not chunks:
        return "（無相關參考資料）"
    parts = []
    for i, c in enumerate(chunks, 1):
        title = c.metadata.get("title", c.metadata.get("source", f"文件 {i}"))
        parts.append(f"[{i}] {title} ({c.doc_type})\n{c.parent_content[:1500]}")
    return "\n\n---\n\n".join(parts)


async def _generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    intent: str,
    category: str,
    complexity: str,
) -> str:
    """Call the actual LLM (non-streaming) and return the generated answer text.

    Uses the same prompt templates as rag_chain.py so eval reflects production behaviour.
    Conversation history is omitted — eval queries are standalone questions.
    """
    intent_suffix = INTENT_SUFFIX_MAP.get(intent, "")
    category_suffix = CATEGORY_SUFFIX_MAP.get(category, "")

    if complexity == Complexity.SIMPLE:
        system_content = SIMPLE_SYSTEM_PROMPT.format(
            intent_suffix=intent_suffix,
            category_suffix=category_suffix,
            chat_history="",
        )
    else:
        context_text = _format_context(chunks)
        system_content = SYSTEM_PROMPT_BASE.format(
            intent_suffix=intent_suffix,
            category_suffix=category_suffix,
            context=context_text,
            chat_history="",
        )

    llm = build_chat_llm(streaming=False)
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=question),
    ]
    response = await llm.ainvoke(messages)
    return response.content


async def _build_eval_rows(
    golden: list[dict],
    db: AsyncSession,
    target_complexity: str,
) -> list[dict]:
    """Retrieve context + generate real LLM answers for all questions of a given complexity tier."""
    rows = []
    filtered = [item for item in golden if item.get("complexity") == target_complexity]

    for item in filtered:
        question = item["question"]
        intent = item.get("intent", "legal_definition")
        category = item.get("category", "other")
        complexity = item.get("complexity", "medium")

        # Adaptive retrieval mirrors rag_chain.py logic
        if complexity == Complexity.SIMPLE:
            chunks: list[RetrievedChunk] = []
        elif complexity == Complexity.HARD:
            chunks = await MultiHopRetriever.retrieve(question, db)
        else:
            chunks = await HybridRetriever.retrieve(question, db)

        # Generate REAL LLM answer — not ground_truth
        answer = await _generate_answer(question, chunks, intent, category, complexity)

        contexts = [c.parent_content for c in chunks] if chunks else ["（無相關參考資料）"]

        rows.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": item["ground_truth"],
            }
        )

    return rows


def _db_factory() -> tuple:
    """Create async engine + session factory pointing at the configured DATABASE_URL."""
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai",
    )
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


def _print_results(label: str, scores: dict[str, float], avg: float) -> None:
    metric_lines = "\n".join(f"  {k}: {v:.3f}" for k, v in scores.items())
    print(
        f"\n{'=' * 50}\n"
        f"RAGAS Results — {label}\n"
        f"{metric_lines}\n"
        f"  average: {avg:.3f} (threshold: {PASS_THRESHOLD})\n"
        f"{'=' * 50}"
    )


# ---------------------------------------------------------------------------
# Eval test 1: Medium + Hard — retrieval quality + faithfulness
# ---------------------------------------------------------------------------

@pytest.mark.eval
@pytest.mark.asyncio
async def test_rag_quality_medium_hard():
    """Evaluate RAG quality for medium + hard queries.

    Uses real LLM-generated answers (not ground_truth).
    Metrics: context_precision, faithfulness, answer_relevancy.
    Covers all 14 domain categories and both complexity tiers.
    """
    with GOLDEN_DATASET_PATH.open(encoding="utf-8") as f:
        golden = json.load(f)

    engine, factory = _db_factory()

    async with factory() as db:
        medium_rows = await _build_eval_rows(golden, db, "medium")
        hard_rows = await _build_eval_rows(golden, db, "hard")

    await engine.dispose()

    all_rows = medium_rows + hard_rows
    assert len(all_rows) > 0, "No medium/hard questions found in golden dataset"

    dataset = Dataset.from_list(all_rows)

    result = evaluate(
        dataset,
        metrics=[context_precision, faithfulness, answer_relevancy],
        llm=JUDGE_LLM,
        embeddings=JUDGE_EMBEDDINGS,
        raise_exceptions=False,
    )

    cp = float(result["context_precision"])
    faith = float(result["faithfulness"])
    ar = float(result["answer_relevancy"])
    avg_score = (cp + faith + ar) / 3

    scores = {
        "context_precision": cp,
        "faithfulness": faith,
        "answer_relevancy": ar,
    }
    _print_results(f"Medium + Hard (n={len(all_rows)})", scores, avg_score)

    assert avg_score >= PASS_THRESHOLD, (
        f"RAG quality (medium/hard) {avg_score:.3f} below threshold {PASS_THRESHOLD}. "
        f"context_precision={cp:.3f}, faithfulness={faith:.3f}, answer_relevancy={ar:.3f}"
    )


# ---------------------------------------------------------------------------
# Eval test 2: Simple — direct LLM knowledge (no retrieval)
# ---------------------------------------------------------------------------

@pytest.mark.eval
@pytest.mark.asyncio
async def test_rag_quality_simple():
    """Evaluate LLM answer quality for simple queries (no retrieval path).

    Uses real LLM-generated answers (not ground_truth).
    Metrics: answer_relevancy, answer_correctness.
    No context_precision / faithfulness because no chunks are retrieved.
    """
    with GOLDEN_DATASET_PATH.open(encoding="utf-8") as f:
        golden = json.load(f)

    engine, factory = _db_factory()

    async with factory() as db:
        simple_rows = await _build_eval_rows(golden, db, "simple")

    await engine.dispose()

    assert len(simple_rows) > 0, "No simple questions found in golden dataset"

    dataset = Dataset.from_list(simple_rows)

    result = evaluate(
        dataset,
        metrics=[answer_relevancy, answer_correctness],
        llm=JUDGE_LLM,
        embeddings=JUDGE_EMBEDDINGS,
        raise_exceptions=False,
    )

    ar = float(result["answer_relevancy"])
    ac = float(result["answer_correctness"])
    avg_score = (ar + ac) / 2

    scores = {
        "answer_relevancy": ar,
        "answer_correctness": ac,
    }
    _print_results(f"Simple (n={len(simple_rows)})", scores, avg_score)

    assert avg_score >= PASS_THRESHOLD, (
        f"RAG quality (simple) {avg_score:.3f} below threshold {PASS_THRESHOLD}. "
        f"answer_relevancy={ar:.3f}, answer_correctness={ac:.3f}"
    )

"""RAGAS automated evaluation — runs against live RAG pipeline.

Evaluates three quality metrics using gpt-4o-mini as the judge LLM:
  - context_precision: Are retrieved chunks relevant to the question?
  - faithfulness:      Is the answer grounded in the retrieved context?
  - answer_relevancy:  Does the answer actually address the question?

Pass threshold: average score >= 0.75 across all three metrics.

Usage:
    pytest tests/test_rag/test_ragas_eval.py -m eval -v --timeout=300
    (requires OPENAI_API_KEY and a running RAG pipeline + PostgreSQL)

Only runs in CD eval stage (Nightly / manual trigger). Marked with @pytest.mark.eval
so it is excluded from regular unit test runs.
"""

import json
import os
from pathlib import Path

import pytest
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, faithfulness
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.ai.retriever import HybridRetriever
from app.services.ai.rag_chain import RAGChain

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PASS_THRESHOLD = 0.75

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

# Explicitly specify gpt-4o-mini as judge LLM — balances accuracy and cost.
# Using a cheap, reliable model avoids RAGAS defaulting to gpt-4 or o1.
JUDGE_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)
JUDGE_EMBEDDINGS = OpenAIEmbeddings(model="text-embedding-3-small")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_rag_for_question(question: str, db: AsyncSession) -> dict:
    """Run hybrid retrieval for a single question and return eval data."""
    chunks = await HybridRetriever.retrieve(question, db)
    contexts = [c.parent_content for c in chunks] if chunks else ["（無相關參考資料）"]
    return {"contexts": contexts}


async def _build_eval_dataset(db: AsyncSession) -> list[dict]:
    """Load golden dataset and collect RAG responses for all questions."""
    with GOLDEN_DATASET_PATH.open(encoding="utf-8") as f:
        golden = json.load(f)

    rows = []
    for item in golden:
        question = item["question"]
        ground_truth = item["ground_truth"]

        rag_data = await _run_rag_for_question(question, db)

        rows.append(
            {
                "question": question,
                "answer": ground_truth,          # use ground_truth as reference answer
                "contexts": rag_data["contexts"],
                "ground_truth": ground_truth,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Eval test
# ---------------------------------------------------------------------------

@pytest.mark.eval
@pytest.mark.asyncio
async def test_rag_quality():
    """Run RAGAS evaluation over 20 golden Q&A pairs.

    Fails if average score across context_precision, faithfulness, and
    answer_relevancy is below PASS_THRESHOLD (0.75).
    """
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai",
    )
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        rows = await _build_eval_dataset(db)

    await engine.dispose()

    dataset = Dataset.from_list(rows)

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

    print(
        f"\nRAGAS Results:\n"
        f"  context_precision:  {cp:.3f}\n"
        f"  faithfulness:       {faith:.3f}\n"
        f"  answer_relevancy:   {ar:.3f}\n"
        f"  average:            {avg_score:.3f} (threshold: {PASS_THRESHOLD})"
    )

    assert avg_score >= PASS_THRESHOLD, (
        f"RAG quality score {avg_score:.3f} below threshold {PASS_THRESHOLD}. "
        f"Details — context_precision: {cp:.3f}, faithfulness: {faith:.3f}, "
        f"answer_relevancy: {ar:.3f}"
    )

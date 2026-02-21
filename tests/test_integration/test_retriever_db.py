"""Integration tests for HybridRetriever — validates SQL correctness.

Tests that the CTE SQL (vector search + TSVector weighted fusion) executes
without errors against a real PostgreSQL + pgvector instance.
Does NOT test semantic quality — that is RAGAS's job.

Usage:
    pytest tests/test_integration/ -m integration -v
    (requires TEST_DATABASE_URL env var pointing to a real PostgreSQL)
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.knowledge import ChildChunk, DocType, ParentDoc
from app.services.ai.retriever import HybridRetriever, RetrievedChunk

# BGE-M3 produces 1024-dimensional vectors; use zero vector for SQL-correctness tests
FAKE_VECTOR = [0.0] * 1024
FAKE_PROPERTY_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def mock_embedding(mocker):
    """Mock embedding service so integration tests don't need the embedding model."""
    mock_embed = AsyncMock(return_value=FAKE_VECTOR)
    mocker.patch(
        "app.services.ai.retriever._embedding_service.embed_single",
        mock_embed,
    )
    return mock_embed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_returns_results(pg_session):
    """Insert mock docs, run hybrid search, verify no SQL errors + result structure."""
    # 1. Insert parent doc
    parent = ParentDoc(
        id=uuid.uuid4(),
        property_id=FAKE_PROPERTY_ID,
        content="業主立案法團可依第344章成立，享有法人地位。",
        doc_type=DocType.STATUTE,
        metadata_={"title": "Cap 344 第14條", "cap": "344"},
    )
    pg_session.add(parent)
    await pg_session.flush()

    # 2. Insert child chunk with fake embedding
    child = ChildChunk(
        id=uuid.uuid4(),
        parent_id=parent.id,
        embedding=FAKE_VECTOR,
        language="zh_hk",
        search_text="業主立案法團成立法人地位",
    )
    pg_session.add(child)
    await pg_session.commit()

    # 3. Run hybrid search — primarily validates SQL executes without error
    results = await HybridRetriever.retrieve("法團", pg_session)

    # 4. Validate return type and structure
    assert isinstance(results, list)
    if results:
        chunk = results[0]
        assert isinstance(chunk, RetrievedChunk)
        assert hasattr(chunk, "parent_id")
        assert hasattr(chunk, "combined_score")
        assert hasattr(chunk, "parent_content")
        assert hasattr(chunk, "vector_score")
        assert hasattr(chunk, "keyword_score")
        assert 0.0 <= chunk.combined_score <= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_empty_db(pg_session):
    """Retriever handles empty database gracefully (returns [])."""
    results = await HybridRetriever.retrieve("任何問題", pg_session)
    assert isinstance(results, list)
    assert results == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_multiple_docs(pg_session):
    """Insert multiple docs, verify retriever returns list and doesn't crash."""
    # Insert 3 parent docs
    parent_ids = []
    for i in range(3):
        parent = ParentDoc(
            id=uuid.uuid4(),
            property_id=FAKE_PROPERTY_ID,
            content=f"測試文件 {i}：業主立案法團相關條文內容",
            doc_type=DocType.STATUTE,
            metadata_={"title": f"測試條文 {i}"},
        )
        pg_session.add(parent)
        await pg_session.flush()
        parent_ids.append(parent.id)

        child = ChildChunk(
            id=uuid.uuid4(),
            parent_id=parent.id,
            embedding=FAKE_VECTOR,
            language="zh_hk",
            search_text=f"業主立案法團 測試 {i}",
        )
        pg_session.add(child)

    await pg_session.commit()

    results = await HybridRetriever.retrieve("業主立案法團", pg_session)
    assert isinstance(results, list)
    # Results should be bounded by top_k
    assert len(results) <= 5  # default RAG_TOP_K


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_score_threshold_filtering(pg_session):
    """Verify results below score threshold are excluded."""
    # Zero vector against zero vector produces well-defined cosine similarity (or 0),
    # so some results may be returned. Validate that returned scores meet threshold.
    parent = ParentDoc(
        id=uuid.uuid4(),
        property_id=FAKE_PROPERTY_ID,
        content="完全無關的測試內容",
        doc_type=DocType.INTERNAL,
        metadata_={"title": "測試"},
    )
    pg_session.add(parent)
    await pg_session.flush()

    child = ChildChunk(
        id=uuid.uuid4(),
        parent_id=parent.id,
        embedding=FAKE_VECTOR,
        language="zh_hk",
        search_text="完全無關",
    )
    pg_session.add(child)
    await pg_session.commit()

    results = await HybridRetriever.retrieve("複雜法律術語測試", pg_session)
    # All returned results must meet score threshold (default 0.35)
    from app.core.config import settings
    for r in results:
        assert r.combined_score >= settings.RAG_SCORE_THRESHOLD


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_returns_correct_doc_type(pg_session):
    """Verify doc_type is correctly populated in retrieved chunks."""
    parent = ParentDoc(
        id=uuid.uuid4(),
        property_id=FAKE_PROPERTY_ID,
        content="管理費追討程序：業主拖欠管理費，法團可向小額錢債審裁處追討。",
        doc_type=DocType.GUIDELINE,
        metadata_={"title": "管理費追討指引"},
    )
    pg_session.add(parent)
    await pg_session.flush()

    child = ChildChunk(
        id=uuid.uuid4(),
        parent_id=parent.id,
        embedding=FAKE_VECTOR,
        language="zh_hk",
        search_text="管理費追討小額錢債",
    )
    pg_session.add(child)
    await pg_session.commit()

    results = await HybridRetriever.retrieve("管理費", pg_session)
    if results:
        assert all(hasattr(r, "doc_type") for r in results)
        # doc_type should be a string
        assert all(isinstance(r.doc_type, str) for r in results)

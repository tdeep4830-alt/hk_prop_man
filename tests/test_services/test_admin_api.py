"""Unit tests for GET /api/v1/admin/query-logs.

Strategy
--------
* Override ``get_current_user`` to inject a synthetic User without touching the DB.
* Override ``get_db`` with a mock AsyncSession whose ``execute`` returns pre-canned
  results, avoiding the SQLite incompatibility with AuditLog's JSONB column.
* No LLM API calls are made; all responses are hard-coded fixtures.

Run with:
    pytest tests/test_services/test_admin_api.py -v -m "not integration"
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.user import MembershipTier, User


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _make_user(tier: MembershipTier, email: str | None = None) -> MagicMock:
    """Build a mock User with the right attributes — avoids SQLAlchemy instrumentation."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = email or f"{tier.value}@test.com"
    user.membership_tier = tier
    user.hashed_password = "hashed"
    user.pref_lang = "zh_hk"
    user.created_at = datetime.now(timezone.utc)
    return user


def _make_audit_log(user_id: uuid.UUID, detail: dict) -> MagicMock:
    """Build a mock AuditLog with the right attributes."""
    log = MagicMock(spec=AuditLog)
    log.id = uuid.uuid4()
    log.user_id = user_id
    log.action = "rag_query"
    log.detail = detail
    log.created_at = datetime.now(timezone.utc)
    return log


def _make_mock_db(
    total: int = 0,
    logs: list[AuditLog] | None = None,
    user_rows: list | None = None,
) -> AsyncMock:
    """
    Return a mock AsyncSession whose execute() returns:
      call 1 → COUNT  (scalar_one → total)
      call 2 → logs   (scalars().all() → logs)
      call 3 → users  (all() → user_rows)        [only if logs is non-empty]
    """
    mock_db = AsyncMock()
    logs = logs or []
    user_rows = user_rows or []
    call_index = [0]

    async def _execute(_query):
        call_index[0] += 1
        result = MagicMock()
        if call_index[0] == 1:                    # COUNT query
            result.scalar_one.return_value = total
        elif call_index[0] == 2:                  # logs query
            result.scalars.return_value.all.return_value = logs
        else:                                      # user email batch query
            result.all.return_value = user_rows
        return result

    mock_db.execute.side_effect = _execute
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def enterprise_user() -> User:
    return _make_user(MembershipTier.ENTERPRISE, "admin@test.com")


@pytest.fixture()
def free_user() -> User:
    return _make_user(MembershipTier.FREE, "free@test.com")


@pytest.fixture()
def pro_user() -> User:
    return _make_user(MembershipTier.PRO, "pro@test.com")


@pytest_asyncio.fixture()
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture()
async def free_client(free_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a FREE tier user."""
    app.dependency_overrides[get_current_user] = lambda: free_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture()
async def pro_client(pro_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a PRO tier user."""
    app.dependency_overrides[get_current_user] = lambda: pro_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture()
async def admin_client(
    enterprise_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as an ENTERPRISE tier user with an empty DB."""
    mock_db = _make_mock_db(total=0, logs=[])

    async def _get_db_override() -> AsyncGenerator:
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: enterprise_user
    app.dependency_overrides[get_db] = _get_db_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helper — build an admin client with pre-seeded logs
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def _admin_client_with_logs(
    enterprise_user: User,
    logs: list[AuditLog],
    user_rows: list | None = None,
):
    mock_db = _make_mock_db(
        total=len(logs), logs=logs, user_rows=user_rows or []
    )

    async def _get_db_override():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: enterprise_user
    app.dependency_overrides[get_db] = _get_db_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Tests — access control
# ---------------------------------------------------------------------------

class TestAccessControl:
    """Verify that the endpoint enforces authentication and tier restrictions."""

    async def test_unauthenticated_returns_401(self, anon_client: AsyncClient):
        """No token → 401 Unauthorized."""
        resp = await anon_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 401

    async def test_free_user_returns_403(self, free_client: AsyncClient):
        """FREE tier → 403 Forbidden."""
        resp = await free_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 403

    async def test_pro_user_returns_403(self, pro_client: AsyncClient):
        """PRO tier → 403 Forbidden."""
        resp = await pro_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 403

    async def test_enterprise_user_returns_200(self, admin_client: AsyncClient):
        """ENTERPRISE tier → 200 OK."""
        resp = await admin_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — response schema
# ---------------------------------------------------------------------------

class TestResponseSchema:
    """Validate the shape of a successful response."""

    async def test_empty_db_returns_valid_page(self, admin_client: AsyncClient):
        """Empty AuditLog → total=0, empty entries list, correct pagination fields."""
        resp = await admin_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["entries"] == []

    async def test_entry_fields_present(self, enterprise_user: User):
        """A single log entry exposes all required fields in the response."""
        user_id = enterprise_user.id
        log = _make_audit_log(user_id, {
            "masked_query":   "業主大會法定要求係咩？",
            "original_query": "業主大會法定要求係咩？",
            "pii_types":      [],
            "intent":         "legal_definition",
            "complexity":     "medium",
            "category":       "owners_committee",
            "latency_ms":     320,
            "llm_model":      "deepseek-ai/DeepSeek-V3",
            "chunks": [
                {"child_id": "c1", "parent_id": "p1", "combined_score": 0.87, "doc_type": "statute"},
                {"child_id": "c2", "parent_id": "p2", "combined_score": 0.61, "doc_type": "case_law"},
            ],
        })

        # user_rows: list of (id, email) named-tuple-like objects
        UserRow = MagicMock()
        UserRow.id = user_id
        UserRow.email = enterprise_user.email

        async with _admin_client_with_logs(
            enterprise_user, [log], user_rows=[UserRow]
        ) as ac:
            resp = await ac.get("/api/v1/admin/query-logs")

        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 1
        e = entries[0]

        # Required fields
        assert e["masked_query"]   == "業主大會法定要求係咩？"
        assert e["intent"]         == "legal_definition"
        assert e["complexity"]     == "medium"
        assert e["category"]       == "owners_committee"
        assert e["latency_ms"]     == 320
        assert e["llm_model"]      == "deepseek-ai/DeepSeek-V3"
        assert e["chunk_count"]    == 2
        assert e["pii_types"]      == []
        assert e["user_email"]     == enterprise_user.email

    async def test_chunk_fields_present(self, enterprise_user: User):
        """Each chunk contains child_id, parent_id, combined_score, doc_type."""
        log = _make_audit_log(enterprise_user.id, {
            "masked_query": "query",
            "pii_types": [],
            "chunks": [
                {"child_id": "abc", "parent_id": "xyz", "combined_score": 0.75, "doc_type": "statute"},
            ],
        })
        async with _admin_client_with_logs(enterprise_user, [log]) as ac:
            resp = await ac.get("/api/v1/admin/query-logs")

        chunk = resp.json()["entries"][0]["chunks"][0]
        assert chunk["child_id"]       == "abc"
        assert chunk["parent_id"]      == "xyz"
        assert chunk["combined_score"] == 0.75
        assert chunk["doc_type"]       == "statute"

    async def test_pii_query_hides_original(self, enterprise_user: User):
        """When PII is present, original_query is absent from the audit log detail."""
        log = _make_audit_log(enterprise_user.id, {
            "masked_query": "業主 [PERSON] 追討管理費",
            "pii_types":    ["PERSON"],
            # no "original_query" key — TelemetryLogger omits it when PII found
            "chunks": [],
        })
        async with _admin_client_with_logs(enterprise_user, [log]) as ac:
            resp = await ac.get("/api/v1/admin/query-logs")

        e = resp.json()["entries"][0]
        assert e["pii_types"]      == ["PERSON"]
        assert e["original_query"] is None

    async def test_simple_path_zero_chunks(self, enterprise_user: User):
        """SIMPLE complexity logs have zero chunks."""
        log = _make_audit_log(enterprise_user.id, {
            "masked_query": "甚麼係管理費",
            "pii_types":    [],
            "complexity":   "simple",
            "chunks":       [],
        })
        async with _admin_client_with_logs(enterprise_user, [log]) as ac:
            resp = await ac.get("/api/v1/admin/query-logs")

        e = resp.json()["entries"][0]
        assert e["chunk_count"] == 0
        assert e["chunks"]      == []


# ---------------------------------------------------------------------------
# Tests — pagination
# ---------------------------------------------------------------------------

class TestPagination:
    """Verify page / limit query params are forwarded correctly."""

    async def test_default_pagination(self, admin_client: AsyncClient):
        """Default page=1, limit=20 are reflected in the response."""
        resp = await admin_client.get("/api/v1/admin/query-logs")
        data = resp.json()
        assert data["page"]  == 1
        assert data["limit"] == 20

    async def test_custom_page_and_limit(self, enterprise_user: User):
        """Custom page=2, limit=5 are reflected in the response."""
        mock_db = _make_mock_db(total=12, logs=[])

        async def _get_db_override():
            yield mock_db

        app.dependency_overrides[get_current_user] = lambda: enterprise_user
        app.dependency_overrides[get_db] = _get_db_override
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/v1/admin/query-logs?page=2&limit=5")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

        data = resp.json()
        assert data["page"]  == 2
        assert data["limit"] == 5
        assert data["total"] == 12

    async def test_limit_max_100(self, admin_client: AsyncClient):
        """limit > 100 → 422 Unprocessable Entity."""
        resp = await admin_client.get("/api/v1/admin/query-logs?limit=101")
        assert resp.status_code == 422

    async def test_page_min_1(self, admin_client: AsyncClient):
        """page=0 → 422 Unprocessable Entity."""
        resp = await admin_client.get("/api/v1/admin/query-logs?page=0")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — intent filter
# ---------------------------------------------------------------------------

class TestIntentFilter:
    """Verify the intent query-string filter is accepted."""

    async def test_valid_intent_filter_accepted(self, enterprise_user: User):
        """intent=legal_definition → 200 (DB mock returns empty list)."""
        mock_db = _make_mock_db(total=0, logs=[])

        async def _get_db_override():
            yield mock_db

        app.dependency_overrides[get_current_user] = lambda: enterprise_user
        app.dependency_overrides[get_db] = _get_db_override
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    "/api/v1/admin/query-logs?intent=legal_definition"
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_no_intent_filter_returns_all(self, admin_client: AsyncClient):
        """No intent param → 200 with all entries."""
        resp = await admin_client.get("/api/v1/admin/query-logs")
        assert resp.status_code == 200

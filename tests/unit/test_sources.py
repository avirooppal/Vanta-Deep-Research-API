import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from contextlib import ExitStack
from tests.integration.test_api_routes import _ctx, _auth_patches, _make_mock_key, _make_mock_org


@pytest.mark.asyncio
async def test_get_sources_returns_list():
    from api.app import app
    from db.models.source import Source
    from db.models.research_job import ResearchJob

    mock_job = ResearchJob(
        id="job_sources_test", org_id="org_test", api_key_id="key_test",
        query="Test query", status="completed", max_rounds=3, priority=3,
        created_at=datetime.now(timezone.utc),
    )

    mock_source = Source(
        id="src_1", job_id="job_sources_test", org_id="org_test",
        url="https://example.com/page1", title="Title 1", excerpt="Excerpt 1",
        round_number=1, fetched_at=datetime.now(timezone.utc)
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    result_key = MagicMock()
    result_key.scalars.return_value.all.return_value = [_make_mock_key()]

    result_sources = MagicMock()
    result_sources.scalars.return_value.all.return_value = [mock_source]

    async def mock_execute(stmt):
        if "sources" in str(stmt):
            return result_sources
        return result_key

    mock_session.execute = mock_execute
    mock_session.get.side_effect = lambda model, pk: _make_mock_org() if model.__name__ == "Org" else mock_job

    with ExitStack() as stack:
        for p in _auth_patches(mock_session) + [patch("api.routes.sources.get_db_session", side_effect=lambda: _ctx(mock_session))]:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/research/job_sources_test/sources",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "src_1"
    assert data[0]["url"] == "https://example.com/page1"

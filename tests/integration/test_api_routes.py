import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from contextlib import ExitStack


def _ctx(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _auth_patches(mock_session):
    """Patch auth + audit middleware DB calls."""
    return [
        patch("api.middleware.auth.get_db_session", side_effect=lambda: _ctx(mock_session)),
        patch("api.middleware.audit_log.get_db_session", side_effect=lambda: _ctx(mock_session)),
        patch("api.middleware.auth.verify_api_key", return_value=True),
    ]


def _make_mock_key(org_id="org_test"):
    key = MagicMock()
    key.org_id = org_id
    key.id = "key_test"
    key.scope = "research:write,research:read"
    key.key_hash = "hash"
    key.is_active = True
    return key


def _make_mock_org(org_id="org_test"):
    org = MagicMock()
    org.is_active = True
    org.id = org_id
    return org


@pytest.mark.asyncio
async def test_get_job_returns_queued_status():
    from api.app import app
    from db.models.research_job import ResearchJob

    mock_job = ResearchJob(
        id="job_abc123", org_id="org_test", api_key_id="key_test",
        query="Test query", status="queued", max_rounds=3, priority=3,
        created_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # Synchronous mock for audit log
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_mock_key()]
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.get.side_effect = lambda model, pk: _make_mock_org() if model.__name__ == "Org" else mock_job

    with ExitStack() as stack:
        for p in _auth_patches(mock_session) + [patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(mock_session))]:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/research/job_abc123",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "job_abc123"
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_409():
    from api.app import app
    from db.models.research_job import ResearchJob

    mock_job = ResearchJob(
        id="job_done", org_id="org_test", api_key_id="k",
        query="q", status="completed", max_rounds=3, priority=3,
        created_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # Synchronous mock for audit log
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_mock_key()]
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.get.side_effect = lambda model, pk: _make_mock_org() if model.__name__ == "Org" else mock_job

    with ExitStack() as stack:
        for p in _auth_patches(mock_session) + [patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(mock_session))]:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                "/v1/research/job_done",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_md_returns_markdown():
    from api.app import app
    from db.models.report import Report

    mock_report = Report(
        id="rpt_abc", job_id="job_xyz", org_id="org_test",
        summary="Summary here", content_md="## Report\nContent here",
        content_json='{"citations": []}', created_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # Synchronous mock for audit log
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_mock_key()]
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.get.side_effect = lambda model, pk: _make_mock_org() if model.__name__ == "Org" else mock_report

    with ExitStack() as stack:
        for p in _auth_patches(mock_session) + [patch("api.routes.reports.get_db_session", side_effect=lambda: _ctx(mock_session))]:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/reports/rpt_abc/export?format=md",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 200
    assert "## Report" in response.text

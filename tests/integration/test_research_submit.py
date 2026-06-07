import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from contextlib import AsyncExitStack, ExitStack


def _make_api_key(org_id="org_test"):
    key = MagicMock()
    key.org_id = org_id
    key.id = "key_test"
    key.scope = "research:write"
    key.key_hash = "anyhash"
    key.is_active = True
    return key


def _make_org(org_id="org_test"):
    org = MagicMock()
    org.is_active = True
    org.id = org_id
    return org


def _make_auth_session():
    """A mock session that satisfies auth_middleware's two DB calls."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_api_key()]
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=_make_org())
    return session


def _ctx(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_submit_research_returns_202():
    from api.app import app

    auth_session = _make_auth_session()
    route_session = AsyncMock()
    route_session.add = MagicMock()  # Synchronous mock to prevent coroutine un-awaited warning
    mock_redis = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("api.middleware.auth.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.audit_log.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.auth.verify_api_key", return_value=True))
        stack.enter_context(patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(route_session)))
        stack.enter_context(patch("api.routes.research.create_pool", return_value=mock_redis))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/research",
                json={"query": "What is the CAR-T therapy market?"},
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert "id" in data
    assert data["query"] == "What is the CAR-T therapy market?"

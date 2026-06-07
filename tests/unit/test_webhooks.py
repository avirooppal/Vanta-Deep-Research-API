import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from contextlib import ExitStack
from tests.integration.test_api_routes import _ctx, _auth_patches, _make_mock_key, _make_mock_org
from core.webhooks.signing import hmac_sign
from db.models.webhook import WebhookEndpoint


def test_hmac_signature():
    secret = "my_secret_key"
    payload = '{"event": "test"}'
    expected = hmac_sign(payload, secret)
    # Re-calculate to assert correctness
    import hmac
    import hashlib
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert expected == sig


@pytest.mark.asyncio
async def test_webhook_crud():
    from api.app import app

    mock_webhook = WebhookEndpoint(
        id="wh_123", org_id="org_test", url="https://example.com/callback",
        secret="sec", is_active=True
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.delete = AsyncMock()

    result_key = MagicMock()
    result_key.scalars.return_value.all.return_value = [_make_mock_key()]

    result_webhooks = MagicMock()
    result_webhooks.scalars.return_value.all.return_value = [mock_webhook]

    async def mock_execute(stmt):
        if "webhook" in str(stmt):
            return result_webhooks
        return result_key

    mock_session.execute = mock_execute
    mock_session.get.side_effect = lambda model, pk: _make_mock_org() if model.__name__ == "Org" else mock_webhook

    with ExitStack() as stack:
        for p in _auth_patches(mock_session) + [patch("api.routes.webhooks.get_db_session", side_effect=lambda: _ctx(mock_session))]:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create
            r_create = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/callback", "secret": "sec"},
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )
            assert r_create.status_code == 201
            assert r_create.json()["url"] == "https://example.com/callback"

            # 2. List
            r_list = await client.get(
                "/v1/webhooks",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )
            assert r_list.status_code == 200
            assert len(r_list.json()) == 1
            assert r_list.json()[0]["id"] == "wh_123"

            # 3. Delete
            r_delete = await client.delete(
                "/v1/webhooks/wh_123",
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )
            assert r_delete.status_code == 204

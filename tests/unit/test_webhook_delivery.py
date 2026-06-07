import pytest
from unittest.mock import AsyncMock, patch
from core.queue.tasks import deliver_webhook_job


@pytest.mark.asyncio
async def test_webhook_delivery_success(httpx_mock):
    httpx_mock.add_response(status_code=200)

    url = "https://example.com/callback"
    payload = '{"event": "test"}'
    signature = "sha256=abcdef"

    await deliver_webhook_job({}, url, payload, signature)

    request = httpx_mock.get_request()
    assert request is not None
    assert request.url == url
    assert request.headers["x-signature"] == signature
    assert request.content.decode("utf-8") == payload


@pytest.mark.asyncio
async def test_webhook_delivery_failure_retry(httpx_mock):
    httpx_mock.add_response(status_code=500)

    url = "https://example.com/callback"
    payload = '{"event": "test"}'
    signature = "sha256=abcdef"

    mock_redis = AsyncMock()

    with patch("core.queue.tasks.create_pool", return_value=mock_redis):
        await deliver_webhook_job({}, url, payload, signature, attempt=1)

    mock_redis.enqueue_job.assert_called_once_with(
        "deliver_webhook_job",
        url=url,
        payload=payload,
        signature=signature,
        attempt=2,
        _defer_by=10
    )
    mock_redis.aclose.assert_called_once()

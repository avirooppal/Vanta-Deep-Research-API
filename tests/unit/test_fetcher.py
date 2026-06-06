import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from integrations.fetcher import fetch_url


def _mock_fetch_client(html_text):
    mock_resp = MagicMock()
    mock_resp.text = html_text
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_fetch_extracts_text():
    html = "<html><head><title>Test Page</title></head><body><p>Hello world content.</p><script>ignored</script></body></html>"

    with patch("integrations.fetcher.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_fetch_client(html)
        page = await fetch_url("https://example.com")

    assert page.success is True
    assert "Hello world content" in page.text
    assert "ignored" not in page.text
    assert page.title == "Test Page"


@pytest.mark.asyncio
async def test_fetch_handles_error():
    with patch("integrations.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_cls.return_value = mock_client

        page = await fetch_url("https://unreachable.example.com")

    assert page.success is False
    assert page.error is not None

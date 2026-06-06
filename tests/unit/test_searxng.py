import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from integrations.searxng import search_searxng


def _mock_searxng_client(json_data):
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_searxng_parses_results():
    mock_response = {
        "results": [
            {"url": "https://example.com", "title": "Example", "content": "An example site."},
            {"url": "https://another.com", "title": "Another", "content": "Another site."},
        ]
    }
    with patch("integrations.searxng.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_searxng_client(mock_response)
        results = await search_searxng("test query", "http://searxng:8080")

    assert len(results) == 2
    assert results[0].url == "https://example.com"
    assert results[0].title == "Example"
    assert results[0].snippet == "An example site."


@pytest.mark.asyncio
async def test_searxng_respects_num_results():
    mock_response = {
        "results": [
            {"url": f"https://example{i}.com", "title": f"Ex{i}", "content": "c"}
            for i in range(10)
        ]
    }
    with patch("integrations.searxng.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_searxng_client(mock_response)
        results = await search_searxng("query", "http://searxng:8080", num_results=3)

    assert len(results) == 3

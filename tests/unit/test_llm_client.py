import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm.client import LLMClient
from core.llm.types import LLMConfig, Message


def _make_mock_client(mock_response):
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_routes_to_openai():
    mock_response = {
        "choices": [{"message": {"content": "mocked"}}],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    with patch("core.llm.providers.openai.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_client(mock_response)
        config = LLMConfig(provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
        result = await LLMClient(config).complete([Message(role="user", content="hi")])
    assert result.content == "mocked"


@pytest.mark.asyncio
async def test_routes_to_anthropic():
    mock_response = {
        "content": [{"type": "text", "text": "claude mocked"}],
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 8, "output_tokens": 4},
    }
    with patch("core.llm.providers.anthropic.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_client(mock_response)
        config = LLMConfig(provider="anthropic", base_url="https://api.anthropic.com/v1", api_key="sk-ant-test", model="claude-sonnet-4-6")
        result = await LLMClient(config).complete([Message(role="user", content="hi")])
    assert result.content == "claude mocked"


@pytest.mark.asyncio
async def test_raises_on_unknown_provider():
    config = LLMConfig(provider="unknown_provider", base_url="http://x", api_key=None, model="m")
    with pytest.raises(ValueError, match="Unsupported provider"):
        await LLMClient(config).complete([Message(role="user", content="hi")])

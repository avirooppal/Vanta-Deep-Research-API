import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm.providers.anthropic import call_anthropic
from core.llm.types import Message, LLMConfig


@pytest.mark.asyncio
async def test_call_anthropic_parses_response():
    mock_response = {
        "content": [{"type": "text", "text": "Anthropic response"}],
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 20, "output_tokens": 8},
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("core.llm.providers.anthropic.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        config = LLMConfig(
            provider="anthropic",
            base_url="https://api.anthropic.com/v1",
            api_key="sk-ant-test",
            model="claude-sonnet-4-6",
        )
        result = await call_anthropic([Message(role="user", content="hello")], config)

    assert result.content == "Anthropic response"
    assert result.tokens_in == 20
    assert result.tokens_out == 8

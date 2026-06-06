import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm.providers.openai import call_openai
from core.llm.types import Message, LLMConfig


@pytest.mark.asyncio
async def test_call_openai_parses_response():
    mock_response = {
        "choices": [{"message": {"content": "Test response"}}],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("core.llm.providers.openai.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        config = LLMConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o",
        )
        result = await call_openai([Message(role="user", content="hi")], config)

    assert result.content == "Test response"
    assert result.tokens_in == 10
    assert result.tokens_out == 5

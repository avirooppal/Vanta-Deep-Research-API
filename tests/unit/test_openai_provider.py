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


@pytest.mark.asyncio
async def test_reasoning_model_uses_max_completion_tokens_and_omits_temperature():
    from core.llm.providers.openai import _uses_max_completion_tokens, _omit_temperature
    assert _uses_max_completion_tokens("o3-mini") is True
    assert _uses_max_completion_tokens("o1-preview") is True
    assert _uses_max_completion_tokens("gpt-4o") is False
    assert _omit_temperature("o3-mini") is True
    assert _omit_temperature("gpt-4o") is False


@pytest.mark.asyncio
async def test_is_symbolic_rate_limit():
    from core.llm.providers.openai import _is_symbolic_rate_limit
    assert _is_symbolic_rate_limit({"status": "RESOURCE_EXHAUSTED"}) is True
    assert _is_symbolic_rate_limit({"status": "RATE_LIMITED"}) is True
    assert _is_symbolic_rate_limit({"message": "Rate limit reached. Try again later."}) is True
    assert _is_symbolic_rate_limit({"message": "Invalid API key"}) is False


@pytest.mark.asyncio
async def test_format_upstream_error():
    from core.llm.providers.openai import _format_upstream_error
    err_429 = _format_upstream_error(429, '{"error": {"message": "rate limit exceeded"}}', "openrouter")
    assert "rate-limited" in err_429
    assert "OpenRouter free models are capped" in err_429

    err_401 = _format_upstream_error(401, '{"error": "Unauthorized"}', "openai")
    assert "rejected API key" in err_401

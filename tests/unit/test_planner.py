import pytest
from unittest.mock import AsyncMock
from core.research.planner import plan_queries
from core.llm.types import LLMResponse


@pytest.mark.asyncio
async def test_plan_queries_parses_json():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content='["query one", "query two", "query three"]',
        model="gpt-4o", tokens_in=10, tokens_out=10
    )
    queries = await plan_queries("What is X?", mock_llm)
    assert queries == ["query one", "query two", "query three"]


@pytest.mark.asyncio
async def test_plan_queries_fallback_on_bad_json():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="not valid json at all",
        model="gpt-4o", tokens_in=5, tokens_out=5
    )
    queries = await plan_queries("What is X?", mock_llm)
    assert queries == ["What is X?"]


@pytest.mark.asyncio
async def test_plan_queries_caps_at_six():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content='["q1","q2","q3","q4","q5","q6","q7","q8"]',
        model="gpt-4o", tokens_in=10, tokens_out=10
    )
    queries = await plan_queries("Big question", mock_llm)
    assert len(queries) <= 6

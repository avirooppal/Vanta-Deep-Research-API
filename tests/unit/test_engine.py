import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from core.research.engine import run_research
from core.research.extractor import Finding
from core.research.synthesizer import ReportOutput
from core.llm.types import LLMResponse
from integrations.searxng import SearchResult
from integrations.fetcher import FetchedPage


@pytest.mark.asyncio
async def test_engine_returns_report():
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(content='["query one"]', model="gpt-4o", tokens_in=10, tokens_out=10),
        LLMResponse(content="- Fact one\n- Fact two", model="gpt-4o", tokens_in=20, tokens_out=10),
        LLMResponse(content="DONE", model="gpt-4o", tokens_in=10, tokens_out=1),
        LLMResponse(
            content="## Summary\nContent [1]\n\n## Sources\n[1] https://a.com",
            model="gpt-4o", tokens_in=100, tokens_out=50
        ),
    ]

    mock_search_results = [SearchResult(url="https://a.com", title="A", snippet="snippet")]
    mock_page = FetchedPage(url="https://a.com", title="A", text="Content about topic.", success=True)

    with patch("core.research.engine.search_searxng", AsyncMock(return_value=mock_search_results)), \
         patch("core.research.engine.fetch_url", AsyncMock(return_value=mock_page)):
        report = await run_research("What is X?", mock_llm, "http://searxng:8080", max_rounds=2)

    assert isinstance(report, ReportOutput)
    assert report.query == "What is X?"


@pytest.mark.asyncio
async def test_engine_respects_cancellation():
    cancelled = asyncio.Event()
    cancelled.set()
    mock_llm = AsyncMock()

    report = await run_research(
        "What is X?", mock_llm, "http://searxng:8080",
        max_rounds=3, cancelled=cancelled
    )

    assert report.query == "What is X?"
    mock_llm.complete.assert_not_called()

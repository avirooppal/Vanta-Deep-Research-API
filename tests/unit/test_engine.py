import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from core.research.engine import run_research
from core.research.agents.synthesizer import ReportOutput
from core.llm.types import LLMResponse
from integrations.searxng import SearchResult
from integrations.fetcher import FetchedPage


def _r(content):
    return LLMResponse(content=content, model="gpt-4o", tokens_in=10, tokens_out=10)


_PLAN = '{"sub_questions": ["What is X?"], "key_topics": ["X"], "success_criteria": "Full answer."}'
_EXTRACTOR = '{"rational": "relevant", "evidence": "Fact one", "summary": "Fact one", "trust_score": 80}'
_FINAL = "## Summary\nContent [1]\n\n## Sources\n[1] https://a.com"
_STUDY = "# Quantum Computing - Study Guide\n\n## 1. Overview\nQubits explain quantum.\n\n## Sources\n[1] https://a.com"


def _flexible_llm(study_mode=False):
    """Build a mock LLM that returns sensible responses for each agent."""
    mock = AsyncMock()
    mock.search_queries_issued = 0
    mock.sources_fetched = 0

    async def _complete(messages, **kwargs):
        # Inspect the first message to decide what to return
        first = messages[0].content if messages else ""

        if "research strategist" in first or "sub_questions" in first:
            return _r(_PLAN)
        if "Classify this research question" in first:
            return _r("general")
        if "CONTINUE" in first or "SYNTHESIZE" in first:
            return _r("CONTINUE")
        if "Search Agent" in first or "search queries" in first.lower():
            return _r('["query one"]')
        if "Source Validation" in first or "trustworthiness" in first:
            return _r('{"trust_score": 85, "flags": "None"}')
        if "research goal" in first or "Extract relevant" in first:
            return _r(_EXTRACTOR)
        if "evolving research report" in first or "Integrate the new findings" in first:
            return _r("Updated evolving report.")
        if "Contradiction" in first:
            return _r("[]")
        if "comprehensive enough" in first:
            return _r("YES — enough information.")
        if "Expert Educator" in first:
            return _r(_STUDY)
        if "comprehensive" in first.lower() and "report" in first.lower():
            return _r(_STUDY if study_mode else _FINAL)
        return _r(_FINAL)

    mock.complete.side_effect = _complete
    return mock


@pytest.mark.asyncio
async def test_engine_returns_report():
    mock_llm = _flexible_llm()

    mock_search_results = [SearchResult(url="https://a.com", title="A", snippet="snippet")]
    mock_page = FetchedPage(url="https://a.com", title="A", text="Content about topic.", success=True)

    with patch("core.research.engine.search_searxng", AsyncMock(return_value=mock_search_results)), \
         patch("core.research.engine.fetch_url", AsyncMock(return_value=mock_page)):
        report = await run_research("What is X?", mock_llm, "http://searxng:8080", max_rounds=2)

    assert isinstance(report, ReportOutput)
    assert report.query == "What is X?"


@pytest.mark.asyncio
async def test_engine_supports_study_mode():
    mock_llm = _flexible_llm(study_mode=True)

    mock_search_results = [SearchResult(url="https://a.com", title="Quantum", snippet="Intro to qubits")]
    mock_page = FetchedPage(url="https://a.com", title="Quantum", text="Quantum computing uses qubits and superposition.", success=True)

    with patch("core.research.engine.search_searxng", AsyncMock(return_value=mock_search_results)), \
         patch("core.research.engine.fetch_url", AsyncMock(return_value=mock_page)):
        report = await run_research(
            "Explain quantum computing",
            mock_llm,
            "http://searxng:8080",
            max_rounds=2,
            mode="study",
        )

    assert isinstance(report, ReportOutput)
    assert "Study Guide" in report.body_md or "Overview" in report.body_md


@pytest.mark.asyncio
async def test_engine_respects_cancellation():
    cancelled = asyncio.Event()
    cancelled.set()
    mock_llm = AsyncMock()
    mock_llm.search_queries_issued = 0
    mock_llm.sources_fetched = 0

    # Planning runs before the loop cancellation check, so give it basic responses
    mock_llm.complete.return_value = _r(_PLAN)

    report = await run_research(
        "What is X?", mock_llm, "http://searxng:8080",
        max_rounds=3, cancelled=cancelled
    )

    assert report.query == "What is X?"

import pytest
from unittest.mock import AsyncMock
from core.research.extractor import extract_findings
from core.llm.types import LLMResponse
from integrations.fetcher import FetchedPage


@pytest.mark.asyncio
async def test_extracts_facts_from_page():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="- Fact one\n- Fact two", model="gpt-4o", tokens_in=50, tokens_out=20
    )
    page = FetchedPage(url="https://ex.com", title="Ex", text="Some content", success=True)
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is not None
    assert finding.url == "https://ex.com"
    assert "Fact one" in finding.facts


@pytest.mark.asyncio
async def test_returns_none_for_no_relevant_content():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="NO_RELEVANT_CONTENT", model="gpt-4o", tokens_in=30, tokens_out=5
    )
    page = FetchedPage(url="https://ex.com", title="Ex", text="Off-topic content", success=True)
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is None


@pytest.mark.asyncio
async def test_returns_none_for_failed_fetch():
    mock_llm = AsyncMock()
    page = FetchedPage(url="https://ex.com", title="", text="", success=False, error="timeout")
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is None
    mock_llm.complete.assert_not_called()

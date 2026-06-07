import pytest
from unittest.mock import AsyncMock
from core.research.synthesizer import should_continue, synthesize_report
from core.research.extractor import Finding
from core.llm.types import LLMResponse

SAMPLE_FINDINGS = [
    Finding(url="https://a.com", title="Source A", facts="Fact one about X.", round_number=1),
    Finding(url="https://b.com", title="Source B", facts="Fact two about X.", round_number=1),
]


@pytest.mark.asyncio
async def test_should_continue_true():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(content="CONTINUE", model="gpt-4o", tokens_in=10, tokens_out=1)
    result = await should_continue("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert result is True


@pytest.mark.asyncio
async def test_should_continue_false():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(content="DONE", model="gpt-4o", tokens_in=10, tokens_out=1)
    result = await should_continue("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert result is False


@pytest.mark.asyncio
async def test_synthesize_report_structure():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="Executive summary.\n\n## Section 1\nContent [1]\n\n## Sources\n[1] https://a.com",
        model="gpt-4o", tokens_in=100, tokens_out=50
    )
    report = await synthesize_report("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert report.query == "What is X?"
    assert len(report.citations) == 2
    assert report.citations[0]["url"] == "https://a.com"
    assert "Executive summary" in report.summary

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.research.state import ResearchState, Finding, ValidatedSource
from core.research.evidence.models import AtomicClaim, ClaimType
from core.research.agents.synthesizer import ReportOutput
from core.research.agents.citation_verifier import CitationVerifierAgent
from core.research.agents.claim_verifier import ClaimVerifierAgent
from core.research.agents.editor import EditorAgent
from core.research.quality.gate import evaluate_quality_gate
from core.llm.types import LLMResponse


@pytest.mark.asyncio
async def test_citation_verifier_cleans_and_validates():
    state = ResearchState(question="Assess solid state batteries", max_rounds=2)
    state.findings = [
        Finding(
            url="https://nature.com/article1",
            title="Solid Electrolyte Progress",
            facts="Sulfide electrolytes achieve 12 mS/cm conductivity.",
            summary="Sulfide conductivity reaches liquid electrolyte levels.",
            round_number=1,
        ),
        Finding(
            url="https://energy.gov/report",
            title="DOE Battery Target",
            facts="Cost targets are $80/kWh by 2030.",
            summary="DOE sets aggressive $80/kWh cell cost targets.",
            round_number=1,
        ),
    ]

    # Report has valid citations [1], invalid out-of-bounds [99], duplicate [1, 1], and mixed [2, 99]
    raw_body = (
        "Sulfide electrolytes demonstrate high conductivity [1, 1]. "
        "Cell costs are projected at $80/kWh [2, 99]. "
        "Fictitious assertion without source [99]."
    )
    report = ReportOutput(
        query=state.question,
        summary="Summary",
        body_md=raw_body,
        citations=[{"id": "src_1", "url": "https://nature.com/article1"}],
    )

    agent = CitationVerifierAgent(llm=MagicMock())
    verified = await agent.run(state, report)

    # [1, 1] collapsed to [1]
    assert "[1]" in verified.body_md
    assert "[1, 1]" not in verified.body_md
    # [2, 99] cleaned to [2]
    assert "[2]" in verified.body_md
    # [99] completely stripped
    assert "[99]" not in verified.body_md


@pytest.mark.asyncio
async def test_claim_verifier_detects_unsupported():
    state = ResearchState(question="Solid state commercialization timeline", max_rounds=2)
    state.claims = [
        AtomicClaim(
            claim_id="clm_1",
            claim_text="Toyota targets pilot production in 2027",
            claim_type=ClaimType.ANNOUNCEMENT,
            source_url="https://toyota.com/pr",
        )
    ]
    state.findings = [
        Finding(
            url="https://toyota.com/pr",
            title="Toyota PR",
            facts="Toyota announced plans for solid-state batteries in 2027.",
            round_number=1,
        )
    ]

    report = ReportOutput(
        query=state.question,
        summary="Timeline assessment",
        body_md="Toyota will produce 1,000,000 solid state vehicles by 2025. Toyota targets pilot lines in 2027.",
        citations=[],
    )

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        {
            "checks": [
                {
                    "report_statement": "Toyota will produce 1,000,000 solid state vehicles by 2025",
                    "status": "NOT_SUPPORTED",
                    "discrepancy_explanation": "No evidence for 1,000,000 vehicle production by 2025."
                },
                {
                    "report_statement": "Toyota targets pilot lines in 2027",
                    "status": "SUPPORTED",
                    "discrepancy_explanation": ""
                }
            ],
            "unsupported_count": 1,
            "has_critical_discrepancy": true
        }
        ''',
        model="test",
        tokens_in=50,
        tokens_out=50,
    ))

    verifier = ClaimVerifierAgent(mock_llm)
    checks = await verifier.run(state, report)
    assert len(checks) == 2
    assert any(c.status.value == "NOT_SUPPORTED" for c in checks)
    assert any("Evidence Audit:" in w for w in state.warnings)


@pytest.mark.asyncio
async def test_editor_agent_removes_filler_and_preserves_citations():
    state = ResearchState(question="Market trends", max_rounds=1)
    raw_text = (
        "# Market Trends\n\n"
        "It is important to note that solid state technology is advancing rapidly [1]. "
        "In today's rapidly evolving landscape, electrolyte conductivity has improved [2]. "
        "This highlights the importance of continued research."
    )
    report = ReportOutput(query=state.question, summary="Summary", body_md=raw_text, citations=[])

    mock_llm = MagicMock()
    # Mock LLM returning cleaned text preserving citations
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=(
            "# Market Trends\n\n"
            "Solid state technology is advancing rapidly [1]. "
            "Electrolyte conductivity has improved [2]. "
            "Commercial scale demands sustained investment."
        ),
        model="test",
        tokens_in=50,
        tokens_out=50,
    ))

    editor = EditorAgent(mock_llm)
    edited = await editor.run(state, report)
    assert "[1]" in edited.body_md
    assert "[2]" in edited.body_md
    assert "It is important to note" not in edited.body_md


def test_final_quality_gate_evaluation():
    state = ResearchState(question="Quantum computing commercial scaling", max_rounds=2)
    state.findings = [Finding(url="https://q.org", title="Qubits", facts="100 logical qubits.", round_number=1)]

    # Robust report with citations and uncertainty
    good_report = ReportOutput(
        query=state.question,
        summary="Quantum summary",
        body_md=(
            "# Quantum Computing Commercial Scaling\n\n"
            "Scaling quantum computing requires fault-tolerant logical qubits [1]. "
            "Recent demonstrations have achieved high two-qubit gate fidelities [1]. "
            "However, long-term commercial timelines remain uncertain due to dilution refrigeration constraints. "
            "Current systems operate primarily in the NISQ regime with substantial hardware overhead."
        ) * 5,  # sufficient length
        citations=[{"id": "src_1", "url": "https://q.org"}],
    )

    result_good = evaluate_quality_gate(state, good_report)
    assert result_good.passed is True
    assert result_good.quality_score >= 70

    # Deficient report: empty, no citations, no uncertainty
    bad_report = ReportOutput(query=state.question, summary="Bad", body_md="Short text.", citations=[])
    result_bad = evaluate_quality_gate(state, bad_report)
    assert result_bad.passed is False
    assert len(result_bad.issues) >= 1

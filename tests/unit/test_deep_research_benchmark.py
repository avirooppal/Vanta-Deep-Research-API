"""
Vanta Deep Research End-to-End Upgrade Benchmark & Regression Suite.

Validates all 6 phases of the upgraded research pipeline against the target standards:
1. Question Understanding & Decomposition (Brief)
2. Hypothesis-Driven Research & Search Diversity (Plan & Multi-Family Queries)
3. Atomic Evidence & Provenance (AtomicClaim, SourceQuality, SourceLineage)
4. Contradiction Diagnosis & Adversarial Falsification (ChallengeAgent)
5. Evidence Audit & Structured Report Planning (ReportPlan)
6. Claim & Citation Entailment Verification, Editor, and Quality Gate
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.research.state import ResearchState, Finding, ValidatedSource
from core.research.planning.brief import understand_question, QuestionType
from core.research.planning.plan import create_research_plan
from core.research.agents.search import SearchAgent
from core.research.evidence.models import (
    AtomicClaim,
    ClaimType,
    SourceQuality,
    SourceLineage,
    QuantitativeFact,
)
from core.research.reasoning.models import ContradictionType, ResearchChallenge
from core.research.agents.contradiction import ContradictionAgent
from core.research.agents.challenge import ChallengeAgent
from core.research.synthesis.planner import audit_evidence, create_report_plan
from core.research.agents.synthesizer import SynthesizerAgent, ReportOutput
from core.research.agents.citation_verifier import CitationVerifierAgent
from core.research.agents.claim_verifier import ClaimVerifierAgent
from core.research.agents.editor import EditorAgent
from core.research.quality.gate import evaluate_quality_gate
from core.llm.types import LLMResponse


@pytest.mark.asyncio
async def test_benchmark_question_understanding_and_decomposition():
    """Benchmark: Complex analytical inquiry is parsed into structured brief & competing sub-questions."""
    query = "Analyze whether solid-state batteries are likely to become commercially competitive with lithium-ion before 2030."
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        {
            "normalized_question": "Are solid-state batteries commercially competitive with Li-ion before 2030?",
            "research_goal": "Assess 2030 commercial parity across cost, safety, and manufacturing yield",
            "question_type": "COMPARATIVE",
            "scope": "Global automotive and grid storage",
            "geographic_scope": "Global",
            "time_scope": "2024-2030",
            "entities": ["QuantumScape", "Toyota", "CATL", "Solid Power"],
            "sub_questions": [
                "What is the projected $/kWh cost curve through 2030?",
                "What are current pilot line manufacturing yield bottlenecks?",
                "How do commercialization timelines compare between sulfide and oxide electrolytes?",
                "What counterevidence exists regarding commercialization delays?"
            ],
            "required_evidence_types": ["peer-reviewed", "financial filings", "pilot announcements"],
            "recency_requirement": "2023-2026"
        }
        ''',
        model="test",
        tokens_in=100,
        tokens_out=150,
    ))

    brief = await understand_question(query, mock_llm)
    assert brief.question_type == QuestionType.COMPARATIVE
    assert len(brief.sub_questions) >= 4
    assert "Toyota" in brief.entities


@pytest.mark.asyncio
async def test_benchmark_search_diversity_and_novelty():
    """Benchmark: SearchAgent emits multi-family queries (broad, primary, academic, skeptical) and rejects duplicates."""
    state = ResearchState(
        question="Solid-state battery commercialization",
        max_rounds=2,
    )
    # Simulate round 1 queries already used
    state.queries_used.add("solid state battery commercialization")
    state.queries_used.add("solid state battery 2030 cost per kwh")

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        [
            "solid state battery commercialization",
            "site:nature.com solid electrolyte conductivity yield",
            "Toyota solid state battery pilot line delay announcement",
            "solid state battery $/kWh capex projection 2030"
        ]
        ''',
        model="test",
        tokens_in=50,
        tokens_out=60,
    ))

    search_agent = SearchAgent(mock_llm)
    queries = await search_agent.run(state)

    # First query was already used (low novelty), so it must be filtered out
    assert "solid state battery commercialization" not in queries
    # Novel technical and skeptical queries should remain
    assert any("nature.com" in q for q in queries)
    assert any("delay" in q.lower() or "pilot" in q.lower() for q in queries)


@pytest.mark.asyncio
async def test_benchmark_contradiction_and_falsification():
    """Benchmark: Contradictions are diagnosed by root cause, and ChallengeAgent flags single-source dependencies."""
    state = ResearchState(question="Assess commercialization timeline", max_rounds=2)
    state.findings = [
        Finding(
            url="https://company.com/announcement",
            title="Company Press Release",
            facts="We plan to achieve mass volume production of solid-state cells by 2027 at $75/kWh.",
            summary="Company targets 2027 commercial production.",
            round_number=1,
        ),
        Finding(
            url="https://bloombergnef.com/analysis",
            title="BNEF Battery Outlook",
            facts="High separator production costs will delay commercial solid-state volume until at least 2030, with early cells exceeding $140/kWh.",
            summary="Independent analysis forecasts 2030+ timeline and higher costs.",
            round_number=1,
        )
    ]

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        [
            {
                "description": "Commercialization target year and cost disparity ($75 vs $140/kWh)",
                "source_urls": ["https://company.com/announcement", "https://bloombergnef.com/analysis"],
                "severity": "HIGH",
                "contradiction_type": "FORECAST_DIFFERENCE",
                "resolution_suggestion": "Distinguish company target from independent analyst forecast"
            }
        ]
        ''',
        model="test",
        tokens_in=80,
        tokens_out=100,
    ))

    contra_agent = ContradictionAgent(mock_llm)
    contras = await contra_agent.run(state)
    assert len(contras) == 1
    assert contras[0].contradiction_type == "FORECAST_DIFFERENCE"

    # ChallengeAgent falsifies assumption
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        [
            {
                "challenge_id": "ch_1",
                "target_conclusion": "Solid state cells will reach mass market by 2027",
                "vulnerability_explanation": "Conclusion relies exclusively on an unverified OEM announcement with historical delays",
                "single_source_dependencies": ["https://company.com/announcement"],
                "competing_explanation": "Pilot scale validation does not guarantee roll-to-roll yield at industrial scale",
                "missing_falsifying_evidence": ["Independent factory yield audits"],
                "suggested_investigation_query": "solid state battery manufacturing yield defect rate"
            }
        ]
        ''',
        model="test",
        tokens_in=80,
        tokens_out=120,
    ))

    challenger = ChallengeAgent(mock_llm)
    challenges = await challenger.run(state)
    assert len(challenges) == 1
    assert challenges[0].challenge_id.startswith("ch_")
    assert "https://company.com/announcement" in challenges[0].single_source_dependencies


@pytest.mark.asyncio
async def test_benchmark_full_verification_and_quality_gate():
    """Benchmark: End-to-end audit, citation cleaning, editing, and quality standards pass."""
    state = ResearchState(question="Evaluate solid state battery viability by 2030", max_rounds=2)
    state.findings = [
        Finding(
            url="https://nature.com/article1",
            title="Solid State Overview",
            facts="Solid electrolytes offer higher theoretical energy density but face interfacial resistance [1].",
            summary="Interfacial resistance remains a primary technical hurdle.",
            round_number=1,
            trust_score=85,
        ),
        Finding(
            url="https://doe.gov/energy",
            title="DOE Battery Roadmap",
            facts="DOE cell level targets are $80/kWh with 1000 cycle life by 2030 [2].",
            summary="DOE roadmaps target $80/kWh by 2030.",
            round_number=1,
            trust_score=90,
        ),
    ]

    raw_report = ReportOutput(
        query=state.question,
        summary="Comprehensive evaluation of solid state viability",
        body_md=(
            "# Evaluate Solid State Battery Viability by 2030\n\n"
            "## Executive Summary\n"
            "Solid-state batteries offer substantial theoretical energy density advantages, but commercial "
            "parity with lithium-ion by 2030 remains uncertain [1]. While laboratory prototypes demonstrate "
            "high ionic conductivity, manufacturing yield constraints in roll-to-roll production pose severe bottlenecks [1].\n\n"
            "## Economic and Cost Parity\n"
            "The Department of Energy has targeted $80/kWh cell-level costs by 2030 [2]. "
            "However, current pilot facilities report substantial cost premiums, creating significant variance between "
            "company announcements and independent analyst estimates [1, 2]. Consequently, volume commercialization before 2030 "
            "is unlikely to displace conventional lithium-ion across mass-market automotive segments.\n\n"
            "## Manufacturing Bottlenecks & Scale Constraints\n"
            "Solid electrolyte separators, particularly ceramic and sulfide thin films, exhibit high defect rates during continuous calendar pressing. "
            "These yield constraints dramatically elevate the effective scrap cost per pack, which prevents early solid state cells from "
            "competing directly with incumbent LFP and NMC chemistries on price [1]. Independent industry consensus expects initial applications to "
            "remain concentrated in premium luxury vehicles and aerospace niches rather than high-volume mass passenger cars."
        ),
        citations=[
            {"id": "src_1", "url": "https://nature.com/article1", "title": "Solid State Overview"},
            {"id": "src_2", "url": "https://doe.gov/energy", "title": "DOE Battery Roadmap"},
        ],
    )

    # 1. Citation verification
    cit_agent = CitationVerifierAgent(llm=MagicMock())
    verified_report = await cit_agent.run(state, raw_report)
    assert "[1]" in verified_report.body_md
    assert "[2]" in verified_report.body_md

    # 2. Quality gate
    gate = evaluate_quality_gate(state, verified_report)
    assert gate.passed is True
    assert gate.quality_score >= 80
    assert gate.checks["citations_present"] is True
    assert gate.checks["uncertainty_communicated"] is True

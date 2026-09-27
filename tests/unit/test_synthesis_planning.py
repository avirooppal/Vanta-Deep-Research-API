import pytest
from unittest.mock import AsyncMock, MagicMock
from core.research.state import ResearchState, Finding, ValidatedSource
from core.research.evidence.models import AtomicClaim, ClaimType, SourceQuality, SourceRole
from core.research.reasoning.models import ResearchChallenge
from core.research.planning.brief import ResearchBrief, QuestionType
from core.research.synthesis.planner import audit_evidence, create_report_plan
from core.research.synthesis.models import ReportPlan, SectionPlan
from core.research.agents.synthesizer import SynthesizerAgent
from core.llm.types import LLMResponse


@pytest.mark.asyncio
async def test_audit_evidence_computes_metrics():
    state = ResearchState(question="Are solid-state batteries commercially viable?", max_rounds=3)
    state.brief = ResearchBrief(
        original_question=state.question,
        normalized_question=state.question,
        research_goal="Evaluate commercial viability of solid-state batteries by 2030",
        question_type=QuestionType.COMPARATIVE,
        sub_questions=["What is the cost?", "What is the manufacturing yield?"]
    )
    
    # Add claims and findings
    c1 = AtomicClaim(
        claim_id="clm_1",
        claim_text="Solid state cell costs are $150/kWh",
        claim_type=ClaimType.MEASUREMENT,
        source_url="https://nature.com/article1",
        confidence=0.8,
    )
    c2 = AtomicClaim(
        claim_id="clm_2",
        claim_text="Commercial production targeted for 2028",
        claim_type=ClaimType.ANNOUNCEMENT,
        source_url="https://company.com/pr",
        confidence=0.6,
    )
    state.claims.extend([c1, c2])
    
    v1 = ValidatedSource(
        url="https://nature.com/article1",
        title="Solid State Review",
        text="Review of solid state battery electrolytes.",
        trust_score=90,
        flags="",
        quality=SourceQuality(authority=90, primary_source_score=90, expertise=90),
    )
    v2 = ValidatedSource(
        url="https://company.com/pr",
        title="Company PR",
        text="Company announces breakthrough in 2028 targets.",
        trust_score=50,
        flags="PR",
        quality=SourceQuality(authority=50, primary_source_score=40, bias_risk=80),
    )
    state.sources.extend([v1, v2])
    
    state.challenges.append(ResearchChallenge(
        challenge_id="ch_1",
        target_conclusion="Commercial production targeted for 2028",
        vulnerability_explanation="Has this timeline been delayed before?",
        single_source_dependencies=["https://company.com/pr"],
    ))

    audit = audit_evidence(state)
    assert audit.audited_claims_count == 2
    assert audit.confidence_level in ["MODERATE EVIDENCE", "LIMITED EVIDENCE", "STRONG EVIDENCE"]


@pytest.mark.asyncio
async def test_create_report_plan_llm():
    state = ResearchState(question="What is the future of EV battery recycling?", max_rounds=3)
    audit = audit_evidence(state)
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='''
        {
            "title": "The Future of EV Battery Recycling",
            "executive_summary_bullets": ["Recycling efficiency exceeds 95% in hydrometallurgical labs", "Feedstock shortage limits commercial scale until 2030"],
            "key_findings": ["Feedstock availability is the primary constraint"],
            "sections": [
                {
                    "heading": "Technological Paradigms",
                    "objective": "Compare pyrometallurgy and hydrometallurgy",
                    "key_points": ["Hydro yields 95% purity"],
                    "counterevidence_points": ["High acid effluent treatment costs"],
                    "include_table": true,
                    "table_description": "Process efficiency comparison"
                }
            ],
            "unresolved_uncertainties": ["Long-term black mass pricing dynamics"]
        }
        ''',
        model="test",
        tokens_in=50,
        tokens_out=50,
    ))
    
    plan = await create_report_plan(state, audit, mock_llm)
    assert plan.title == "The Future of EV Battery Recycling"
    assert len(plan.executive_summary_bullets) == 2
    assert len(plan.sections) == 1
    assert plan.sections[0].heading == "Technological Paradigms"
    outline = plan.to_outline_prompt()
    assert "The Future of EV Battery Recycling" in outline
    assert "Technological Paradigms" in outline


@pytest.mark.asyncio
async def test_synthesizer_uses_report_plan():
    state = ResearchState(question="Assess commercial viability of quantum computing", max_rounds=3)
    state.report_plan = ReportPlan(
        title="Quantum Computing Commercial Viability",
        executive_summary_bullets=["NISQ era limits commercial applications to optimization heuristics"],
        sections=[
            SectionPlan(
                heading="Error Mitigation vs Fault Tolerance",
                objective="Evaluate logical qubit roadmaps",
            )
        ]
    )
    
    mock_llm = MagicMock()
    captured_messages = []
    
    async def fake_complete(messages, **kwargs):
        captured_messages.extend(messages)
        return LLMResponse(content="# Executive Summary\nQuantum computing is in early stage.\n\n## Error Mitigation\nAnalysis here.", model="test", tokens_in=50, tokens_out=50)
        
    mock_llm.complete = AsyncMock(side_effect=fake_complete)
    
    synthesizer = SynthesizerAgent(mock_llm)
    state.evolving_report = "Preliminary findings show 1000 physical qubits needed per logical qubit."
    report = await synthesizer.run(state)
    
    assert report.query == state.question
    # Check that prompt included outline
    sent_prompt = captured_messages[0].content
    assert "Planned Sections:" in sent_prompt
    assert "Error Mitigation vs Fault Tolerance" in sent_prompt

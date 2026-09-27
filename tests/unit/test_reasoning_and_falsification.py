"""
Phase 3 tests — Reasoning, Falsification, Contradictions & ChallengeAgent.
Pure-Python unit tests; no external network or service dependencies.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from core.research.reasoning.models import ContradictionType, ResearchChallenge, CoverageMap
from core.research.agents.contradiction import ContradictionAgent
from core.research.agents.challenge import ChallengeAgent
from core.research.state import ResearchState, Finding, Contradiction
from core.llm.types import LLMResponse


# ---------------------------------------------------------------------------
# Contradiction Root Cause Classification Tests
# ---------------------------------------------------------------------------

class TestContradictionClassification:
    @pytest.mark.asyncio
    async def test_contradiction_agent_classifies_type(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""[
                {
                    "description": "Market size estimate varies between $10B and $18B",
                    "source_urls": ["https://source-a.com", "https://source-b.com"],
                    "severity": "high",
                    "contradiction_type": "NUMERICAL_DISAGREEMENT",
                    "resolution_suggestion": "Source A covers only passenger EVs, whereas Source B includes commercial trucks."
                }
            ]""",
            tokens_in=120,
            tokens_out=80,
            model="test-model",
        )

        agent = ContradictionAgent(mock_llm)
        state = ResearchState(question="Market size", max_rounds=3)
        state.findings = [
            Finding(url="https://source-a.com", title="A", facts="Market size is $10B in 2025", round_number=1),
            Finding(url="https://source-b.com", title="B", facts="Market size is $18B in 2025", round_number=1),
        ]

        contradictions = await agent.run(state)

        assert len(contradictions) == 1
        c = contradictions[0]
        assert c.contradiction_type == "NUMERICAL_DISAGREEMENT"
        assert "passenger EVs" in c.resolution_suggestion


# ---------------------------------------------------------------------------
# ChallengeAgent / Devil's Advocate Tests
# ---------------------------------------------------------------------------

class TestChallengeAgent:
    @pytest.mark.asyncio
    async def test_challenge_agent_generates_falsification_attacks(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""[
                {
                    "target_conclusion": "Solid state batteries will achieve volume production by 2027",
                    "vulnerability_explanation": "Relies exclusively on corporate PR from a single OEM that has repeatedly delayed pilot milestones.",
                    "single_source_dependencies": ["Toyota PR announcement 2024"],
                    "competing_explanation": "Ceramic separator defect rates remain too high for high-speed roll-to-roll assembly.",
                    "missing_falsifying_evidence": ["Independent factory yield data"],
                    "suggested_investigation_query": "automotive solid state battery ceramic separator yield bottleneck"
                }
            ]""",
            tokens_in=150,
            tokens_out=100,
            model="test-model",
        )

        agent = ChallengeAgent(mock_llm)
        state = ResearchState(question="Solid state timeline", max_rounds=3)
        state.evolving_report = "Automakers plan volume launch by 2027 based on recent announcements."
        state.findings = [
            Finding(url="https://oem-pr.com/news", title="OEM PR", facts="Volume production planned for 2027.", round_number=1),
            Finding(url="https://industry.com/article", title="Industry news", facts="Plans announced for 2027 rollout.", round_number=1),
        ]

        challenges = await agent.run(state)

        assert len(challenges) == 1
        ch = challenges[0]
        assert "corporate PR" in ch.vulnerability_explanation
        assert "Toyota PR announcement 2024" in ch.single_source_dependencies
        assert "ceramic separator yield" in ch.suggested_investigation_query
        assert ch.challenge_id.startswith("ch_")


# ---------------------------------------------------------------------------
# CoverageMap Tests
# ---------------------------------------------------------------------------

class TestCoverageMap:
    def test_coverage_map_structure(self):
        cmap = CoverageMap(
            track_scores={"T1": 0.85, "T2": 0.40},
            overall_coverage=0.625,
            uncovered_sub_questions=["Cost per kWh trajectory"],
            should_stop=False,
        )
        assert cmap.overall_coverage == 0.625
        assert len(cmap.uncovered_sub_questions) == 1

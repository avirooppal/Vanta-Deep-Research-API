"""
Phase 1 tests — Research Planning & Query Diversity.
Pure-Python unit tests; no external network or service dependencies.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from core.research.planning.brief import QuestionType, ResearchBrief, understand_question
from core.research.planning.plan import SearchTrack, Hypothesis, ResearchPlan, create_research_plan
from core.research.agents.search import SearchAgent, is_query_novel
from core.research.agents.coordinator import CoordinatorAgent
from core.research.state import ResearchState, Finding
from core.llm.types import LLMResponse


# ---------------------------------------------------------------------------
# ResearchBrief Tests
# ---------------------------------------------------------------------------

class TestResearchBrief:
    @pytest.mark.asyncio
    async def test_understand_question_structured_output(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""{
                "normalized_question": "Commercial viability of solid-state batteries by 2030",
                "research_goal": "Assess technical yield and cost competitiveness vs Li-ion",
                "question_type": "FORECASTING",
                "scope": "Automotive battery market",
                "time_scope": "2024-2030",
                "entities": ["QuantumScape", "Toyota", "CATL"],
                "terminology": ["solid electrolyte", "dendrite formation", "dry coating"],
                "assumptions": ["Electric vehicles require >300Wh/kg pack density"],
                "sub_questions": [
                    "What is current manufacturing yield for ceramic separators?",
                    "What is projected cell cost ($/kWh) by 2030?"
                ],
                "required_evidence_types": ["peer_reviewed_literature", "SEC_filings"],
                "recency_requirement": "recent",
                "depth_requirement": "deep"
            }""",
            tokens_in=150,
            tokens_out=120,
            model="test-model",
        )

        brief = await understand_question("Will solid state batteries be viable by 2030?", mock_llm)

        assert brief.question_type == QuestionType.FORECASTING
        assert brief.normalized_question == "Commercial viability of solid-state batteries by 2030"
        assert len(brief.entities) == 3
        assert len(brief.sub_questions) == 2
        assert "QuantumScape" in brief.entities

    @pytest.mark.asyncio
    async def test_understand_question_graceful_fallback(self):
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("LLM error")

        brief = await understand_question("What is dark matter?", mock_llm)

        assert brief.question_type == QuestionType.OPEN_ENDED_EXPLORATION
        assert brief.original_question == "What is dark matter?"
        assert len(brief.sub_questions) >= 2


# ---------------------------------------------------------------------------
# ResearchPlan Tests
# ---------------------------------------------------------------------------

class TestResearchPlan:
    @pytest.mark.asyncio
    async def test_create_research_plan_tracks_and_hypotheses(self):
        brief = ResearchBrief(
            original_question="Will solid state batteries beat lithium-ion by 2030?",
            normalized_question="Solid state vs lithium-ion economics 2030",
            research_goal="Evaluate commercial timeline and cost bottlenecks",
            question_type=QuestionType.COMPARATIVE,
            sub_questions=[
                "Technical manufacturing bottlenecks",
                "Cost per kWh projections",
            ],
            entities=["Toyota", "QuantumScape"],
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""{
                "search_tracks": [
                    {
                        "track_id": "T1",
                        "sub_question": "Manufacturing scale and yield rates",
                        "focus_areas": ["ceramic separator cracks", "roll-to-roll throughput"],
                        "preferred_source_types": ["academic_paper", "official_filing"],
                        "query_templates": ["solid electrolyte roll-to-roll yield"],
                        "is_critical": true
                    },
                    {
                        "track_id": "T2",
                        "sub_question": "Cost comparison ($/kWh)",
                        "focus_areas": ["active material cost", "capex per GWh"],
                        "preferred_source_types": ["industry_report"],
                        "query_templates": ["solid state cell cost per kWh 2030"],
                        "is_critical": true
                    }
                ],
                "hypotheses": [
                    {
                        "hypothesis_id": "H1",
                        "statement": "Solid-state batteries reach parity by 2028.",
                        "competing_explanation": "Manufacturing defects delay volume production beyond 2030.",
                        "supporting_evidence_needed": ["Verified pilot lines producing >100MWh/yr"],
                        "falsification_evidence_needed": ["Continued delays in announced OEM models"]
                    }
                ],
                "contradiction_targets": [
                    "Announced OEM timeline vs analyst consensus"
                ],
                "stopping_conditions": [
                    "Empirical yield and cost figures verified by independent sources"
                ]
            }""",
            tokens_in=200,
            tokens_out=180,
            model="test-model",
        )

        plan = await create_research_plan(brief, mock_llm)

        assert len(plan.search_tracks) == 2
        assert plan.search_tracks[0].track_id == "T1"
        assert len(plan.hypotheses) == 1
        assert "parity by 2028" in plan.hypotheses[0].statement
        assert len(plan.contradiction_targets) == 1

        summary = plan.to_text_summary()
        assert "Manufacturing scale" in summary
        assert "Competing Hypotheses" in summary


# ---------------------------------------------------------------------------
# SearchAgent Multi-Family & Novelty Tests
# ---------------------------------------------------------------------------

class TestSearchAgentUpgrade:
    def test_novelty_detector(self):
        seen = {
            "solid state battery commercialization timeline",
            "toyota solid state battery announcement",
        }

        # Near duplicate should NOT be novel
        assert not is_query_novel("solid state battery commercialization timeline", seen)
        assert not is_query_novel("solid state battery commercialization", seen)

        # Fresh query family should be novel
        assert is_query_novel("site:nature.com lithium dendrite suppression ceramic electrolyte", seen)
        assert is_query_novel("cost per kilowatt hour pack level manufacturing yield", seen)

    @pytest.mark.asyncio
    async def test_search_agent_generates_diverse_queries_with_plan(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""[
                "solid state battery commercialization 2025 2030",
                "site:gov solid electrolyte battery grant awards energy density",
                "peer reviewed solid state battery manufacturing dendrite challenges",
                "automotive solid state battery delayed production announcements"
            ]""",
            tokens_in=100,
            tokens_out=80,
            model="test-model",
        )

        agent = SearchAgent(mock_llm)
        state = ResearchState(question="Solid state batteries future", max_rounds=3)
        brief = ResearchBrief(
            original_question="Solid state batteries future",
            normalized_question="Solid state batteries future",
            research_goal="Future of batteries",
        )
        state.plan = ResearchPlan(
            primary_question="Solid state batteries future",
            brief=brief,
            search_tracks=[SearchTrack(track_id="T1", sub_question="Manufacturing challenges")],
        )

        queries = await agent.run(state)

        assert len(queries) == 4
        assert any("site:gov" in q for q in queries)
        assert any("delayed" in q for q in queries)


# ---------------------------------------------------------------------------
# Coordinator Track-Awareness Tests
# ---------------------------------------------------------------------------

class TestCoordinatorUpgrade:
    @pytest.mark.asyncio
    async def test_coordinator_continues_when_evidence_is_early(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="CONTINUE",
            tokens_in=50,
            tokens_out=5,
            model="test-model",
        )

        coordinator = CoordinatorAgent(mock_llm)
        state = ResearchState(question="Target question", max_rounds=3)
        state.current_round = 1
        state.findings = [
            Finding(url="https://x.com", title="X", facts="Fact 1", round_number=1)
        ]

        decision = await coordinator.run(state)
        assert decision == "CONTINUE"

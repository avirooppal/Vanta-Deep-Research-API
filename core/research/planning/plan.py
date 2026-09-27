"""
Vanta Phase 1 — ResearchPlan & Track Generation.

Generates an actionable multi-track research plan from a ResearchBrief:
- Concrete search tracks mapped to sub-questions
- Competing hypotheses for analytical falsification
- Contradiction targets and explicit stopping conditions
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.optimizer import strip_thinking
from core.research.planning.brief import ResearchBrief

logger = logging.getLogger(__name__)


@dataclass
class SearchTrack:
    """A distinct exploration track addressing a specific sub-question."""
    track_id: str
    sub_question: str
    focus_areas: list[str] = field(default_factory=list)
    preferred_source_types: list[str] = field(default_factory=list)
    query_templates: list[str] = field(default_factory=list)
    is_critical: bool = True
    coverage_score: float = 0.0  # 0.0 to 1.0


@dataclass
class Hypothesis:
    """A tentative explanation or claim to be tested and actively falsified."""
    hypothesis_id: str
    statement: str
    competing_explanation: str
    supporting_evidence_needed: list[str] = field(default_factory=list)
    falsification_evidence_needed: list[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """Comprehensive blueprint guiding the multi-agent research loop."""
    primary_question: str
    brief: ResearchBrief
    sub_questions: list[str] = field(default_factory=list)
    search_tracks: list[SearchTrack] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    contradiction_targets: list[str] = field(default_factory=list)
    stopping_conditions: list[str] = field(default_factory=list)

    def to_text_summary(self) -> str:
        """Produce a formatted overview for prompts and state reporting."""
        lines = [
            f"=== Research Plan for: {self.primary_question} ===",
            f"Goal: {self.brief.research_goal}",
            f"Question Type: {self.brief.question_type.value} | Scope: {self.brief.scope} ({self.brief.time_scope})",
            "\nSearch Tracks:",
        ]
        for t in self.search_tracks:
            lines.append(f"  [{t.track_id}] {t.sub_question}")
            if t.focus_areas:
                lines.append(f"       Focus: {', '.join(t.focus_areas)}")
            if t.preferred_source_types:
                lines.append(f"       Sources: {', '.join(t.preferred_source_types)}")

        if self.hypotheses:
            lines.append("\nCompeting Hypotheses:")
            for h in self.hypotheses:
                lines.append(f"  - [{h.hypothesis_id}] Primary: {h.statement}")
                lines.append(f"       Alternative: {h.competing_explanation}")

        if self.contradiction_targets:
            lines.append("\nKey Areas for Disagreement / Contradiction Check:")
            for c in self.contradiction_targets:
                lines.append(f"  - {c}")

        if self.stopping_conditions:
            lines.append("\nStopping Conditions:")
            for s in self.stopping_conditions:
                lines.append(f"  - {s}")

        return "\n".join(lines)


RESEARCH_PLANNER_SYSTEM = """You are the Lead Research Strategist at Vanta.
Given a ResearchBrief, generate a rigorous, hypothesis-driven ResearchPlan.

Requirements:
1. Decompose the brief into 3-5 distinct SearchTracks. Each track must target a specific sub-question
   (e.g., technical status, cost/economics, historical precedent/delays, commercialization claims).
2. Propose 1-2 competing hypotheses to test with evidence and attempt to falsify.
3. List contradiction targets (e.g. market size variances, delivery timeline promises vs real yields).
4. Define measurable stopping conditions.

Respond strictly in JSON with this structure:
{
    "search_tracks": [
        {
            "track_id": "T1",
            "sub_question": "...",
            "focus_areas": ["...", "..."],
            "preferred_source_types": ["academic_paper", "official_filing", "industry_report"],
            "query_templates": ["..."],
            "is_critical": true
        }
    ],
    "hypotheses": [
        {
            "hypothesis_id": "H1",
            "statement": "Primary hypothesis",
            "competing_explanation": "Alternative counter-explanation",
            "supporting_evidence_needed": ["metric X"],
            "falsification_evidence_needed": ["metric Y demonstrating failure"]
        }
    ],
    "contradiction_targets": [
        "Conflicting timeline forecasts between OEM statements and analyst estimates"
    ],
    "stopping_conditions": [
        "Identified independently verified yield and cost figures",
        "Resolved discrepancies between announced and actual production timelines"
    ]
}"""


async def create_research_plan(brief: ResearchBrief, llm: LLMClient) -> ResearchPlan:
    """Generate a ResearchPlan from a ResearchBrief."""
    user_prompt = (
        f"Research Brief:\n"
        f"- Original Question: {brief.original_question}\n"
        f"- Goal: {brief.research_goal}\n"
        f"- Question Type: {brief.question_type.value}\n"
        f"- Entities: {', '.join(brief.entities) if brief.entities else 'None'}\n"
        f"- Sub-questions:\n" + "\n".join(f"  * {sq}" for sq in brief.sub_questions)
    )

    messages = [
        LLMMessage(role="system", content=RESEARCH_PLANNER_SYSTEM),
        LLMMessage(role="user", content=user_prompt),
    ]

    try:
        response = await llm.complete(messages, complexity="low", agent_name="ResearchPlannerAgent")
        content = strip_thinking(response.content).strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        parsed = json.loads(content.strip())

        tracks = []
        for i, t in enumerate(parsed.get("search_tracks", [])):
            tracks.append(SearchTrack(
                track_id=t.get("track_id", f"T{i+1}"),
                sub_question=t.get("sub_question", brief.sub_questions[i % len(brief.sub_questions)]),
                focus_areas=t.get("focus_areas", []),
                preferred_source_types=t.get("preferred_source_types", []),
                query_templates=t.get("query_templates", []),
                is_critical=t.get("is_critical", True),
            ))

        if not tracks:
            # Fallback tracks from brief sub-questions
            tracks = [
                SearchTrack(track_id=f"T{i+1}", sub_question=sq, is_critical=True)
                for i, sq in enumerate(brief.sub_questions)
            ]

        hypotheses = []
        for i, h in enumerate(parsed.get("hypotheses", [])):
            hypotheses.append(Hypothesis(
                hypothesis_id=h.get("hypothesis_id", f"H{i+1}"),
                statement=h.get("statement", ""),
                competing_explanation=h.get("competing_explanation", ""),
                supporting_evidence_needed=h.get("supporting_evidence_needed", []),
                falsification_evidence_needed=h.get("falsification_evidence_needed", []),
            ))

        return ResearchPlan(
            primary_question=brief.original_question,
            brief=brief,
            sub_questions=brief.sub_questions,
            search_tracks=tracks,
            hypotheses=hypotheses,
            contradiction_targets=parsed.get("contradiction_targets", []),
            stopping_conditions=parsed.get("stopping_conditions", []),
        )

    except Exception as exc:
        logger.warning(f"Research planning generation failed: {exc}, using fallback plan")
        tracks = [
            SearchTrack(track_id=f"T{i+1}", sub_question=sq, is_critical=True)
            for i, sq in enumerate(brief.sub_questions)
        ]
        return ResearchPlan(
            primary_question=brief.original_question,
            brief=brief,
            sub_questions=brief.sub_questions,
            search_tracks=tracks,
            hypotheses=[
                Hypothesis(
                    hypothesis_id="H1",
                    statement=f"The prevailing market consensus regarding {brief.original_question} is accurate.",
                    competing_explanation=f"Key technical, economic, or regulatory barriers impede the consensus view.",
                )
            ],
            contradiction_targets=["Variance in timelines, cost figures, or performance claims"],
            stopping_conditions=["All major sub-questions covered by independent evidence"],
        )

"""
Vanta Phase 1 — Question Understanding & ResearchBrief.

Transforms raw user queries into a structured ResearchBrief capturing:
- Question intent classification
- Scope, time horizon, and entities
- Decomposition into core sub-questions
- Required evidence types and recency requirements
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.optimizer import strip_thinking

logger = logging.getLogger(__name__)


class QuestionType(str, Enum):
    DESCRIPTIVE = "DESCRIPTIVE"
    COMPARATIVE = "COMPARATIVE"
    CAUSAL = "CAUSAL"
    EXPLANATORY = "EXPLANATORY"
    FORECASTING = "FORECASTING"
    TECHNICAL = "TECHNICAL"
    SCIENTIFIC = "SCIENTIFIC"
    MARKET = "MARKET"
    COMPANY = "COMPANY"
    PRODUCT = "PRODUCT"
    HISTORICAL = "HISTORICAL"
    POLICY = "POLICY"
    LITERATURE_REVIEW = "LITERATURE_REVIEW"
    DUE_DILIGENCE = "DUE_DILIGENCE"
    FACT_CHECK = "FACT_CHECK"
    OPEN_ENDED_EXPLORATION = "OPEN_ENDED_EXPLORATION"


@dataclass
class ResearchBrief:
    """Structured analytical brief derived from user's research inquiry."""
    original_question: str
    normalized_question: str
    research_goal: str
    question_type: QuestionType = QuestionType.OPEN_ENDED_EXPLORATION
    scope: str = "global"
    time_scope: str = "current"
    entities: list[str] = field(default_factory=list)
    terminology: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    sub_questions: list[str] = field(default_factory=list)
    required_evidence_types: list[str] = field(default_factory=list)
    recency_requirement: str = "recent"  # "breaking" | "recent" | "historical" | "all_time"
    depth_requirement: str = "deep"      # "quick" | "standard" | "deep" | "forensic"

    def to_dict(self) -> dict:
        return {
            "original_question": self.original_question,
            "normalized_question": self.normalized_question,
            "research_goal": self.research_goal,
            "question_type": self.question_type.value,
            "scope": self.scope,
            "time_scope": self.time_scope,
            "entities": self.entities,
            "terminology": self.terminology,
            "assumptions": self.assumptions,
            "sub_questions": self.sub_questions,
            "required_evidence_types": self.required_evidence_types,
            "recency_requirement": self.recency_requirement,
            "depth_requirement": self.depth_requirement,
        }


QUESTION_UNDERSTANDING_SYSTEM = """You are a Principal Research Analyst at Vanta.
Analyze the user's research question and create a structured analytical ResearchBrief.

Classify the question type from:
DESCRIPTIVE, COMPARATIVE, CAUSAL, EXPLANATORY, FORECASTING, TECHNICAL, SCIENTIFIC,
MARKET, COMPANY, PRODUCT, HISTORICAL, POLICY, LITERATURE_REVIEW, DUE_DILIGENCE,
FACT_CHECK, OPEN_ENDED_EXPLORATION.

Decompose the question into 3-6 essential sub-questions covering different angles
(e.g., technical feasibility, economic/cost reality, competitive landscape, historical failure modes, skepticism).

Respond in JSON only with these exact fields:
{
    "normalized_question": "Clean, precise phrasing of core question",
    "research_goal": "What decision or understanding the research must deliver",
    "question_type": "FORECASTING",
    "scope": "Geographic / domain boundaries",
    "time_scope": "e.g., 2024-2030 or current",
    "entities": ["Company A", "Technology B"],
    "terminology": ["Key acronyms or terms"],
    "assumptions": ["Underlying assumptions made by question"],
    "sub_questions": [
        "Sub-question 1",
        "Sub-question 2",
        "Sub-question 3"
    ],
    "required_evidence_types": ["peer_reviewed_literature", "financial_filings", "independent_benchmarks"],
    "recency_requirement": "recent",
    "depth_requirement": "deep"
}"""


async def understand_question(question: str, llm: LLMClient) -> ResearchBrief:
    """Analyze research question and build a structured ResearchBrief."""
    messages = [
        LLMMessage(role="system", content=QUESTION_UNDERSTANDING_SYSTEM),
        LLMMessage(role="user", content=f"Research Question: {question}"),
    ]

    try:
        response = await llm.complete(messages, complexity="low", agent_name="QuestionUnderstandingAgent")
        content = strip_thinking(response.content).strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        parsed = json.loads(content.strip())

        q_type_str = parsed.get("question_type", "OPEN_ENDED_EXPLORATION").upper()
        try:
            q_type = QuestionType(q_type_str)
        except ValueError:
            q_type = QuestionType.OPEN_ENDED_EXPLORATION

        sub_qs = parsed.get("sub_questions", [])
        if not sub_qs:
            sub_qs = [question]

        return ResearchBrief(
            original_question=question,
            normalized_question=parsed.get("normalized_question", question),
            research_goal=parsed.get("research_goal", f"Thorough investigation of {question}"),
            question_type=q_type,
            scope=parsed.get("scope", "global"),
            time_scope=parsed.get("time_scope", "current"),
            entities=parsed.get("entities", []),
            terminology=parsed.get("terminology", []),
            assumptions=parsed.get("assumptions", []),
            sub_questions=sub_qs,
            required_evidence_types=parsed.get("required_evidence_types", ["web_sources", "news"]),
            recency_requirement=parsed.get("recency_requirement", "recent"),
            depth_requirement=parsed.get("depth_requirement", "deep"),
        )
    except Exception as exc:
        logger.warning(f"Question understanding failed: {exc}, using fallback brief")
        return ResearchBrief(
            original_question=question,
            normalized_question=question,
            research_goal=f"Comprehensive analysis of {question}",
            question_type=QuestionType.OPEN_ENDED_EXPLORATION,
            sub_questions=[
                f"What is the current state and evidence regarding {question}?",
                f"What are the major challenges, bottlenecks, and counterarguments?",
                f"What are the key quantitative metrics and timelines?",
            ],
            entities=[],
            required_evidence_types=["primary_sources", "expert_analysis"],
        )

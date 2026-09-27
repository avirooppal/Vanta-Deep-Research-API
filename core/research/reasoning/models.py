"""
Vanta Phase 3 — Reasoning, Falsification & Coverage Models.

Empowers Vanta to challenge its own emerging conclusions, categorize contradictions
into root causes (definitional, temporal, methodological, numerical), and measure
systematic evidence coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ContradictionType(str, Enum):
    DIRECT_CONTRADICTION = "DIRECT_CONTRADICTION"
    NUMERICAL_DISAGREEMENT = "NUMERICAL_DISAGREEMENT"
    TEMPORAL_DISAGREEMENT = "TEMPORAL_DISAGREEMENT"
    DEFINITION_DIFFERENCE = "DEFINITION_DIFFERENCE"
    METHODOLOGICAL_DIFFERENCE = "METHODOLOGICAL_DIFFERENCE"
    FORECAST_DIFFERENCE = "FORECAST_DIFFERENCE"


@dataclass
class ResearchChallenge:
    """An adversarial challenge attacking an emerging conclusion or assumption."""
    challenge_id: str
    target_conclusion: str
    vulnerability_explanation: str
    single_source_dependencies: list[str] = field(default_factory=list)
    competing_explanation: str = ""
    missing_falsifying_evidence: list[str] = field(default_factory=list)
    suggested_investigation_query: str = ""

    def to_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "target_conclusion": self.target_conclusion,
            "vulnerability_explanation": self.vulnerability_explanation,
            "single_source_dependencies": self.single_source_dependencies,
            "competing_explanation": self.competing_explanation,
            "missing_falsifying_evidence": self.missing_falsifying_evidence,
            "suggested_investigation_query": self.suggested_investigation_query,
        }


@dataclass
class CoverageMap:
    """Coverage audit across sub-questions and search tracks."""
    track_scores: dict[str, float] = field(default_factory=dict)  # track_id -> score 0.0 to 1.0
    overall_coverage: float = 0.0
    uncovered_sub_questions: list[str] = field(default_factory=list)
    should_stop: bool = False
    stop_reason: str = ""

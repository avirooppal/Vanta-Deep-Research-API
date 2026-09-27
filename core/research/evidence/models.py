"""
Vanta Phase 2 — Structured Evidence Models: Claims, SourceQuality & Lineage.

Separates:
1. EVIDENCE (what sources say)
2. INFERENCE (reasoned conclusions from multiple facts)
3. ANALYSIS (synthesis and evaluation)

Enforces atomic claims, multidimensional source scoring, and quantitative extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ClaimType(str, Enum):
    FACT = "FACT"
    MEASUREMENT = "MEASUREMENT"
    ESTIMATE = "ESTIMATE"
    FORECAST = "FORECAST"
    OPINION = "OPINION"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    ALLEGATION = "ALLEGATION"
    INFERENCE = "INFERENCE"
    CAUSAL_CLAIM = "CAUSAL_CLAIM"
    COMPARISON = "COMPARISON"
    DEFINITION = "DEFINITION"


class SourceRole(str, Enum):
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    SUPPORTING_EVIDENCE = "SUPPORTING_EVIDENCE"
    CONTEXT = "CONTEXT"
    COUNTEREVIDENCE = "COUNTEREVIDENCE"
    EXPERT_INTERPRETATION = "EXPERT_INTERPRETATION"
    DATA_SOURCE = "DATA_SOURCE"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


@dataclass
class QuantitativeFact:
    """Structured numerical datum with temporal and unit calibration."""
    metric_name: str
    value: str | float
    unit: str = ""
    period: str = ""           # e.g., "FY2024", "Q3 2025", "by 2030"
    is_forecast: bool = False
    context: str = ""


@dataclass
class SourceQuality:
    """Multidimensional evaluation of source trustworthiness and methodology."""
    authority: int = 50                 # 0-100 institutional / domain stature
    primary_source_score: int = 50      # 0-100 (100 = official filing / direct dataset)
    expertise: int = 50                 # 0-100 domain author expertise
    methodological_quality: int = 50    # 0-100 scientific / sampling rigor
    recency_score: int = 50             # 0-100 freshness relative to inquiry
    bias_risk: int = 20                 # 0-100 (0 = neutral, 100 = extreme commercial/ideological bias)
    overall_trust: int = 50             # Computed composite score

    @classmethod
    def compute(
        cls,
        authority: int = 50,
        primary_source_score: int = 50,
        expertise: int = 50,
        methodological_quality: int = 50,
        recency_score: int = 50,
        bias_risk: int = 20,
    ) -> SourceQuality:
        # Weighted composite penalizing bias
        base = (
            authority * 0.25 +
            primary_source_score * 0.25 +
            expertise * 0.20 +
            methodological_quality * 0.20 +
            recency_score * 0.10
        )
        bias_penalty = (bias_risk / 100.0) * 25.0
        overall = int(max(0, min(100, base - bias_penalty)))
        return cls(
            authority=authority,
            primary_source_score=primary_source_score,
            expertise=expertise,
            methodological_quality=methodological_quality,
            recency_score=recency_score,
            bias_risk=bias_risk,
            overall_trust=overall,
        )


@dataclass
class SourceLineage:
    """Detects and tracks syndicated content, wire reports, and press release origins."""
    source_url: str
    quoted_source_url: Optional[str] = None
    is_press_release: bool = False
    syndicated_agency: Optional[str] = None  # e.g., "Reuters", "PR Newswire", "AP"
    cluster_id: Optional[str] = None


@dataclass
class AtomicClaim:
    """Atomic, verifiable unit of factual evidence extracted from a source."""
    claim_id: str
    claim_text: str
    claim_type: ClaimType = ClaimType.FACT
    source_url: str = ""
    source_title: str = ""
    supporting_passage: str = ""
    entities: list[str] = field(default_factory=list)
    quantitative_facts: list[QuantitativeFact] = field(default_factory=list)
    publication_date: Optional[str] = None
    event_date: Optional[str] = None
    confidence: str = "MODERATE EVIDENCE"  # "STRONG EVIDENCE" | "MODERATE EVIDENCE" | "LIMITED EVIDENCE"
    source_role: SourceRole = SourceRole.SUPPORTING_EVIDENCE
    round_number: int = 1

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type.value,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "supporting_passage": self.supporting_passage,
            "entities": self.entities,
            "quantitative_facts": [q.__dict__ for q in self.quantitative_facts],
            "publication_date": self.publication_date,
            "event_date": self.event_date,
            "confidence": self.confidence,
            "source_role": self.source_role.value,
            "round_number": self.round_number,
        }

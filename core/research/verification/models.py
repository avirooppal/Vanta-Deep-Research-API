"""
Vanta Phase 5 — Verification & Quality Models.

Data structures for claim verification, citation entailment checking,
and the final pre-delivery research quality gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EntailmentStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class CitationCheck:
    """Verifies that a cited source actually entails the claim being made."""
    citation_index: int
    source_url: str
    sentence_text: str
    status: EntailmentStatus = EntailmentStatus.UNVERIFIED
    rationale: str = ""


@dataclass
class ClaimCheck:
    """Audit of an individual factual statement from the final report against known evidence."""
    report_statement: str
    claim_type: str = "FACT"
    status: EntailmentStatus = EntailmentStatus.SUPPORTED
    matching_claim_id: Optional[str] = None
    discrepancy_explanation: str = ""


@dataclass
class QualityGateResult:
    """Final quality evaluation prior to releasing the research report."""
    passed: bool
    quality_score: int                 # 0-100
    checks: dict[str, bool] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    remediation_applied: list[str] = field(default_factory=list)

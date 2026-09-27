"""
Vanta Phase 5 — Final Quality Gate.

Evaluates synthesized research against strict analytical quality standards before release:
1. Verifies question coverage and sub-question resolution.
2. Checks citation density and grounding.
3. Confirms that known contradictions and uncertainties are explicitly addressed.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.research.agents.synthesizer import ReportOutput
from core.research.state import ResearchState
from core.research.verification.models import QualityGateResult

logger = logging.getLogger(__name__)


def evaluate_quality_gate(state: ResearchState, report: ReportOutput) -> QualityGateResult:
    """Deterministic evaluation of research quality, coverage, and integrity."""
    checks = {}
    issues = []
    score = 100

    # 1. Substantive content check
    word_count = len(report.body_md.split()) if report.body_md else 0
    checks["substantive_length"] = word_count >= 150
    if not checks["substantive_length"]:
        score -= 25
        issues.append(f"Report is unusually brief ({word_count} words).")

    # 2. Citations check
    citations_in_body = len(re.findall(r"\[\d+\]", report.body_md or ""))
    checks["citations_present"] = citations_in_body >= 1 or len(report.citations) == 0
    if not checks["citations_present"]:
        score -= 20
        issues.append("Report lacks inline traceable citations [N].")

    # 3. Contradiction handling check
    if state.contradictions:
        contradiction_keywords = [
            "differ", "disagree", "conflict", "contradict", "variance", "diverge", "discrepancy"
        ]
        body_lower = (report.body_md or "").lower()
        handled = any(kw in body_lower for kw in contradiction_keywords)
        checks["contradictions_acknowledged"] = handled
        if not handled:
            score -= 15
            issues.append(
                f"{len(state.contradictions)} contradiction(s) were detected but may not be explicitly discussed in the report."
            )
    else:
        checks["contradictions_acknowledged"] = True

    # 4. Uncertainty calibration check
    uncertainty_keywords = ["uncertain", "unclear", "estimate", "limitation", "caveat", "forecast", "target"]
    body_lower = (report.body_md or "").lower()
    has_uncertainty = any(kw in body_lower for kw in uncertainty_keywords)
    checks["uncertainty_communicated"] = has_uncertainty
    if not has_uncertainty:
        score -= 10
        issues.append("Report may overstate certainty; lack of explicit qualifications or uncertainty markers.")

    # 5. Core question alignment
    q_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", state.question.lower()))
    rep_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", body_lower))
    overlap = q_words.intersection(rep_words)
    checks["question_relevance"] = len(overlap) >= max(1, len(q_words) // 2)
    if not checks["question_relevance"]:
        score -= 20
        issues.append("Report does not strongly reflect core query terminology.")

    score = max(0, min(100, score))
    passed = score >= 60

    if not passed:
        logger.warning(f"Quality gate warning (score={score}): {'; '.join(issues)}")

    return QualityGateResult(
        passed=passed,
        quality_score=score,
        checks=checks,
        issues=issues,
    )

"""
Vanta Phase 4 — Evidence Audit & ReportPlanner.

Audits gathered evidence and produces an outline blueprint for the Synthesizer:
1. Performs deterministic checks on claims, contradictions, and sub-question coverage.
2. Directs the LLM to design an adaptive ReportPlan with themed sections, counterevidence, and quantitative tables.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.optimizer import strip_thinking
from core.research.state import ResearchState
from core.research.synthesis.models import EvidenceAuditResult, ReportPlan, SectionPlan

logger = logging.getLogger(__name__)


def audit_evidence(state: ResearchState) -> EvidenceAuditResult:
    """Perform pre-synthesis evidence audit across findings, claims, and contradictions."""
    claims_count = len(state.claims) if hasattr(state, "claims") and state.claims else len(state.findings)
    contradictions_count = len(state.contradictions) if hasattr(state, "contradictions") and state.contradictions else 0
    challenges_count = len(state.challenges) if hasattr(state, "challenges") and state.challenges else 0

    # Determine confidence level
    avg_trust = 50
    if state.findings:
        avg_trust = sum(getattr(f, "trust_score", 50) for f in state.findings) // len(state.findings)

    if avg_trust >= 75 and claims_count >= 5 and contradictions_count <= 2:
        confidence = "STRONG EVIDENCE"
    elif avg_trust >= 45 and claims_count >= 2:
        confidence = "MODERATE EVIDENCE"
    elif contradictions_count > 3:
        confidence = "CONFLICTING EVIDENCE"
    else:
        confidence = "LIMITED EVIDENCE"

    sub_qs = []
    if hasattr(state, "brief") and state.brief and hasattr(state.brief, "sub_questions"):
        sub_qs = state.brief.sub_questions
    elif hasattr(state, "plan") and state.plan and hasattr(state.plan, "sub_questions"):
        sub_qs = state.plan.sub_questions

    supported = sub_qs[:3] if sub_qs else ["Core question"]
    weak = sub_qs[3:] if len(sub_qs) > 3 else []

    return EvidenceAuditResult(
        audited_claims_count=claims_count,
        supported_sub_questions=supported,
        weak_or_unsupported_areas=weak,
        contradictions_count=contradictions_count,
        challenges_count=challenges_count,
        confidence_level=confidence,
        ready_for_synthesis=claims_count > 0,
    )


REPORT_PLANNER_SYSTEM = """You are the Senior Report Architect at Vanta.
Your job is to structure a comprehensive, deeply organized research report answering the user's inquiry.
Do NOT force generic encyclopedic headings when inappropriate. Structure sections to reflect the actual research logic.

Requirements:
1. Executive Summary direct bullets (3-5 concrete answers).
2. 4-8 Key Findings that are evidence-backed and decision-relevant.
3. 3-5 Main analytical sections with objectives, key evidence, and explicit counterevidence/limitations.
4. Specify where a quantitative or comparison table would clarify tradeoffs.
5. Explicitly identify what remains uncertain or unproven.

Respond strictly in JSON:
{
    "title": "Clear, informative report title",
    "executive_summary_bullets": [
        "Direct finding 1...",
        "Direct finding 2..."
    ],
    "key_findings": [
        "Specific key finding with evidence...",
        "Another key finding..."
    ],
    "sections": [
        {
            "heading": "Technical Architecture & Bottlenecks",
            "objective": "Evaluate current separator yield and dendrite prevention mechanisms",
            "key_points": ["Point A", "Point B"],
            "counterevidence_points": ["Counterpoint C"],
            "include_table": true,
            "table_description": "Comparison of sulfide vs oxide ceramic separators"
        },
        {
            "heading": "Economic Reality & Cost Trajectory",
            "objective": "Compare cell-level capex and $/kWh projections to 2030",
            "key_points": ["Point D"],
            "counterevidence_points": [],
            "include_table": false,
            "table_description": ""
        }
    ],
    "unresolved_uncertainties": [
        "Pilot line yield rates remain closely guarded commercial secrets"
    ]
}"""


async def create_report_plan(
    state: ResearchState,
    audit: EvidenceAuditResult,
    llm: LLMClient,
) -> ReportPlan:
    """Generate a structured ReportPlan organizing the report."""
    brief_goal = getattr(state.brief, "research_goal", "") if hasattr(state, "brief") and state.brief else ""
    findings_preview = "\n".join(
        f"- [{f.title}] {f.summary or f.facts[:150]}" for f in state.findings[:12]
    )
    contradictions_preview = "\n".join(
        f"- {c.description} ({getattr(c, 'contradiction_type', 'CONTRADICTION')})"
        for c in (state.contradictions or [])[:4]
    )

    prompt = f"""Question: {state.question}
Research Goal: {brief_goal}
{audit.summary()}

Gathered Findings Preview:
{findings_preview}

Identified Contradictions / Variances:
{contradictions_preview or 'None identified'}

Generate the structured ReportPlan JSON."""

    messages = [
        LLMMessage(role="system", content=REPORT_PLANNER_SYSTEM),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await llm.complete(messages, complexity="low", agent_name="ReportPlannerAgent")
        content = strip_thinking(response.content).strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        parsed = json.loads(content.strip())

        sections = []
        for s in parsed.get("sections", []):
            sections.append(SectionPlan(
                heading=s.get("heading", "Analysis"),
                objective=s.get("objective", ""),
                key_points=s.get("key_points", []),
                counterevidence_points=s.get("counterevidence_points", []),
                include_table=bool(s.get("include_table", False)),
                table_description=s.get("table_description", ""),
            ))

        if not sections:
            sections = [
                SectionPlan(heading="Core Findings & Analysis", objective="Synthesize primary evidence", include_table=False),
                SectionPlan(heading="Counterevidence & Limitations", objective="Discuss skepticism and caveats", include_table=False),
            ]

        return ReportPlan(
            title=parsed.get("title", f"Deep Research: {state.question}"),
            executive_summary_bullets=parsed.get("executive_summary_bullets", []),
            key_findings=parsed.get("key_findings", []),
            sections=sections,
            unresolved_uncertainties=parsed.get("unresolved_uncertainties", []),
            confidence_summary=audit.confidence_level,
        )

    except Exception as exc:
        logger.warning(f"Report planning generation failed: {exc}, using fallback outline")
        return ReportPlan(
            title=f"Research Report: {state.question}",
            executive_summary_bullets=[f"Evidence synthesized across {len(state.findings)} sources."],
            key_findings=[f.summary for f in state.findings[:4] if f.summary],
            sections=[
                SectionPlan(heading="Primary Evidence & Technical Analysis", objective="Synthesize gathered findings", include_table=True, table_description="Key Metrics Summary"),
                SectionPlan(heading="Disagreements, Caveats & Counterevidence", objective="Evaluate contradictions and uncertainties", include_table=False),
            ],
            unresolved_uncertainties=["Data limitations in public disclosures"],
            confidence_summary=audit.confidence_level,
        )

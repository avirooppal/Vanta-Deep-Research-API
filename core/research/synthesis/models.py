"""
Vanta Phase 4 — Synthesis Models: EvidenceAudit, SectionPlan & ReportPlan.

Prevents premature or unorganized report synthesis by requiring:
1. EvidenceAudit checking claim support and uncertainty
2. Structured ReportPlan outlining section objectives, counterevidence, and data tables
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SectionPlan:
    """Blueprint for an individual analytical section in the final report."""
    heading: str
    objective: str
    key_points: list[str] = field(default_factory=list)
    counterevidence_points: list[str] = field(default_factory=list)
    include_table: bool = False
    table_description: str = ""
    sub_questions_addressed: list[str] = field(default_factory=list)


@dataclass
class EvidenceAuditResult:
    """Audit of gathered evidence before entering report synthesis."""
    audited_claims_count: int
    supported_sub_questions: list[str] = field(default_factory=list)
    weak_or_unsupported_areas: list[str] = field(default_factory=list)
    contradictions_count: int = 0
    challenges_count: int = 0
    confidence_level: str = "MODERATE EVIDENCE"  # STRONG, MODERATE, LIMITED, CONFLICTING
    ready_for_synthesis: bool = True

    def summary(self) -> str:
        return (
            f"Evidence Audit: {self.audited_claims_count} claims vetted | "
            f"Confidence: {self.confidence_level} | "
            f"Supported sub-questions: {len(self.supported_sub_questions)} | "
            f"Weak areas: {len(self.weak_or_unsupported_areas)}"
        )


@dataclass
class ReportPlan:
    """Comprehensive blueprint organizing the final deep research report."""
    title: str
    executive_summary_bullets: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    sections: list[SectionPlan] = field(default_factory=list)
    unresolved_uncertainties: list[str] = field(default_factory=list)
    confidence_summary: str = ""

    def to_outline_prompt(self) -> str:
        lines = [
            f"Report Title: {self.title}",
            "\nExecutive Summary Direct Findings:",
        ]
        for b in self.executive_summary_bullets:
            lines.append(f"  * {b}")

        lines.append("\nKey Evidence-Backed Findings:")
        for kf in self.key_findings:
            lines.append(f"  * {kf}")

        lines.append("\nPlanned Sections:")
        for s in self.sections:
            lines.append(f"  ### {s.heading}")
            lines.append(f"      Objective: {s.objective}")
            if s.key_points:
                lines.append(f"      Key Points: {'; '.join(s.key_points)}")
            if s.counterevidence_points:
                lines.append(f"      Counterevidence: {'; '.join(s.counterevidence_points)}")
            if s.include_table:
                lines.append(f"      [Include Comparison Table: {s.table_description}]")

        if self.unresolved_uncertainties:
            lines.append("\nExplicit Unknowns / Uncertainties to communicate:")
            for u in self.unresolved_uncertainties:
                lines.append(f"  * {u}")

        return "\n".join(lines)

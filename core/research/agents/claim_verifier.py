"""
Vanta Phase 5 — ClaimVerifierAgent.

Verifies major report claims against the evidence graph and atomic claims:
1. Detects unsupported conclusions that lack grounding in extracted claims.
2. Identifies fact/announcement conflation (e.g. stating a planned milestone as an accomplished fact).
3. Verifies numerical figures match the extracted quantitative facts.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.agents.synthesizer import ReportOutput
from core.research.optimizer import strip_thinking
from core.research.state import ResearchState
from core.research.verification.models import ClaimCheck, EntailmentStatus

logger = logging.getLogger(__name__)

CLAIM_VERIFICATION_PROMPT = """You are the Senior Evidence Auditor at Vanta.
Your job is to audit statements in a draft research report against the gathered evidence base.

Research Question:
{question}

Gathered Evidence Summary:
{evidence_summary}

Draft Report Sample to Audit:
{sample_text}

Audit the claims in the sample text.
For any statement that:
1. Makes an unsupported assertion not found in the evidence.
2. Confuses an ANNOUNCEMENT/TARGET with an established FACT (e.g. "will produce in 2027" instead of "targets 2027").
3. Distorts numbers or quantitative findings.

Respond strictly in JSON format:
{{
    "checks": [
        {{
            "report_statement": "exact or summarized sentence from report",
            "status": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "NOT_SUPPORTED",
            "discrepancy_explanation": "reason if not fully supported"
        }}
    ],
    "unsupported_count": 0,
    "has_critical_discrepancy": false
}}"""


class ClaimVerifierAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ClaimVerifierAgent", llm=llm)

    async def run(self, state: ResearchState, report: ReportOutput) -> list[ClaimCheck]:
        """Audit sample statements from report against extracted claims and findings."""
        if not report or not report.body_md or not state.findings:
            return []

        # Build evidence summary from atomic claims or findings
        evidence_lines = []
        if state.claims:
            for c in state.claims[:20]:
                type_tag = f"[{getattr(c, 'claim_type', 'FACT')}]"
                evidence_lines.append(f"- {type_tag} {c.claim_text}")
        else:
            for f in state.findings[:15]:
                txt = f.summary or f.facts[:200]
                evidence_lines.append(f"- [{f.title}] {txt}")

        evidence_summary = "\n".join(evidence_lines)

        # Extract top paragraphs / executive summary from report to audit
        sample_text = report.body_md[:3000]

        prompt = CLAIM_VERIFICATION_PROMPT.format(
            question=state.question,
            evidence_summary=evidence_summary,
            sample_text=sample_text,
        )

        try:
            response = await self._complete(
                [LLMMessage(role="user", content=prompt)],
                complexity="low",
                timeout=60,
            )
            content = strip_thinking(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())

            results: list[ClaimCheck] = []
            for item in data.get("checks", []):
                status_str = item.get("status", "SUPPORTED")
                status = (
                    EntailmentStatus.NOT_SUPPORTED
                    if status_str == "NOT_SUPPORTED"
                    else (
                        EntailmentStatus.PARTIALLY_SUPPORTED
                        if status_str == "PARTIALLY_SUPPORTED"
                        else EntailmentStatus.SUPPORTED
                    )
                )
                results.append(
                    ClaimCheck(
                        report_statement=item.get("report_statement", ""),
                        status=status,
                        discrepancy_explanation=item.get("discrepancy_explanation", ""),
                    )
                )

            unsupported = [c for c in results if c.status == EntailmentStatus.NOT_SUPPORTED]
            if unsupported:
                logger.warning(f"ClaimVerifier identified {len(unsupported)} unsupported assertions.")
                state.warnings.append(
                    f"Evidence Audit: {len(unsupported)} claim(s) lacked full ground-truth backing."
                )

            await self.publish("claim_verifier.completed", {
                "audited_count": len(results),
                "unsupported_count": len(unsupported),
            })
            return results

        except Exception as exc:
            logger.warning(f"Claim verification encountered non-fatal error: {exc}")
            return []

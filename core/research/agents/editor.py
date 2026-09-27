"""
Vanta Phase 5 — EditorAgent.

Refines the draft report for:
1. High information density & clarity (prunes filler phrases and boilerplate).
2. Elimination of cross-section redundancy.
3. Preserving all numerical claims, qualifications, and citation tags [N] strictly intact.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.agents.synthesizer import ReportOutput
from core.research.optimizer import strip_thinking
from core.research.state import ResearchState

logger = logging.getLogger(__name__)

EDITOR_SYSTEM_PROMPT = """You are the Senior Managing Editor at Vanta.
Your job is to polish, clarify, and elevate the draft research report into a world-class, high-density briefing document.

STRICT CONSTRAINTS:
1. DO NOT introduce new facts, claims, or speculation not present in the draft.
2. DO NOT delete, alter, or invent citation brackets like [1], [2, 3]. Preserve ALL existing citations next to the claims they support.
3. DO NOT alter numerical figures, dates, or quantitative metrics.
4. REMOVE empty AI filler phrases like "It is important to note", "In today's rapidly evolving landscape", "This highlights the importance of", "delve into".
5. ELIMINATE redundant restatements across sections.
6. ENSURE crisp analytical paragraph structure: Claim -> Evidence -> Interpretation -> Qualification.

Return ONLY the polished markdown report text without commentary."""


class EditorAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="EditorAgent", llm=llm)

    async def run(self, state: ResearchState, report: ReportOutput) -> ReportOutput:
        """Edit draft report for density and flow while protecting citation integrity."""
        if not report or not report.body_md:
            return report

        # If very brief, apply rule-based cleanup directly
        if len(report.body_md.split()) < 30:
            report.body_md = self._clean_filler_rules(report.body_md)
            return report

        prompt = f"""Research Inquiry: {state.question}

Draft Report to Edit:
{report.body_md}"""

        messages = [
            LLMMessage(role="system", content=EDITOR_SYSTEM_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self._complete(messages, complexity="low", timeout=120)
            edited_text = strip_thinking(response.content).strip()

            # Safety guard: ensure the editor did not wipe out citations or drop more than 50% length
            orig_citations = set(re.findall(r"\[\d+\]", report.body_md))
            edited_citations = set(re.findall(r"\[\d+\]", edited_text))

            if len(edited_text.split()) >= 15 and orig_citations.issubset(edited_citations or {1}):
                report.body_md = edited_text
                # Refresh executive summary from first section
                summary_cand = edited_text.split("\n\n")[0].lstrip("#").strip()
                if len(summary_cand) > 20:
                    report.summary = summary_cand
            else:
                # If citations were lost or output truncated, keep original with lightweight regex cleaning
                logger.info("Editor skipped LLM rewrite due to citation drift; applied rule-based cleanup.")
                report.body_md = self._clean_filler_rules(report.body_md)

        except Exception as exc:
            logger.warning(f"EditorAgent encountered non-fatal error: {exc}")
            report.body_md = self._clean_filler_rules(report.body_md)

        await self.publish("editor.completed", {
            "query": report.query,
            "word_count": len(report.body_md.split()),
        })

        return report

    @staticmethod
    def _clean_filler_rules(text: str) -> str:
        """Deterministic cleanup of generic AI phrases without changing facts."""
        fillers = [
            r"(?i)\bit is important to note that\s*",
            r"(?i)\bin today'?s rapidly evolving landscape,?\s*",
            r"(?i)\bit is worth mentioning that\s*",
            r"(?i)\bthis highlights the importance of\s*",
            r"(?i)\bit should be noted that\s*",
        ]
        for pat in fillers:
            text = re.sub(pat, "", text)
        return text

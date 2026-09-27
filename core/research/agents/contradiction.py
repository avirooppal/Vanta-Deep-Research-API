"""
Vanta Phase 3 — Upgraded ContradictionAgent with Root Cause Classification.

Identifies conflicting evidence and analyzes whether contradictions stem from:
- Direct factual incompatibility
- Numerical disagreements
- Temporal differences (comparing different time periods)
- Definitional or scope boundaries
- Methodological variations
- Corporate announcement vs independent analyst forecasts
"""
from __future__ import annotations

import json
import logging
from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.optimizer import strip_thinking
from core.research.reasoning.models import ContradictionType
from core.research.state import Contradiction, ResearchState

logger = logging.getLogger(__name__)

CONTRADICTION_PROMPT = """You are an Expert Contradiction Detection Agent at Vanta.
Review the provided findings and identify any conflicting evidence or claims.
Determine the root cause of the disagreement:
- "DIRECT_CONTRADICTION": Factually incompatible claims about identical events.
- "NUMERICAL_DISAGREEMENT": Variance in numbers, dollars, or percentages.
- "TEMPORAL_DISAGREEMENT": Differences attributable to comparing different years or historical vs current periods.
- "DEFINITION_DIFFERENCE": Apparent conflict caused by differing scope, geography, or industry definitions.
- "METHODOLOGICAL_DIFFERENCE": Incompatible measurement techniques or sample populations.
- "FORECAST_DIFFERENCE": Corporate target / PR statement vs independent analyst forecast.

Return a JSON array of objects with:
- "description": str (concise description of conflict)
- "source_urls": list of str (URLs that conflict)
- "severity": str ("high" or "low")
- "contradiction_type": str (one of the 6 types above)
- "resolution_suggestion": str (how to reconcile or clearly report the disagreement)
If no contradictions, return []."""


class ContradictionAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ContradictionAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[Contradiction]:
        if len(state.findings) < 2:
            return []

        # Inspect recent findings (with claim types)
        recent = state.findings[-10:]
        findings_text = "\n".join(
            f"URL: {f.url} | Type: {getattr(f, 'claim_type', 'FACT')} | Claim: {(f.summary or f.facts or '')[:140]}"
            for f in recent
        )
        prompt = f"Findings to analyze for conflicting claims:\n{findings_text}"

        messages = [
            LLMMessage(role="system", content=CONTRADICTION_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self._complete(messages, complexity="low")
            content = strip_thinking(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())

            contradictions = []
            if isinstance(data, list):
                for c in data:
                    if isinstance(c, dict):
                        ctype_str = c.get("contradiction_type", "DIRECT_CONTRADICTION").upper()
                        try:
                            ctype = ContradictionType(ctype_str).value
                        except ValueError:
                            ctype = ContradictionType.DIRECT_CONTRADICTION.value

                        contradictions.append(Contradiction(
                            description=c.get("description", ""),
                            source_urls=c.get("source_urls", []),
                            severity=c.get("severity", "low"),
                            resolution_suggestion=c.get("resolution_suggestion", ""),
                            contradiction_type=ctype,
                        ))

            if contradictions:
                await self.publish("contradiction.detected", {
                    "count": len(contradictions),
                })

            return contradictions
        except Exception as exc:
            logger.warning(f"Contradiction detection failed: {exc}")
            return []

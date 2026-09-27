"""
Vanta Phase 3 — ChallengeAgent (Devil's Advocate & Falsification).

Attacks the emerging research conclusions:
- Identifies claims dependent on single sources or self-serving corporate statements
- Tests whether correlation is being conflated with causation
- Formulates skeptical competing explanations and suggests targeted counter-queries
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.optimizer import strip_thinking
from core.research.reasoning.models import ResearchChallenge
from core.research.state import ResearchState

logger = logging.getLogger(__name__)

CHALLENGE_AGENT_SYSTEM = """You are the Lead Devil's Advocate & Adversarial Research Reviewer at Vanta.
Your job is NOT to find random new facts. Your job is to rigorously CHALLENGE and stress-test the emerging conclusions.

Review the research question, the current findings, and the emerging report. Ask:
1. What could make the emerging conclusion completely wrong?
2. Which critical claims rely on a single source or self-interested corporate announcements?
3. Are announced production/delivery targets being confused with real, verified outcomes?
4. What plausible competing explanations have been ignored?
5. What counterevidence or critical test is missing?

Respond strictly in JSON with an array of challenges:
[
  {
    "target_conclusion": "Emerging conclusion being questioned",
    "vulnerability_explanation": "Why this conclusion is vulnerable or unproven",
    "single_source_dependencies": ["Claim X from Source Y"],
    "competing_explanation": "Skeptical or alternative interpretation",
    "missing_falsifying_evidence": ["Evidence needed to refute or verify"],
    "suggested_investigation_query": "Targeted search query to investigate this vulnerability"
  }
]
If the evidence is already balanced or no major vulnerabilities exist, return []."""


class ChallengeAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ChallengeAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[ResearchChallenge]:
        """Analyze state findings and emerging conclusions for vulnerabilities and bias."""
        if len(state.findings) < 2:
            return []

        # Summarize current findings and emerging draft
        findings_summary = "\n".join(
            f"- [{f.title}] ({getattr(f, 'claim_type', 'FACT')}) {f.summary or f.facts[:160]}"
            for f in state.findings[-8:]
        )
        report_preview = (state.evolving_report or "No evolving draft yet.")[:1200]

        prompt = f"""Research Question: {state.question}
Current Draft / Conclusions:
{report_preview}

Recent Findings:
{findings_summary}

Perform adversarial review and return JSON list of challenges."""

        messages = [
            LLMMessage(role="system", content=CHALLENGE_AGENT_SYSTEM),
            LLMMessage(role="user", content=prompt),
        ]

        challenges: list[ResearchChallenge] = []
        try:
            response = await self._complete(messages, complexity="low")
            content = strip_thinking(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            parsed = json.loads(content.strip())

            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        challenges.append(ResearchChallenge(
                            challenge_id=f"ch_{uuid.uuid4().hex[:8]}",
                            target_conclusion=item.get("target_conclusion", ""),
                            vulnerability_explanation=item.get("vulnerability_explanation", ""),
                            single_source_dependencies=item.get("single_source_dependencies", []),
                            competing_explanation=item.get("competing_explanation", ""),
                            missing_falsifying_evidence=item.get("missing_falsifying_evidence", []),
                            suggested_investigation_query=item.get("suggested_investigation_query", ""),
                        ))

            if challenges:
                await self.publish("challenge.generated", {
                    "count": len(challenges),
                    "round": state.current_round,
                })

            return challenges

        except Exception as exc:
            logger.warning(f"ChallengeAgent execution failed: {exc}")
            return []

"""
Vanta Phase 1 — Upgraded CoordinatorAgent.

Manages research loop orchestration with explicit awareness of:
- ResearchBrief and research goals
- ResearchPlan search tracks and critical sub-questions
- Evidence depth and whether critical tracks remain unexplored
"""
from __future__ import annotations

import logging
from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.optimizer import strip_thinking
from core.research.state import ResearchState

logger = logging.getLogger(__name__)

COORDINATOR_SYSTEM = """You are the Lead Research Coordinator Agent at Vanta.
Your job is to manage the research loop and decide whether to CONTINUE exploring or proceed to SYNTHESIZE.

Guidelines:
- If critical sub-questions or search tracks remain unexplored and rounds remain, decide CONTINUE.
- If we have gathered robust, diverse evidence addressing the core sub-questions or reached max rounds, decide SYNTHESIZE.
- Do NOT decide SYNTHESIZE after only 1 round unless maximum rounds is 1.

Respond with ONLY the word CONTINUE or SYNTHESIZE."""


class CoordinatorAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="CoordinatorAgent", llm=llm)

    async def run(self, state: ResearchState) -> str:
        """Decide whether to continue or synthesize based on evidence and plan coverage."""
        if state.current_round >= state.max_rounds:
            return "SYNTHESIZE"

        if not state.findings:
            return "CONTINUE"

        # Plan context
        plan_summary = ""
        if hasattr(state, "plan") and state.plan:
            plan_summary = f"\nResearch Plan & Tracks:\n{state.plan.to_text_summary()[:800]}\n"
        elif getattr(state, "research_plan", ""):
            plan_summary = f"\nResearch Plan:\n{state.research_plan[:600]}\n"

        findings_summary = "\n".join(
            f"- [{f.title}] {f.summary or f.facts[:180]}" for f in state.findings[:10]
        )

        mode_name = state.mode or "research"
        mode_desc = ""
        if hasattr(state, "mode_config") and state.mode_config:
            mode_desc = f"\nMode: {state.mode_config.display_name} ({state.mode_config.name}) - {state.mode_config.description}"
        else:
            mode_desc = f"\nMode: {mode_name}"

        prompt = f"""Question: {state.question}{mode_desc}
Round: {state.current_round} of {state.max_rounds}
Total Validated Sources: {len(state.sources)}
Total Findings Gathered: {len(state.findings)}
{plan_summary}
Sample Evidence Gathered:
{findings_summary}

Decide: CONTINUE (gather more evidence on missing tracks) or SYNTHESIZE (evidence is comprehensive)."""

        messages = [
            LLMMessage(role="system", content=COORDINATOR_SYSTEM),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self._complete(messages, complexity="low")
        decision = strip_thinking(response.content).strip().upper()

        await self.publish("coordinator.decision", {
            "decision": decision,
            "round": state.current_round,
        })

        if "SYNTHESIZE" in decision:
            return "SYNTHESIZE"
        return "CONTINUE"


# Backward compat
async def coordinate(state: ResearchState, llm: LLMClient) -> str:
    agent = CoordinatorAgent(llm)
    return await agent.run(state)

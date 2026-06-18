from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState
from core.research.agents.base import BaseAgent

COORDINATOR_PROMPT = """You are the Research Coordinator Agent.
Your job is to manage the state of an ongoing research process.
You will be provided with the user's original query, the current round number, the maximum rounds, and a summary of findings so far.

You must decide the next step. Your choices are:
- "CONTINUE": We need more information. Loop back to Search -> Extract.
- "SYNTHESIZE": We have enough information, or we have hit the maximum rounds. Proceed to Synthesizer.

Respond with ONLY the word CONTINUE or SYNTHESIZE."""

class CoordinatorAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="Coordinator", llm=llm)
        
    async def run(self, state: ResearchState) -> str:
        """Decide whether to continue or synthesize."""
        if state.current_round >= state.max_rounds:
            return "SYNTHESIZE"

        if not state.findings:
            return "CONTINUE"

        findings_summary = "\n".join(f"- {f.facts[:200]}..." for f in state.findings[:10])
        
        prompt = f"""
Query: {state.question}
Round: {state.current_round} / {state.max_rounds}
Total Findings: {len(state.findings)}
Sample Findings:
{findings_summary}
"""
        messages = [
            LLMMessage(role="system", content=COORDINATOR_PROMPT),
            LLMMessage(role="user", content=prompt)
        ]

        response = await self.llm.complete(messages, complexity="low")
        decision = response.content.strip().upper()
        
        await self.publish("coordinator.decision", {
            "decision": decision, 
            "round": state.current_round
        })
        
        if "SYNTHESIZE" in decision:
            return "SYNTHESIZE"
        return "CONTINUE"

# For backwards compatibility with engine.py
async def coordinate(state: ResearchState, llm: LLMClient) -> str:
    agent = CoordinatorAgent(llm)
    return await agent.run(state)

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState, Contradiction
from core.research.agents.base import BaseAgent
import json

CONTRADICTION_PROMPT = """You are a Contradiction Detection Agent.
Review the provided findings and identify any conflicting claims.
Return a JSON array of objects with:
- "description": str (description of conflict)
- "source_urls": list of str (URLs that conflict)
- "severity": str ("high" or "low")
- "resolution_suggestion": str
If no contradictions, return [].
Do not use markdown blocks."""

class ContradictionAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ContradictionAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[Contradiction]:
        if len(state.findings) < 2:
            return []
            
        findings_text = "\n".join(f"URL: {f.url} | Claim: {f.facts}" for f in state.findings)
        prompt = f"Findings:\n{findings_text}"
        
        messages = [
            LLMMessage(role="system", content=CONTRADICTION_PROMPT),
            LLMMessage(role="user", content=prompt)
        ]
        
        try:
            response = await self.llm.complete(messages)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            data = json.loads(content)
            
            contradictions = []
            for c in data:
                contradictions.append(Contradiction(
                    description=c.get("description", ""),
                    source_urls=c.get("source_urls", []),
                    severity=c.get("severity", "low"),
                    resolution_suggestion=c.get("resolution_suggestion", "")
                ))
            
            if contradictions:
                await self.publish("contradiction.detected", {
                    "count": len(contradictions)
                })
                
            return contradictions
        except Exception:
            return []

# For backwards compatibility with engine.py temporarily
async def detect_contradictions(state: ResearchState, llm: LLMClient) -> list[Contradiction]:
    agent = ContradictionAgent(llm)
    return await agent.run(state)

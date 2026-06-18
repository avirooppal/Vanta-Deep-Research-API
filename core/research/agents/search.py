import json
from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState
from core.research.agents.base import BaseAgent

SEARCH_AGENT_PROMPT = """You are a Search Agent. 
Your goal is to generate 3 to 6 targeted search queries based on the user's research question and what we have found so far.
Return a JSON array of strings containing the queries.
Do not include markdown blocks or any other text."""

class SearchAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="SearchAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[str]:
        findings_summary = "\n".join(f"- {f.facts[:200]}..." for f in state.findings[-5:]) if state.findings else "No findings yet."
        
        prompt = f"""
Original Question: {state.question}
Recent Findings:
{findings_summary}

Please generate search queries to find the missing information or explore deeper.
"""
        
        messages = [
            LLMMessage(role="system", content=SEARCH_AGENT_PROMPT),
            LLMMessage(role="user", content=prompt)
        ]
        
        response = await self.llm.complete(messages, complexity="low")
        
        queries = [state.question]
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            parsed_queries = json.loads(content)
            if isinstance(parsed_queries, list) and len(parsed_queries) > 0:
                queries = [str(q) for q in parsed_queries]
        except json.JSONDecodeError:
            pass

        await self.publish("search.queries_generated", {
            "queries": queries,
            "round": state.current_round
        })
            
        return queries

# For backwards compatibility with engine.py temporarily
async def generate_queries(state: ResearchState, llm: LLMClient) -> list[str]:
    agent = SearchAgent(llm)
    return await agent.run(state)

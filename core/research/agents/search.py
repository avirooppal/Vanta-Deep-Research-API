import json
from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState
from core.research.agents.base import BaseAgent
from core.research.optimizer import current_date_context

SEARCH_AGENT_PROMPT = """You are a Search Agent.
Your goal is to generate focused web search queries based on the user's research question, the current research plan, and what we have found so far.
Return ONLY a JSON array of query strings, nothing else.
Example: ["query one", "query two", "query three"]"""


class SearchAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="SearchAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[str]:
        is_first_round = state.current_round == 1
        num_queries = 4 if is_first_round else 3
        round_instruction = (
            "This is the first round — generate broad, diverse queries that explore the key facets of the question."
            if is_first_round else
            "We already have partial findings. Generate targeted follow-up queries to fill gaps, "
            "verify claims, or explore specific aspects that the report doesn't yet cover well."
        )

        strategy_guidance = ""
        if hasattr(state, "mode_config") and state.mode_config:
            strategy_guidance = f"\nMode: {state.mode_config.display_name}\nMode Strategy: {state.mode_config.search_strategy}\n"

        recent_findings = "\n".join(
            f"- {f.summary or f.facts[:200]}..." for f in state.findings[-5:]
        ) if state.findings else "No findings yet."

        research_plan = getattr(state, "research_plan", "") or "(No plan — search broadly.)"
        evolving_report = getattr(state, "evolving_report", "") or "(No report yet.)"

        prompt = (
            current_date_context()
            + f"Original Question: {state.question}{strategy_guidance}\n"
            f"Research Plan:\n{research_plan}\n\n"
            f"Current Report Summary (first 1000 chars):\n{evolving_report[:1000]}\n\n"
            f"Recent Findings:\n{recent_findings}\n\n"
            f"Round: {state.current_round}\n"
            f"{round_instruction}\n\n"
            f"Generate {num_queries} search queries."
        )

        messages = [
            LLMMessage(role="system", content=SEARCH_AGENT_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self.llm.complete(messages, complexity="low")

        queries = [state.question]
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            parsed_queries = json.loads(content.strip())
            if isinstance(parsed_queries, list) and len(parsed_queries) > 0:
                queries = [str(q) for q in parsed_queries]
        except json.JSONDecodeError:
            pass

        # Dedup against already-used queries
        queries_used: set = getattr(state, "queries_used", set())
        new_queries = [q for q in queries if q not in queries_used]
        if not new_queries:
            new_queries = queries  # fallback: allow repeats if all were seen
        queries_used.update(new_queries)

        await self.publish("search.queries_generated", {
            "queries": new_queries,
            "round": state.current_round,
        })

        return new_queries


# Backward compat
async def generate_queries(state: ResearchState, llm: LLMClient) -> list[str]:
    agent = SearchAgent(llm)
    return await agent.run(state)

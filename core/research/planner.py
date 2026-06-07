import json
from core.llm.client import LLMClient
from core.llm.types import Message

PLAN_PROMPT = """You are a research planning assistant.
Given a research question, generate a list of specific search queries that together would comprehensively answer it.
Return ONLY a JSON array of strings, no explanation, no markdown fences.
Example output: ["query one", "query two", "query three"]
Generate between 3 and 6 queries."""


async def plan_queries(question: str, llm: LLMClient) -> list[str]:
    messages = [
        Message(role="system", content=PLAN_PROMPT),
        Message(role="user", content=f"Research question: {question}"),
    ]
    response = await llm.complete(messages)
    try:
        queries = json.loads(response.content)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries[:6]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: treat the whole question as one query
    return [question]

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from integrations.fetcher import FetchedPage
from core.research.state import ValidatedSource
from core.research.agents.base import BaseAgent
import json

VALIDATOR_PROMPT = """You are a Source Validation Agent.
Given a URL and its title/content snippet, you must evaluate its trustworthiness.
Return a JSON object with:
- "trust_score": Integer from 0 to 100 (100 is highly trustworthy, e.g. academic, 0 is spam/malicious).
- "flags": String describing any biases, paywalls, or low-quality indicators (or "None").

Only return the JSON object, no markdown blocks."""

class ValidatorAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ValidatorAgent", llm=llm)

    async def run(self, page: FetchedPage) -> ValidatedSource:
        prompt = f"URL: {page.url}\nTitle: {page.title}\nSnippet: {page.text[:1000]}"
        messages = [
            LLMMessage(role="system", content=VALIDATOR_PROMPT),
            LLMMessage(role="user", content=prompt)
        ]
        
        trust_score = getattr(page, 'trust_score', 50)
        flags = "None"
        
        try:
            response = await self.llm.complete(messages)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            data = json.loads(content)
            llm_score = int(data.get("trust_score", trust_score))
            trust_score = (trust_score + llm_score) // 2
            flags = str(data.get("flags", "None"))
        except Exception:
            pass
            
        source = ValidatedSource(
            url=page.url,
            title=page.title,
            text=page.text,
            trust_score=trust_score,
            flags=flags
        )

        await self.publish("validator.source_validated", {
            "url": source.url,
            "trust_score": source.trust_score,
            "flags": source.flags
        })

        return source

# For backwards compatibility with engine.py temporarily
async def validate_source(page: FetchedPage, llm: LLMClient) -> ValidatedSource:
    agent = ValidatorAgent(llm)
    return await agent.run(page)

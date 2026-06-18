from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ValidatedSource, Finding
from core.research.agents.base import BaseAgent
import json

EXTRACTOR_PROMPT = """You are a Fact Extraction Agent.
Extract relevant claims from the provided text based on the research question.
Return a JSON array of objects, where each object has:
- "facts": a string of the claim
- "trust_score": an integer from 0-100 indicating confidence based on language used in the source
- "contradicts_claim_id": if this claim directly contradicts one of the provided "Previously extracted related claims", include its ID here. Otherwise null.
If no relevant claims, return an empty array [].
Do not include markdown blocks."""

class ExtractorAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="ExtractorAgent", llm=llm)

    async def run(self, source: ValidatedSource, question: str, round_n: int, memory=None) -> list[Finding]:
        memory_context = ""
        if memory:
            prev_claims = await memory.search_memory(question, limit=5)
            if prev_claims:
                memory_context = "Previously extracted related claims:\n" + "\n".join(f"- [ID: {c['id']}] {c['fact']}" for c in prev_claims) + "\n\n"
                
        prompt = f"Question: {question}\n\n{memory_context}Text: {source.text[:8000]}"
        messages = [
            LLMMessage(role="system", content=EXTRACTOR_PROMPT),
            LLMMessage(role="user", content=prompt)
        ]
        
        try:
            response = await self.llm.complete(messages)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            claims = json.loads(content)
            
            findings = []
            for claim in claims:
                if isinstance(claim, dict) and "facts" in claim:
                    finding = Finding(
                        url=source.url,
                        title=source.title,
                        facts=claim["facts"],
                        round_number=round_n,
                        trust_score=claim.get("trust_score", 50),
                        contradicts_claim_id=claim.get("contradicts_claim_id")
                    )
                    findings.append(finding)
            
            await self.publish("extractor.claims_extracted", {
                "source_url": source.url,
                "claims_count": len(findings)
            })
            
            return findings
        except Exception:
            return []

# For backwards compatibility with engine.py temporarily
async def extract_claims(source: ValidatedSource, question: str, llm: LLMClient, round_n: int, memory=None) -> list[Finding]:
    agent = ExtractorAgent(llm)
    return await agent.run(source, question, round_n, memory)

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ValidatedSource, Finding
from core.research.agents.base import BaseAgent
from core.research.optimizer import compress_source_text, is_low_quality
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Goal-based extraction prompt (Alibaba IterResearch / Odysseus-inspired)
# ---------------------------------------------------------------------------
EXTRACTOR_SYSTEM = """Extract relevant information from a webpage for a given research goal.

Goal: {goal}

Task guidelines:
1. Locate the specific sections directly related to the goal within the provided webpage content.
2. Identify and extract the most relevant information; output full original context where possible, up to three or more paragraphs.
3. Organize into a concise paragraph with logical flow, judging each piece of information's contribution to the goal.
4. Assign a trust_score (0-100) based on the language confidence in the source.

Respond in JSON with exactly these fields:
{{
    "rational": "Why this section relates to the research goal",
    "evidence": "Full quotes and context from the page",
    "summary": "Concise answer to the research goal",
    "trust_score": 75
}}

If no relevant content is found, respond with:
{{
    "rational": "No relevant information found",
    "evidence": "",
    "summary": "No relevant information found",
    "trust_score": 0
}}
"""

# Backward-compat prompt for legacy single-field extraction
EXTRACTOR_PROMPT_LEGACY = """You are a Fact Extraction Agent.
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

    async def run(
        self,
        source: ValidatedSource,
        question: str,
        round_n: int,
        memory=None,
        mode_config=None,
    ) -> list[Finding]:
        memory_context = ""
        if memory:
            prev_claims = await memory.search_memory(question, limit=5)
            if prev_claims:
                memory_context = (
                    "Previously extracted related claims:\n"
                    + "\n".join(f"- [ID: {c['id']}] {c['fact']}" for c in prev_claims)
                    + "\n\n"
                )

        focus_guidance = ""
        if mode_config and hasattr(mode_config, "extraction_focus") and mode_config.extraction_focus:
            focus_guidance = f"\nMode Extraction Focus: {mode_config.extraction_focus}\n"

        content = source.text or ""
        max_source_chars = 6000  # was 12000 — halved to cut token use
        if len(content) > max_source_chars:
            truncated = content[:max_source_chars]
            last_para = truncated.rfind("\n\n")
            if last_para > max_source_chars * 0.8:
                content = truncated[:last_para]
            else:
                content = truncated

        compressed_text = compress_source_text(content, query=question, max_chars=1800)  # was 3500

        # --- Goal-based structured extraction ---
        system_prompt = EXTRACTOR_SYSTEM.format(goal=question)
        prompt = f"{focus_guidance}{memory_context}Text:\n{compressed_text}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.complete(messages)
            content_str = response.content.strip()
            if content_str.startswith("```json"):
                content_str = content_str[7:]
            if content_str.endswith("```"):
                content_str = content_str[:-3]
            content_str = content_str.strip()

            parsed = json.loads(content_str)

            # Handle both new structured format and legacy array format
            if isinstance(parsed, dict):
                findings = [self._dict_to_finding(parsed, source, round_n, memory_context)]
            elif isinstance(parsed, list):
                findings = [
                    self._legacy_claim_to_finding(c, source, round_n)
                    for c in parsed
                    if isinstance(c, dict) and ("facts" in c or "summary" in c)
                ]
            else:
                findings = []

            # Filter low-quality extractions
            findings = [
                f for f in findings
                if f is not None and not is_low_quality(f.summary or f.facts)
            ]

            await self.publish("extractor.claims_extracted", {
                "source_url": source.url,
                "claims_count": len(findings),
            })

            return findings

        except Exception as e:
            logger.warning(f"LLM extraction failed for {source.url}: {e}")
            return []

    def _dict_to_finding(self, parsed: dict, source: ValidatedSource, round_n: int, memory_context: str) -> Finding | None:
        summary = parsed.get("summary", "")
        evidence = parsed.get("evidence", "")
        rational = parsed.get("rational", "")
        trust_score = int(parsed.get("trust_score", 50))

        if not summary and not evidence:
            return None

        return Finding(
            url=source.url,
            title=source.title,
            # facts keeps the combined text for backward compat
            facts=summary or evidence,
            round_number=round_n,
            trust_score=min(100, max(0, trust_score)),
            rational=rational,
            evidence=evidence,
            summary=summary,
        )

    def _legacy_claim_to_finding(self, claim: dict, source: ValidatedSource, round_n: int) -> Finding:
        return Finding(
            url=source.url,
            title=source.title,
            facts=claim.get("facts", ""),
            round_number=round_n,
            trust_score=claim.get("trust_score", 50),
            contradicts_claim_id=claim.get("contradicts_claim_id"),
        )


# Backward compat
async def extract_claims(source: ValidatedSource, question: str, llm: LLMClient, round_n: int, memory=None) -> list[Finding]:
    agent = ExtractorAgent(llm)
    return await agent.run(source, question, round_n, memory)

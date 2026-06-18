from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState
from core.research.agents.base import BaseAgent
from dataclasses import dataclass

@dataclass
class ReportOutput:
    query: str
    summary: str
    body_md: str
    citations: list[dict]

SYNTHESIS_PROMPT = """You are a Synthesis Agent. 
Write a comprehensive markdown report answering the user's question using the provided findings.
Make sure to include an Executive Summary.
Cite your sources inline using [1], [2] format corresponding to the finding numbers."""

MAX_SYNTHESIS_CHARS = 80000

class SynthesizerAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="SynthesizerAgent", llm=llm)

    async def run(self, state: ResearchState) -> ReportOutput:
        findings_blocks = []
        total_chars = 0
        truncated = False
        
        sorted_findings = sorted(enumerate(state.findings), key=lambda x: x[1].round_number, reverse=True)
        
        for i, f in sorted_findings:
            block = f"[{i+1}] {f.url}\n{f.facts}"
            if total_chars + len(block) > MAX_SYNTHESIS_CHARS:
                truncated = True
                break
            findings_blocks.append((i, block))
            total_chars += len(block)
            
        findings_blocks.sort(key=lambda x: x[0])
        findings_text = "\n\n".join(b[1] for b in findings_blocks)
        
        if truncated:
            findings_text = "[Earlier findings truncated for context limit. Full sources in job record.]\n\n" + findings_text

        if state.contradictions:
            findings_text += "\n\n=== CONTRADICTIONS DETECTED ===\n"
            for c in state.contradictions:
                findings_text += f"Conflict: {c.description} (Severity: {c.severity})\nResolution: {c.resolution_suggestion}\n\n"

        messages = [
            LLMMessage(role="system", content=SYNTHESIS_PROMPT),
            LLMMessage(role="user", content=f"Research question: {state.question}\n\nFindings:\n{findings_text}")
        ]
        
        response = await self.llm.complete(messages)
        body_md = response.content.strip()
        summary = body_md.split("\n\n")[0].lstrip("#").strip()

        citations = [
            {"id": f"src_{i+1}", "url": f.url, "title": f.title}
            for i, f in enumerate(state.findings)
        ]

        report = ReportOutput(
            query=state.question,
            summary=summary,
            body_md=body_md,
            citations=citations,
        )

        await self.publish("synthesizer.report_generated", {
            "query": report.query,
            "citations_count": len(report.citations)
        })

        return report

# For backwards compatibility with engine.py temporarily
async def synthesize(state: ResearchState, llm: LLMClient) -> ReportOutput:
    agent = SynthesizerAgent(llm)
    return await agent.run(state)

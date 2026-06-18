from core.llm.client import LLMClient
from core.llm.types import Message
from core.research.state import ResearchState
from core.research.agents.synthesizer import ReportOutput
from core.research.agents.base import BaseAgent
import re

class CitationVerifierAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="CitationVerifierAgent", llm=llm)

    async def run(self, state: ResearchState, report: ReportOutput) -> ReportOutput:
        # A simple native Python citation verifier that removes references to [N] if N is out of bounds
        valid_indices = {str(i+1) for i in range(len(state.findings))}
        
        def remove_invalid_citations(match):
            citation = match.group(0)
            nums = re.findall(r'\d+', citation)
            valid_nums = [n for n in nums if n in valid_indices]
            if not valid_nums:
                return ""
            return "[" + ", ".join(valid_nums) + "]"
            
        verified_body = re.sub(r'\[[\d,\s]+\]', remove_invalid_citations, report.body_md)
        report.body_md = verified_body

        await self.publish("citation_verifier.citations_verified", {
            "query": report.query
        })
        
        return report

# For backwards compatibility with engine.py temporarily
async def verify_citations(state: ResearchState, report: ReportOutput, llm: LLMClient) -> ReportOutput:
    agent = CitationVerifierAgent(llm)
    return await agent.run(state, report)

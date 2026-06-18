import asyncio
from typing import Callable, Awaitable
from core.llm.client import LLMClient
from core.research.state import ResearchState, ValidatedSource, Finding
from core.research.agents.coordinator import CoordinatorAgent
from core.research.agents.search import SearchAgent
from core.research.agents.validator import ValidatorAgent
from core.research.agents.extractor import ExtractorAgent
from core.research.agents.contradiction import ContradictionAgent
from core.research.agents.synthesizer import SynthesizerAgent
from core.research.agents.citation_verifier import CitationVerifierAgent
from integrations.searxng import search_searxng
from integrations.fetcher import fetch_url
from core.config import settings

class RoundResult:
    def __init__(self, round_number: int, new_findings: list[Finding], total_findings: int, progress_pct: int, sources: list[ValidatedSource]):
        self.round_number = round_number
        self.new_findings = new_findings
        self.total_findings = total_findings
        self.progress_pct = progress_pct
        self.sources = sources

ProgressCallback = Callable[[RoundResult], Awaitable[None]]

async def _noop_progress(result: RoundResult) -> None:
    pass

async def run_research(
    question: str,
    llm: LLMClient,
    searxng_url: str,
    max_rounds: int = 3,
    on_progress: ProgressCallback = _noop_progress,
    cancelled: asyncio.Event | None = None,
    job_id: str | None = None,
):
    state = ResearchState(question=question, max_rounds=max_rounds)
    sem = asyncio.Semaphore(settings.extraction_concurrency)
    
    from core.research.memory import MemoryStore
    memory = MemoryStore(job_id=job_id, llm=llm) if job_id else None

    # Instantiate Agents
    coordinator_agent = CoordinatorAgent(llm)
    search_agent = SearchAgent(llm)
    validator_agent = ValidatorAgent(llm)
    extractor_agent = ExtractorAgent(llm)
    contradiction_agent = ContradictionAgent(llm)
    synthesizer_agent = SynthesizerAgent(llm)
    citation_verifier_agent = CitationVerifierAgent(llm)

    while not state.is_done:
        if cancelled and cancelled.is_set():
            break

        # 1. Coordinator decides next step
        decision = await coordinator_agent.run(state)
        
        if decision == "SYNTHESIZE":
            break

        # 2. Search Agent
        queries = await search_agent.run(state)
        llm.search_queries_issued += len(queries)
        state.queries.extend(queries)
        
        search_tasks = [search_searxng(q, searxng_url, num_results=5) for q in queries]
        search_results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        urls = []
        seen = {f.url for f in state.findings}
        for result_list in search_results_nested:
            if isinstance(result_list, list):
                for r in result_list:
                    if r.url not in seen:
                        urls.append(r.url)
                        seen.add(r.url)

        # 3. Fetch -> Validator -> Extractor pipeline
        async def process_url(url: str):
            async with sem:
                page = await fetch_url(url)
                if not page.success:
                    return None
                llm.sources_fetched += 1
                
                # Validator Agent
                validated_source = await validator_agent.run(page)
                if validated_source.trust_score < 30:
                    return None  # Skip low trust sources
                    
                # Extractor Agent
                findings = await extractor_agent.run(validated_source, question, state.current_round, memory)
                return (validated_source, findings)

        extract_tasks = [process_url(url) for url in urls[:15]]
        results = await asyncio.gather(*extract_tasks, return_exceptions=True)
        
        new_findings = []
        new_sources = []
        for r in results:
            if isinstance(r, tuple):
                source, findings = r
                new_sources.append(source)
                new_findings.extend(findings)
                
        state.sources.extend(new_sources)
        state.findings.extend(new_findings)

        # 4. Contradiction Agent
        state.contradictions = await contradiction_agent.run(state)

        # 5. Progress Report
        await on_progress(RoundResult(
            round_number=state.current_round,
            new_findings=new_findings,
            total_findings=len(state.findings),
            progress_pct=int((state.current_round / max_rounds) * 90),
            sources=new_sources
        ))

        state.current_round += 1

    # 6. Synthesis Agent
    from core.research.agents.synthesizer import ReportOutput
    if not state.findings:
        return ReportOutput(
            query=question,
            summary="No findings could be gathered for this query.",
            body_md="No findings could be gathered.",
            citations=[],
        )

    report = await synthesizer_agent.run(state)
    
    # 7. Citation Verifier Agent
    report = await citation_verifier_agent.run(state, report)
    
    return report

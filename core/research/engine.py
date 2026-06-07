import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable
from core.llm.client import LLMClient
from core.research.planner import plan_queries
from core.research.extractor import extract_findings, Finding
from core.research.synthesizer import should_continue, synthesize_report, ReportOutput
from integrations.searxng import search_searxng
from integrations.fetcher import fetch_url
from core.config import settings


@dataclass
class RoundResult:
    round_number: int
    new_findings: list[Finding]
    total_findings: int


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
) -> ReportOutput:
    all_findings: list[Finding] = []
    sem = asyncio.Semaphore(settings.extraction_concurrency)

    for round_n in range(1, max_rounds + 1):
        if cancelled and cancelled.is_set():
            break

        queries = await plan_queries(question, llm)
        llm.search_queries_issued += len(queries)
        search_tasks = [search_searxng(q, searxng_url, num_results=5) for q in queries]
        search_results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        urls: list[str] = []
        seen: set[str] = {f.url for f in all_findings}
        for result_list in search_results_nested:
            if isinstance(result_list, list):
                for r in result_list:
                    if r.url not in seen:
                        urls.append(r.url)
                        seen.add(r.url)

        async def fetch_and_extract(url: str) -> Finding | None:
            async with sem:
                page = await fetch_url(url)
                if page.success:
                    llm.sources_fetched += 1
                return await extract_findings(page, question, llm, round_n)


        extract_tasks = [fetch_and_extract(url) for url in urls[:15]]
        raw_findings = await asyncio.gather(*extract_tasks, return_exceptions=True)

        new_findings = [f for f in raw_findings if isinstance(f, Finding) and f is not None]
        all_findings.extend(new_findings)

        await on_progress(RoundResult(
            round_number=round_n,
            new_findings=new_findings,
            total_findings=len(all_findings),
        ))

        if all_findings and not await should_continue(question, all_findings, llm):
            break

    if not all_findings:
        return ReportOutput(
            query=question,
            summary="No findings could be gathered for this query.",
            body_md="No findings could be gathered.",
            citations=[],
        )

    return await synthesize_report(question, all_findings, llm)

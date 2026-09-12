import asyncio
import json
import logging
import re
from typing import Callable, Awaitable

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState, ValidatedSource, Finding
from core.research.agents.coordinator import CoordinatorAgent
from core.research.agents.search import SearchAgent
from core.research.agents.validator import ValidatorAgent
from core.research.agents.extractor import ExtractorAgent
from core.research.agents.contradiction import ContradictionAgent
from core.research.agents.synthesizer import SynthesizerAgent, ReportOutput
from core.research.agents.citation_verifier import CitationVerifierAgent
from core.research.modes import (
    get_mode_config, ModeConfig,
    VALID_CATEGORIES, CATEGORY_CLASSIFICATION_PROMPT,
)
from core.research.optimizer import current_date_context, strip_thinking
from integrations.searxng import search_searxng
from integrations.fetcher import fetch_url
from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Planning prompt (Odysseus / IterResearch-inspired)
# ---------------------------------------------------------------------------

# Slim plan prompt — avoids multi-shot examples to save tokens
RESEARCH_PLAN_PROMPT = """\
Analyze this question and return a JSON research plan:
{question}

JSON fields:
- "sub_questions": 2-4 specific sub-questions
- "key_topics": key topics/angles
- "success_criteria": one sentence
"""

STOP_CHECK_PROMPT = """\
Is this research report comprehensive enough to answer: {question}?

Rounds: {round_num}/{max_rounds}
Report summary:
{report}

Reply ONLY "YES" or "NO" + one-sentence reason."""

# ---------------------------------------------------------------------------
# Progress callback types
# ---------------------------------------------------------------------------

class RoundResult:
    def __init__(
        self,
        round_number: int,
        new_findings: list[Finding],
        total_findings: int,
        progress_pct: int,
        sources: list[ValidatedSource],
    ):
        self.round_number = round_number
        self.new_findings = new_findings
        self.total_findings = total_findings
        self.progress_pct = progress_pct
        self.sources = sources


ProgressCallback = Callable[[RoundResult], Awaitable[None]]


async def _noop_progress(result: RoundResult) -> None:
    pass


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------

async def run_research(
    question: str,
    llm: LLMClient,
    searxng_url: str,
    max_rounds: int = 3,
    on_progress: ProgressCallback = _noop_progress,
    cancelled: asyncio.Event | None = None,
    job_id: str | None = None,
    mode: str = "research",
    min_rounds: int = 2,
    max_empty_rounds: int = 2,
    synthesis_window: int = 6,
):
    # Validate self-hosted providers that need an explicit base_url
    _provider = getattr(llm.config, "provider", "")
    _base_url = getattr(llm.config, "base_url", "") or ""
    _NEEDS_CUSTOM_URL = {"ollama_cloud"}
    if _provider in _NEEDS_CUSTOM_URL and "localhost" not in _base_url and "api.ollama.com" not in _base_url:
        if _base_url in ("", "https://api.ollama.com/v1"):
            return ReportOutput(
                query=question,
                summary="Provider requires a custom base URL.",
                body_md=(
                    f"**{_provider}** requires you to specify the remote endpoint URL.\n\n"
                    "In the console → LLM Settings, set **Base URL Override** to your "
                    "Ollama-compatible API endpoint (e.g. `http://your-server:11434/v1`)."
                ),
                citations=[],
            )
    mode_config = get_mode_config(mode)
    effective_rounds = (
        min(max_rounds, mode_config.max_rounds_cap)
        if max_rounds
        else mode_config.default_rounds
    )
    state = ResearchState(
        question=question,
        max_rounds=effective_rounds,
        mode=mode_config.name,
        mode_config=mode_config,
    )
    sem = asyncio.Semaphore(settings.extraction_concurrency)

    from core.research.memory import MemoryStore
    memory = MemoryStore(job_id=job_id, llm=llm) if job_id else None

    # -----------------------------------------------------------------------
    # Instantiate agents
    # -----------------------------------------------------------------------
    coordinator_agent = CoordinatorAgent(llm)
    search_agent = SearchAgent(llm)
    validator_agent = ValidatorAgent(llm)
    extractor_agent = ExtractorAgent(llm)
    contradiction_agent = ContradictionAgent(llm)
    synthesizer_agent = SynthesizerAgent(llm)
    citation_verifier_agent = CitationVerifierAgent(llm)

    # -----------------------------------------------------------------------
    # PLAN: analyze question, create research strategy
    # -----------------------------------------------------------------------
    state.research_plan = await _create_plan(question, llm)
    logger.info(f"Research plan: {state.research_plan[:200]}")

    # Auto-detect category (fast, one-shot, low cost)
    state.category = await _classify_category(question, llm)
    if state.category:
        logger.info(f"Auto-detected category: {state.category}")

    # -----------------------------------------------------------------------
    # Research loop
    # -----------------------------------------------------------------------
    consecutive_empty_rounds = 0
    _last_search_error: str | None = None

    while not state.is_done:
        if cancelled and cancelled.is_set():
            break

        # Hard stop on round count
        if state.current_round > state.max_rounds:
            break

        # 1. Coordinator decides next step (round-count guard + quick sanity check)
        decision = await coordinator_agent.run(state)
        if decision == "SYNTHESIZE":
            break

        # 2. Search Agent — date-grounded, plan-aware, query-deduped
        queries = await search_agent.run(state)
        llm.search_queries_issued += len(queries)
        state.queries.extend(queries)

        search_tasks = [search_searxng(q, searxng_url, num_results=5) for q in queries]
        search_results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        urls = []
        seen = {f.url for f in state.findings}
        for result_list in search_results_nested:
            if isinstance(result_list, Exception):
                _last_search_error = str(result_list)
                logger.warning(f"Search error: {result_list}")
                continue
            if isinstance(result_list, list):
                for r in result_list:
                    if r.url not in seen:
                        urls.append(r.url)
                        seen.add(r.url)

        # 3. Fetch → Validator → Extractor pipeline
        async def process_url(url: str):
            async with sem:
                page = await fetch_url(url)
                if not page.success:
                    return None
                llm.sources_fetched += 1

                validated_source = await validator_agent.run(page)
                if validated_source.trust_score < mode_config.min_trust_score:
                    return None

                findings = await extractor_agent.run(
                    validated_source, question, state.current_round, memory, mode_config=mode_config
                )
                return (validated_source, findings)

        extract_tasks = [process_url(url) for url in urls[:10]]  # cap per-round fetches
        results = await asyncio.gather(*extract_tasks, return_exceptions=True)

        new_findings: list[Finding] = []
        new_sources: list[ValidatedSource] = []
        for r in results:
            if isinstance(r, tuple):
                source, findings = r
                new_sources.append(source)
                new_findings.extend(findings)

        state.sources.extend(new_sources)
        state.findings.extend(new_findings)

        # 4. Empty-round guard
        if not new_findings:
            consecutive_empty_rounds += 1
            err_detail = f" (last error: {_last_search_error})" if _last_search_error else ""
            logger.warning(
                f"Round {state.current_round}: no new findings "
                f"({consecutive_empty_rounds} consecutive empty rounds){err_detail}"
            )
            if consecutive_empty_rounds >= max_empty_rounds:
                logger.warning(
                    f"Search appears dry — stopping early{err_detail}. "
                    "Check SearXNG and ensure search engines are reachable."
                )
                break
        else:
            consecutive_empty_rounds = 0
            _last_search_error = None

        # 5. Incremental synthesis — update evolving report each round (sliding window)
        if new_findings:
            window_findings = new_findings[-synthesis_window:]
            state.evolving_report = await synthesizer_agent.synthesize_round(state, window_findings)

        # 6. Contradiction detection
        state.contradictions = await contradiction_agent.run(state)

        # 7. Progress callback
        await on_progress(RoundResult(
            round_number=state.current_round,
            new_findings=new_findings,
            total_findings=len(state.findings),
            progress_pct=int((state.current_round / effective_rounds) * 90),
            sources=new_sources,
        ))

        state.current_round += 1

        # 8. LLM-driven stop check (after min_rounds)
        if state.current_round > min_rounds and state.evolving_report:
            should_stop = await _should_stop(question, state.evolving_report, state.current_round - 1, effective_rounds, llm)
            if should_stop:
                logger.info(f"LLM decided to stop after round {state.current_round - 1}")
                break

    # -----------------------------------------------------------------------
    # Final report
    # -----------------------------------------------------------------------
    if not state.findings:
        err_detail = f"\n\n**Search error:** {_last_search_error}" if _last_search_error else ""
        return ReportOutput(
            query=question,
            summary="No findings could be gathered for this query.",
            body_md=(
                "No findings could be gathered. The search rounds returned no usable content.\n\n"
                "**Possible causes:**\n"
                "- The model is rate-limited (avoid `openrouter/free`; use a specific model)\n"
                "- Search queries did not match relevant pages\n"
                "- Fetched pages are paywalled or JS-rendered"
                + err_detail
            ),
            citations=[],
        )

    # If synthesis never produced a report (e.g. all synthesis calls timed out),
    # fall back to a compiled findings report rather than losing the gathered data.
    if not state.evolving_report and state.findings:
        logger.warning(
            "Synthesis produced no evolving report; compiling fallback from %d finding(s)",
            len(state.findings),
        )
        fallback_body = _fallback_report(question, state.findings)
        return ReportOutput(
            query=question,
            summary=f"Research completed with {len(state.findings)} findings (synthesis timed out).",
            body_md=fallback_body,
            citations=[
                {"id": f"src_{i+1}", "url": f.url, "title": f.title}
                for i, f in enumerate(state.findings)
            ],
        )

    report = await synthesizer_agent.run(state)
    report = await citation_verifier_agent.run(state, report)

    return report


# ---------------------------------------------------------------------------
# Fallback report compiler (Odysseus-inspired)
# ---------------------------------------------------------------------------

def _fallback_report(question: str, findings: list) -> str:
    """Compile gathered findings into a basic markdown report.

    Used when the LLM synthesis step produced no output (e.g. it timed out)
    but the search rounds did collect findings — so the user still gets the
    material that was gathered instead of a bare 'No findings' message.
    """
    parts = [
        f"# {question}\n",
        f"_Automatic synthesis did not complete. This report lists the "
        f"{len(findings)} finding(s) gathered during research._\n",
    ]
    for i, f in enumerate(findings, 1):
        url = getattr(f, "url", "")
        title = getattr(f, "title", "") or url
        summary = getattr(f, "summary", "") or ""
        evidence = getattr(f, "evidence", "") or ""
        content = summary if summary else (evidence[:2000] if evidence else str(getattr(f, "facts", ""))[:2000])
        parts.append(f"**{i}. [{title}]({url})**\n\n{content}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Planning helper
# ---------------------------------------------------------------------------

async def _create_plan(question: str, llm: LLMClient) -> str:
    """LLM analyzes the question and creates a structured research plan."""
    prompt = current_date_context() + RESEARCH_PLAN_PROMPT.format(question=question)
    try:
        response = await llm.complete(
            [LLMMessage(role="user", content=prompt)],
            complexity="low",
        )
        text = strip_thinking(response.content) or ""
        # Parse JSON plan
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        try:
            parsed = json.loads(text)
            parts = []
            if parsed.get("sub_questions"):
                parts.append("Sub-questions: " + "; ".join(parsed["sub_questions"]))
            if parsed.get("key_topics"):
                parts.append("Key topics: " + ", ".join(parsed["key_topics"]))
            if parsed.get("success_criteria"):
                parts.append("Success: " + parsed["success_criteria"])
            return "\n".join(parts) if parts else text
        except (json.JSONDecodeError, AttributeError):
            return text
    except Exception as e:
        logger.warning(f"Research planning failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Category classifier
# ---------------------------------------------------------------------------

async def _classify_category(question: str, llm: LLMClient) -> str | None:
    """Fast one-shot LLM call to classify the research question."""
    prompt = CATEGORY_CLASSIFICATION_PROMPT.format(question=question)
    try:
        response = await llm.complete(
            [LLMMessage(role="user", content=prompt)],
            complexity="low",
        )
        cat = (strip_thinking(response.content) or "").strip().lower()
        # Clean up and match
        first = cat.split()[0].strip(".,\"'*:") if cat.split() else ""
        if first in VALID_CATEGORIES:
            return first
        for c in VALID_CATEGORIES:
            if c in cat:
                return c
        return None
    except Exception as e:
        logger.warning(f"Category classification failed: {e}")
        return None


# ---------------------------------------------------------------------------
# LLM-driven stop check
# ---------------------------------------------------------------------------

async def _should_stop(
    question: str,
    report: str,
    round_num: int,
    max_rounds: int,
    llm: LLMClient,
) -> bool:
    """Let the LLM decide whether the report is comprehensive enough."""
    prompt = STOP_CHECK_PROMPT.format(
        question=question,
        report=report[:1500],  # tight cap — just enough to judge completeness
        round_num=round_num,
        max_rounds=max_rounds,
    )
    try:
        response = await llm.complete(
            [LLMMessage(role="user", content=prompt)],
            complexity="low",
        )
        clean = strip_thinking(response.content or "").strip()
        # Tolerate "**YES**", "Yes.", etc.
        answer = re.sub(r'^[\s*_`"\'>#\-]+', "", clean).upper()
        logger.info(f"Stop decision (round {round_num}): {clean[:120]}")
        return answer.startswith("YES")
    except Exception as e:
        logger.warning(f"Stop decision failed: {e}")
        return False  # continue on error

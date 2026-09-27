"""
Vanta Phase 1 — Upgraded SearchAgent with Multi-Family Queries and Novelty Tracking.

Generates diverse query families:
- BROAD_DISCOVERY
- PRIMARY_SOURCE (site:gov, official filings, regulatory, institutional)
- TECHNICAL_ACADEMIC (peer-reviewed, arxiv, ieee, nature)
- CRITICAL_SKEPTICAL (delays, challenges, criticisms, failure modes)
- QUANTITATIVE (costs, percentages, metrics, benchmark figures)

Applies token-level novelty filtering to maximize new information gain per search.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.base import BaseAgent
from core.research.optimizer import current_date_context, strip_thinking
from core.research.state import ResearchState

logger = logging.getLogger(__name__)

SEARCH_AGENT_SYSTEM = """You are an Elite Investigative Search Strategist at Vanta.
Your goal is to discover authoritative evidence answering the user's research plan.
You must NOT produce generic, repetitive keyword searches.

Generate a diverse set of search queries spanning distinct QUERY FAMILIES:
1. BROAD DISCOVERY: Overview and core landscape.
2. PRIMARY SOURCE: Official agency filings, government reports (site:gov / official domains), corporate 10-K, technical standards.
3. TECHNICAL / ACADEMIC: Peer-reviewed literature, academic benchmarks, clinical trials, or whitepapers.
4. CRITICAL / SKEPTICAL: Explicitly investigate failure modes, delayed commercialization, skepticism, counterevidence, or cost hurdles.
5. QUANTITATIVE: Concrete numbers, cost per unit, metrics, percentage changes, or timeline years.

Respond strictly in JSON with an array of query strings or query objects:
[
  "solid state battery commercialization timeline 2025 2030",
  "site:gov solid electrolyte battery energy density cost per kWh",
  "solid state battery manufacturing yield dendrite bottleneck",
  "automotive solid state battery delayed production announcements"
]"""


def is_query_novel(new_q: str, seen_queries: set[str], threshold: float = 0.75) -> bool:
    """Check if new query has sufficient lexical novelty compared to already issued queries."""
    new_words = set(re.findall(r"\w+", new_q.lower()))
    if not new_words or len(new_words) < 2:
        return False
    for prev in seen_queries:
        prev_words = set(re.findall(r"\w+", prev.lower()))
        if not prev_words:
            continue
        overlap = len(new_words & prev_words)
        union = len(new_words | prev_words)
        jaccard = overlap / union if union > 0 else 0
        if jaccard >= threshold:
            return False
    return True


class SearchAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="SearchAgent", llm=llm)

    async def run(self, state: ResearchState) -> list[str]:
        is_first_round = state.current_round == 1
        num_queries = 5 if is_first_round else 4

        # Track context from ResearchPlan if available
        plan_context = ""
        if hasattr(state, "plan") and state.plan:
            plan_obj = state.plan
            tracks_info = []
            tracks = getattr(plan_obj, "search_tracks", [])
            for t in tracks:
                tracks_info.append(f"- Track {getattr(t, 'track_id', '')}: {getattr(t, 'sub_question', '')}")
            contradictions = getattr(plan_obj, "contradiction_targets", [])
            plan_context = (
                f"\nStructured Research Tracks:\n" + "\n".join(tracks_info) +
                (f"\nContradiction Targets to investigate:\n" + "\n".join(f"- {c}" for c in contradictions) if contradictions else "")
            )
        elif getattr(state, "research_plan", ""):
            plan_context = f"\nResearch Plan:\n{state.research_plan}"

        strategy_guidance = ""
        if hasattr(state, "mode_config") and state.mode_config:
            strategy_guidance = f"\nMode: {state.mode_config.display_name} | Strategy: {state.mode_config.search_strategy}\n"

        recent_findings = "\n".join(
            f"- {f.summary or f.facts[:200]}..." for f in state.findings[-5:]
        ) if state.findings else "No findings yet."

        round_focus = (
            "Round 1: Explore foundational breadth across tracks, primary sources, and initial academic benchmarks."
            if is_first_round else
            f"Round {state.current_round}: Dig into unresolved tracks, skepticism/counterevidence, quantitative metrics, and conflicting claims."
        )

        prompt = (
            current_date_context()
            + f"Question: {state.question}{strategy_guidance}\n"
            f"{plan_context}\n\n"
            f"Recent Findings Summary:\n{recent_findings}\n\n"
            f"Focus: {round_focus}\n\n"
            f"Generate {num_queries} queries across diverse families (broad, primary, academic, skeptical, quantitative)."
        )

        messages = [
            LLMMessage(role="system", content=SEARCH_AGENT_SYSTEM),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self._complete(messages, complexity="low")

        raw_queries: list[str] = []
        try:
            content = strip_thinking(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            parsed = json.loads(content.strip())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        raw_queries.append(item.strip())
                    elif isinstance(item, dict) and "query" in item:
                        raw_queries.append(str(item["query"]).strip())
        except (json.JSONDecodeError, AttributeError):
            pass

        if not raw_queries:
            raw_queries = [state.question]

        # Novelty and deduplication filtering
        queries_used: set = getattr(state, "queries_used", set())
        novel_queries: list[str] = []
        for q in raw_queries:
            if q not in queries_used and is_query_novel(q, queries_used, threshold=0.75):
                novel_queries.append(q)

        # Fallback: if all were filtered out by novelty, pick the least overlapping ones or raw queries
        if not novel_queries:
            novel_queries = [q for q in raw_queries if q not in queries_used]
        if not novel_queries:
            novel_queries = raw_queries[:2]  # allow repeats only if pool completely exhausted

        queries_used.update(novel_queries)

        await self.publish("search.queries_generated", {
            "queries": novel_queries,
            "round": state.current_round,
        })

        return novel_queries


# Backward compat
async def generate_queries(state: ResearchState, llm: LLMClient) -> list[str]:
    agent = SearchAgent(llm)
    return await agent.run(state)

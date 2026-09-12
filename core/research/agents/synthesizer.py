from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.state import ResearchState
from core.research.agents.base import BaseAgent
from core.research.optimizer import deduplicate_findings
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ReportOutput:
    query: str
    summary: str
    body_md: str
    citations: list[dict]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYNTHESIZE_ROUND_PROMPT = """\
You are updating an evolving research report.

**Original question:** {question}

**Current report:**
{report}

**New findings from this round:**
{new_findings}

Integrate the new findings into the existing report. Produce an updated, well-organized \
report that answers the original question as completely as possible given all evidence so far. \
Remove redundancy, resolve contradictions, and maintain logical flow. \
Keep source URLs as inline citations where relevant.

Write only the updated report — no preamble or meta-commentary."""

FINAL_REPORT_PROMPT = """\
Write a **long, detailed, comprehensive** research report answering this question:

**Question:** {question}

**All collected evidence and analysis:**
{report}

Requirements:
- Write at MINIMUM 1500 words — this should be a thorough, magazine-quality article
- Use clear ## headings and ### subheadings to organize into logical sections
- Each section should have multiple detailed paragraphs, not just bullet points
- Synthesize and analyze the information — explain WHY things matter, draw comparisons, provide context
- Include specific data points, numbers, and statistics from the evidence
- Include source URLs as inline citations [like this](url)
- Note where sources agree and where they disagree
- Add a brief executive summary at the top
- End with a clear conclusion that directly answers the question
- Write in an engaging, informative style — not dry or robotic"""

EXPAND_PROMPT = """\
This report is too brief. Please expand it significantly:
- Add detailed paragraphs for each section (not just bullet points)
- Include specific data, numbers, and comparisons from the evidence
- Explain context and significance — don't just list facts
- Use ## headings and ### subheadings
- Target at least 1000 words
Write the full expanded report now."""

# Category-specific format overrides (Odysseus-inspired)
CATEGORY_PROMPTS = {
    "product": """\
IMPORTANT FORMAT OVERRIDE — this is a PRODUCT research report:
- Structure as a RANKED LIST of products/options (best first)
- For EACH product include: name as ### heading, approximate price, 2-3 sentence summary, **Pros:** bullet list, **Cons:** bullet list, **Where to buy:** URLs as links
- Start with a quick-compare markdown table of top picks (columns: Name, Price, Best For, Rating)
- End with a ## Verdict section picking Best Overall and Best Value
- Still include source citations inline""",

    "comparison": """\
IMPORTANT FORMAT OVERRIDE — this is a COMPARISON report:
- Create a ## Comparison Table as a markdown table comparing ALL options across key criteria
- Write a ## section per option with its strengths, weaknesses, and ideal use case
- End with ## Best For verdicts
- Include a ## Shared Considerations section""",

    "howto": """\
IMPORTANT FORMAT OVERRIDE — this is a HOW-TO guide:
- Start with ## Quick Guide — a super concise numbered list (one line per step)
- Then ## Prerequisites listing what's needed before starting
- Then detailed steps: ## Step 1: ..., ## Step 2: ...
- Use blockquotes (> ) for tips and warnings
- End with ## Common Mistakes section
- Add estimated time and difficulty level near the top""",

    "factcheck": """\
IMPORTANT FORMAT OVERRIDE — this is a FACT-CHECK report:
- Start with ## The Claim restating what's being checked
- Create ## Evidence For and ## Evidence Against sections
- Include a ## Verdict section: Supported / Mixed Evidence / Unsupported
- End with ## Nuance & Caveats for important context and limitations""",
}

MAX_SYNTHESIS_CHARS = 30000  # was 80000 — cuts final synthesis token cost significantly


class SynthesizerAgent(BaseAgent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="SynthesizerAgent", llm=llm)

    async def synthesize_round(
        self,
        state: ResearchState,
        new_findings: list,
    ) -> str:
        """Incrementally update the evolving report with new round findings."""
        if not new_findings:
            return state.evolving_report

        new_findings_text = self._format_findings(new_findings)
        current_report = state.evolving_report or "(First round — no report yet.)"

        prompt = SYNTHESIZE_ROUND_PROMPT.format(
            question=state.question,
            report=current_report,
            new_findings=new_findings_text,
        )

        try:
            response = await self.llm.complete(
                [LLMMessage(role="user", content=prompt)],
                # Synthesis is a heavy generation call; 180s matches Odysseus to avoid
                # mid-stream timeouts on slow local models (#Odysseus-inspired)
                timeout=180,
            )
            updated = response.content.strip()
            return updated if updated else current_report
        except Exception:
            return state.evolving_report  # keep old on failure

    async def run(self, state: ResearchState) -> ReportOutput:
        """Generate the final polished report from the evolving report."""
        # Deduplicate findings for citations
        unique_findings = deduplicate_findings(state.findings)

        # Build the final prompt from evolving report + mode config
        evolving = state.evolving_report or self._findings_as_text(unique_findings)

        system_prompt = None
        if hasattr(state, "mode_config") and state.mode_config and getattr(state.mode_config, "synthesis_prompt", None):
            system_prompt = state.mode_config.synthesis_prompt

        if system_prompt:
            # Mode-specific synthesis (study guide, executive brief, deep academic)
            findings_text = self._findings_as_text(unique_findings)
            if state.contradictions:
                findings_text += "\n\n=== CONTRADICTIONS DETECTED ===\n"
                for c in state.contradictions:
                    findings_text += f"Conflict: {c.description} (Severity: {c.severity})\nResolution: {c.resolution_suggestion}\n\n"

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=f"Research question: {state.question}\n\nFindings:\n{findings_text}"),
            ]
            response = await self.llm.complete(messages)
            body_md = response.content.strip()
        else:
            # Standard final report generation
            body_md = await self._final_report(state.question, evolving, state)

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
            "citations_count": len(report.citations),
        })

        return report

    async def _final_report(self, question: str, evolving_report: str, state: ResearchState) -> str:
        """Write polished final report with category format override and expand-retry."""
        prompt = FINAL_REPORT_PROMPT.format(
            question=question,
            report=evolving_report,
        )

        # Inject category-specific format override
        category = getattr(state, "category", None)
        if category and category in CATEGORY_PROMPTS:
            prompt += "\n\n" + CATEGORY_PROMPTS[category]

        try:
            response = await self.llm.complete(
                [LLMMessage(role="user", content=prompt)],
                timeout=180,  # heavy generation — matches Odysseus
            )
            result = response.content.strip()

            # Expand-retry only if very short AND not a low-context provider
            if len(result.split()) < 250:  # was 400 — less aggressive expand retry
                expand_response = await self.llm.complete([
                    LLMMessage(role="user", content=prompt),
                    LLMMessage(role="assistant", content=result),
                    LLMMessage(role="user", content=EXPAND_PROMPT),
                ], timeout=180)
                expanded = expand_response.content.strip()
                if len(expanded.split()) > len(result.split()):
                    return expanded

            return result
        except Exception:
            return evolving_report  # fallback to evolving report

    def _format_findings(self, findings: list) -> str:
        """Format a list of findings for synthesis prompt."""
        blocks = []
        for i, f in enumerate(findings):
            url_line = f"[{i+1}] {f.url}"
            # Prefer richer structured fields if available
            if getattr(f, "evidence", "") or getattr(f, "summary", ""):
                block = f"{url_line}\nSummary: {f.summary}\nEvidence: {f.evidence[:400]}"  # was 800
            else:
                block = f"{url_line}\n{f.facts[:500]}"
            blocks.append(block)
        return "\n\n".join(blocks)

    def _findings_as_text(self, findings: list) -> str:
        """Format findings list, respecting MAX_SYNTHESIS_CHARS budget."""
        blocks = []
        total_chars = 0
        truncated = False

        sorted_findings = sorted(enumerate(findings), key=lambda x: x[1].round_number, reverse=True)

        for i, f in sorted_findings:
            if getattr(f, "evidence", "") or getattr(f, "summary", ""):
                block = f"[{i+1}] {f.url}\nSummary: {f.summary}\nEvidence: {f.evidence[:300]}"  # was 600
            else:
                block = f"[{i+1}] {f.url}\n{f.facts[:400]}"

            if total_chars + len(block) > MAX_SYNTHESIS_CHARS:
                truncated = True
                break
            blocks.append((i, block))
            total_chars += len(block)

        blocks.sort(key=lambda x: x[0])
        text = "\n\n".join(b[1] for b in blocks)

        if truncated:
            text = "[Earlier findings truncated for context limit.]\n\n" + text

        return text

    @staticmethod
    def _fallback_report(question: str, findings: list) -> str:
        """Compile gathered findings into a basic markdown report.

        Used when synthesis produces no output or times out, but findings were gathered.
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


# Backward compat
async def synthesize(state: ResearchState, llm: LLMClient) -> ReportOutput:
    agent = SynthesizerAgent(llm)
    return await agent.run(state)

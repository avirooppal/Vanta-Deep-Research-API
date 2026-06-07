from dataclasses import dataclass
from core.llm.client import LLMClient
from core.llm.types import Message
from core.research.extractor import Finding


@dataclass
class ReportOutput:
    query: str
    summary: str
    body_md: str
    citations: list[dict]   # [{"id": "src_1", "url": "...", "title": "..."}]


CONTINUE_PROMPT = """You are evaluating whether a research task needs more investigation.
Given the findings so far and the original question, reply with ONLY the word CONTINUE or DONE.
Reply CONTINUE if important aspects are uncovered or unclear.
Reply DONE if the findings are comprehensive enough to write a full report."""

SYNTHESIS_PROMPT = """You are a senior research analyst writing a comprehensive research report.
Given the question and collected findings below, write a well-structured markdown report.

Requirements:
- Start with a 2-3 sentence executive summary
- Use ## headings for major sections
- Include inline citation markers like [1], [2] referencing the sources list
- Be factual, cite sources for all claims
- Minimum 500 words
- End with a ## Sources section listing all cited sources

Return ONLY the markdown report."""


async def should_continue(
    question: str, findings: list[Finding], llm: LLMClient
) -> bool:
    findings_text = "\n\n".join(
        f"Source: {f.url}\n{f.facts}" for f in findings
    )
    messages = [
        Message(role="system", content=CONTINUE_PROMPT),
        Message(
            role="user",
            content=f"Question: {question}\n\nFindings so far:\n{findings_text[:6000]}",
        ),
    ]
    response = await llm.complete(messages)
    return "CONTINUE" in response.content.upper()


async def synthesize_report(
    question: str, findings: list[Finding], llm: LLMClient
) -> ReportOutput:
    findings_text = "\n\n".join(
        f"[{i+1}] {f.url}\n{f.facts}" for i, f in enumerate(findings)
    )
    messages = [
        Message(role="system", content=SYNTHESIS_PROMPT),
        Message(
            role="user",
            content=f"Research question: {question}\n\nFindings:\n{findings_text}",
        ),
    ]
    response = await llm.complete(messages)
    body_md = response.content.strip()
    summary = body_md.split("\n\n")[0].lstrip("#").strip()

    citations = [
        {"id": f"src_{i+1}", "url": f.url, "title": f.title}
        for i, f in enumerate(findings)
    ]

    return ReportOutput(
        query=question,
        summary=summary,
        body_md=body_md,
        citations=citations,
    )

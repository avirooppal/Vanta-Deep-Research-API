from dataclasses import dataclass
from core.llm.client import LLMClient
from core.llm.types import Message
from integrations.fetcher import FetchedPage


@dataclass
class Finding:
    url: str
    title: str
    facts: str      # LLM-extracted key facts
    round_number: int


EXTRACT_PROMPT = """You are a research assistant extracting key facts from a web page.
Given the page content below, extract only the facts relevant to the research question.
Be concise. Return plain text bullet points. Maximum 300 words.
If the page has no relevant content, return: NO_RELEVANT_CONTENT"""


async def extract_findings(
    page: FetchedPage,
    question: str,
    llm: LLMClient,
    round_number: int = 1,
) -> Finding | None:
    if not page.success or not page.text:
        return None

    messages = [
        Message(role="system", content=EXTRACT_PROMPT),
        Message(
            role="user",
            content=f"Research question: {question}\n\n<<<PAGE CONTENT>>>\n{page.text[:8000]}\n<<<END PAGE CONTENT>>>",
        ),
    ]
    response = await llm.complete(messages)

    if "NO_RELEVANT_CONTENT" in response.content:
        return None

    return Finding(
        url=page.url,
        title=page.title,
        facts=response.content.strip(),
        round_number=round_number,
    )

import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass

MAX_CONTENT_CHARS = 12000


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    success: bool
    error: str | None = None


async def fetch_url(url: str) -> FetchedPage:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Remove boilerplate tags
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        text = " ".join(soup.get_text(separator=" ").split())
        text = text[:MAX_CONTENT_CHARS]

        return FetchedPage(url=url, title=title, text=text, success=True)

    except Exception as exc:
        return FetchedPage(url=url, title="", text="", success=False, error=str(exc))

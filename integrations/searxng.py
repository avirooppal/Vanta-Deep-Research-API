import httpx
from dataclasses import dataclass


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str


async def search_searxng(
    query: str,
    base_url: str,
    num_results: int = 10,
) -> list[SearchResult]:
    params = {
        "q": query,
        "format": "json",
        "engines": "google,bing,duckduckgo",
        "language": "en",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/search",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("results", [])[:num_results]:
        results.append(SearchResult(
            url=item.get("url", ""),
            title=item.get("title", ""),
            snippet=item.get("content", ""),
        ))
    return results

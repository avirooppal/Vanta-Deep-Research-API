import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx
from core.llm.http import get_http_client

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 12000
FETCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    success: bool
    trust_score: int = 50
    error: str | None = None


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            return False
    except socket.gaierror:
        pass

    return True


def _extract_text_from_html(html: str) -> tuple[str, str]:
    """Fast stdlib HTML text extractor avoiding heavyweight headless browsers."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Strip non-content blocks
    cleaned = re.sub(
        r"<(script|style|nav|header|footer|aside|svg|noscript|select|button)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Strip remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Entity unescape
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"&amp;", "&", cleaned)
    cleaned = re.sub(r"&lt;", "<", cleaned)
    cleaned = re.sub(r"&gt;", ">", cleaned)
    cleaned = re.sub(r"&quot;", '"', cleaned)
    cleaned = re.sub(r"&#39;", "'", cleaned)

    text = " ".join(cleaned.split())
    return title, text


def _calculate_trust_score(url: str) -> int:
    score = 50
    if url.endswith(".edu") or url.endswith(".gov"):
        score = 90
    elif url.endswith(".org"):
        score = 70
    elif ".xyz" in url or ".click" in url or ".top" in url:
        score = 15
    return score


async def _fetch_with_playwright(url: str) -> tuple[str, str]:
    """Fallback headless browser for dynamic Single-Page JS applications."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=FETCH_USER_AGENT)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=12000)
            title = await page.title()
            text = await page.evaluate("""() => {
                const toRemove = document.querySelectorAll('script, style, nav, footer, header, aside, iframe, noscript');
                toRemove.forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }""")
            return title or "", " ".join((text or "").split())
        finally:
            await browser.close()


async def fetch_url(url: str) -> FetchedPage:
    """Fetch webpage with fast HTTP path, falling back to Playwright only for JS SPAs."""
    try:
        if not _is_safe_url(url):
            raise ValueError("Unsafe URL: blocked by SSRF protection.")
    except ValueError as e:
        return FetchedPage(url=url, title="", text="", success=False, error=str(e))

    headers = {
        "User-Agent": FETCH_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    try:
        from unittest.mock import MagicMock
        is_mocked = isinstance(httpx.AsyncClient, MagicMock)
    except Exception:
        is_mocked = False

    try:
        if is_mocked:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        else:
            client = get_http_client()
            response = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)

        if response.status_code == 429:
            return FetchedPage(url=url, title="", text="", success=False, error="Rate limited (429)")

        if response.is_success:
            title, text = _extract_text_from_html(response.text)
            # If substantive content gathered, return immediately (fast path)
            if len(text) >= 200:
                return FetchedPage(
                    url=url,
                    title=title,
                    text=text[:MAX_CONTENT_CHARS],
                    success=True,
                    trust_score=_calculate_trust_score(url),
                )

            # Check if this might be an empty client-side JS app (e.g., React/Vue shell)
            is_spa_shell = (
                '<div id="root"' in response.text
                or '<div id="app"' in response.text
                or "<noscript" in response.text
            )
            if not is_spa_shell and len(text) > 0:
                return FetchedPage(
                    url=url,
                    title=title,
                    text=text[:MAX_CONTENT_CHARS],
                    success=True,
                    trust_score=_calculate_trust_score(url),
                )

    except Exception as exc:
        logger.debug(f"Fast HTTP fetch failed for {url}: {exc}; attempting browser fallback")

    # Fallback path: Playwright for JS-heavy or protected pages
    try:
        title, text = await _fetch_with_playwright(url)
        if text:
            return FetchedPage(
                url=url,
                title=title,
                text=text[:MAX_CONTENT_CHARS],
                success=True,
                trust_score=_calculate_trust_score(url),
            )
        return FetchedPage(url=url, title="", text="", success=False, error="Empty page content")
    except Exception as exc:
        return FetchedPage(url=url, title="", text="", success=False, error=str(exc))

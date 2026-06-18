import socket
import ipaddress
from urllib.parse import urlparse
from dataclasses import dataclass
from playwright.async_api import async_playwright

MAX_CONTENT_CHARS = 12000

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
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified:
            return False
    except socket.gaierror:
        pass
    
    return True

async def fetch_url(url: str) -> FetchedPage:
    try:
        if not _is_safe_url(url):
            raise ValueError("Unsafe URL: blocked by SSRF protection.")
    except ValueError as e:
        return FetchedPage(url=url, title="", text="", success=False, error=str(e))

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Wait for network idle to allow JS apps to render
            await page.goto(url, wait_until="networkidle", timeout=15000)
            
            title = await page.title()
            
            text = await page.evaluate('''() => {
                const elementsToRemove = document.querySelectorAll('script, style, nav, footer, header, aside, iframe');
                elementsToRemove.forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }''')
            
            await browser.close()
            
            text = " ".join((text or "").split())
            text = text[:MAX_CONTENT_CHARS]
            
            trust_score = 50
            if url.endswith(".edu") or url.endswith(".gov"):
                trust_score = 90
            elif url.endswith(".org"):
                trust_score = 70
            elif ".xyz" in url or ".click" in url:
                trust_score = 10
            
            return FetchedPage(url=url, title=title, text=text, success=True, trust_score=trust_score)
            
    except Exception as exc:
        return FetchedPage(url=url, title="", text="", success=False, error=str(exc))

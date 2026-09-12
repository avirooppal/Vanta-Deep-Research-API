import httpx
from typing import Optional

_http_client: Optional[httpx.AsyncClient] = None
_http_limits = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=30,
    keepalive_expiry=30.0,
)


def get_http_client() -> httpx.AsyncClient:
    """Return process-wide pooled AsyncClient with persistent keep-alive."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            limits=_http_limits,
            http2=False,
            timeout=120.0,
        )
    return _http_client


async def close_http_client() -> None:
    """Gracefully close the global pooled client on shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None

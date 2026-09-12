import asyncio
import json
import logging
import random
import httpx
from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.http import get_http_client

logger = logging.getLogger(__name__)


def _format_anthropic_error(status: int, text: str) -> str:
    detail = ""
    try:
        j = json.loads(text) if text else {}
        if isinstance(j, dict):
            err = j.get("error") or j
            if isinstance(err, dict):
                detail = (err.get("message") or err.get("detail") or "").strip()
            elif isinstance(err, str):
                detail = err.strip()
    except Exception:
        detail = (text or "").strip()[:240]

    if status in (401, 403):
        return f"Anthropic rejected API key / access denied ({status}){f': {detail}' if detail else ''}."
    if status == 429:
        return f"Anthropic rate-limited the request (429){f': {detail}' if detail else ''}."
    if status >= 500:
        return f"Anthropic server outage (HTTP {status}){f': {detail}' if detail else ''}."
    return f"Anthropic returned HTTP {status}{f': {detail}' if detail else ''}"


async def call_anthropic(messages: list[Message], config: LLMConfig, timeout: int | None = None) -> LLMResponse:
    system_messages = [m for m in messages if m.role == "system"]
    user_messages = [m for m in messages if m.role != "system"]

    system_content = system_messages[0].content if system_messages else ""

    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens if config.max_tokens is not None else 4096,
        "system": system_content,
        "messages": [{"role": m.role, "content": m.content} for m in user_messages],
    }

    headers = {
        "x-api-key": config.api_key or "",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    max_retries = 5
    base_delay = 2.0
    http_timeout = float(timeout) if timeout else 120.0
    client = get_http_client()
    url = f"{config.base_url.rstrip('/')}/messages"

    for attempt in range(max_retries + 1):
        try:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=http_timeout,
            )
        except (httpx.TransportError, httpx.TimeoutException) as net_err:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"Anthropic transport error (attempt {attempt+1}/{max_retries+1}): {net_err}. Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(f"Anthropic network error: {net_err}") from net_err

        if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    delay = float(retry_after) + random.uniform(0.5, 1.5)
                except ValueError:
                    delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            else:
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)

            logger.warning(
                f"Anthropic HTTP {response.status_code} (attempt {attempt+1}/{max_retries+1}). Retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            continue

        if not response.is_success:
            friendly = _format_anthropic_error(response.status_code, response.text)
            raise RuntimeError(friendly)

        data = response.json()
        break

    return LLMResponse(
        content=data["content"][0].get("text") or "",
        model=data.get("model", config.model),
        tokens_in=data.get("usage", {}).get("input_tokens", 0),
        tokens_out=data.get("usage", {}).get("output_tokens", 0),
    )

import asyncio
import json
import logging
import random
import httpx
from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.http import get_http_client

logger = logging.getLogger(__name__)

# Models that require max_completion_tokens instead of max_tokens and reject custom temperature
_REASONING_MODELS = {"o1", "o3", "o4", "gpt-4.5", "gpt-5"}
_SYMBOLIC_RATE_LIMIT_STATUSES = frozenset({
    "RATE_LIMITED",
    "RATE_LIMIT_EXCEEDED",
    "RESOURCE_EXHAUSTED",
})


def _uses_max_completion_tokens(model: str | None) -> bool:
    if not model:
        return False
    m = model.lower()
    return any(m.startswith(p) or f"/{p}" in m for p in _REASONING_MODELS)


def _omit_temperature(model: str | None) -> bool:
    return _uses_max_completion_tokens(model)


def _is_symbolic_rate_limit(err_val) -> bool:
    if isinstance(err_val, dict):
        status = str(err_val.get("status") or "").strip().upper()
        if status in _SYMBOLIC_RATE_LIMIT_STATUSES:
            return True
        marker = " ".join(str(err_val.get(k) or "") for k in ("type", "code", "message", "status")).lower()
    else:
        marker = str(err_val or "").lower()

    return any(tok in marker for tok in ("rate_limit", "rate limit", "too many requests", "resource_exhausted"))


def _format_upstream_error(status: int, text: str, provider: str) -> str:
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
        return f"{provider} rejected API key / access denied ({status}){f': {detail}' if detail else ''}."
    if status == 404:
        return f"{provider} returned 404 — model or endpoint not found{f' ({detail})' if detail else ''}."
    if status == 429:
        extra = ""
        if provider == "openrouter":
            extra = " (OpenRouter free models are capped at 20 req/min & 50 req/day; use a paid model preset to avoid throttles)."
        return f"{provider} rate-limited the request (429){f': {detail}' if detail else ''}.{extra}"
    if status >= 500:
        return f"{provider} server outage or gateway error (HTTP {status}){f': {detail}' if detail else ''}."
    return f"{provider} returned HTTP {status}{f': {detail}' if detail else ''}"


async def call_openai(messages: list[Message], config: LLMConfig, timeout: int | None = None) -> LLMResponse:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    if config.provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/deepresearch"
        headers["X-Title"] = "Vanta"

    payload: dict = {
        "model": config.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }

    if not _omit_temperature(config.model) and config.temperature is not None:
        payload["temperature"] = config.temperature

    if config.max_tokens is not None:
        tok_key = "max_completion_tokens" if _uses_max_completion_tokens(config.model) else "max_tokens"
        payload[tok_key] = config.max_tokens

    max_retries = 5
    base_delay = 2.0
    http_timeout = float(timeout) if timeout else 120.0
    client = get_http_client()
    base = (config.base_url or "").rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"

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
                    f"LLM transport error on {config.provider} (attempt {attempt+1}/{max_retries+1}): {net_err}. Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(f"{config.provider} network error: {net_err}") from net_err

        # Check for 429 or symbolic rate limit in 200/400 payloads
        is_rate_limited = response.status_code == 429
        err_detail = None
        data = None

        try:
            data = response.json()
            if isinstance(data, dict) and data.get("error"):
                err_detail = data["error"]
                if _is_symbolic_rate_limit(err_detail):
                    is_rate_limited = True
        except Exception:
            pass

        # Handle transient rate-limit / server errors
        if (is_rate_limited or response.status_code in (502, 503, 504)) and attempt < max_retries:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    delay = float(retry_after) + random.uniform(0.5, 1.5)
                except ValueError:
                    delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            else:
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)

            status_lbl = "429 Rate Limit" if is_rate_limited else f"HTTP {response.status_code}"
            logger.warning(
                f"{config.provider} returned {status_lbl} (attempt {attempt+1}/{max_retries+1}). Retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            continue

        if not response.is_success or (isinstance(data, dict) and data.get("error")):
            status_code = response.status_code if response.status_code != 200 else (429 if is_rate_limited else 400)
            err_text = json.dumps(data) if data else response.text
            friendly = _format_upstream_error(status_code, err_text, config.provider)
            raise RuntimeError(friendly)

        if not data:
            data = response.json()
        break

    return LLMResponse(
        content=data["choices"][0]["message"].get("content") or "",
        model=data.get("model", config.model),
        tokens_in=data.get("usage", {}).get("prompt_tokens", 0),
        tokens_out=data.get("usage", {}).get("completion_tokens", 0),
    )


async def embed_openai(text: str, config: LLMConfig) -> list[float]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    payload = {
        "model": "text-embedding-3-small",
        "input": text,
    }

    client = get_http_client()
    response = await client.post(
        "https://api.openai.com/v1/embeddings",
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]

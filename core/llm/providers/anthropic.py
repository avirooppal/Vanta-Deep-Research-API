import httpx
import asyncio
from core.llm.types import Message, LLMResponse, LLMConfig


async def call_anthropic(messages: list[Message], config: LLMConfig) -> LLMResponse:
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

    max_retries = 3
    base_delay = 2.0

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(max_retries + 1):
            response = await client.post(
                f"{config.base_url.rstrip('/')}/messages",
                headers=headers,
                json=payload,
            )
            
            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
                
            response.raise_for_status()
            data = response.json()
            break

    return LLMResponse(
        content=data["content"][0].get("text") or "",
        model=data.get("model", config.model),
        tokens_in=data.get("usage", {}).get("input_tokens", 0),
        tokens_out=data.get("usage", {}).get("output_tokens", 0),
    )

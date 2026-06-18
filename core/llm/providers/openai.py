import httpx
from core.llm.types import Message, LLMResponse, LLMConfig


async def call_openai(messages: list[Message], config: LLMConfig) -> LLMResponse:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    if config.provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/deepresearch"
        headers["X-Title"] = "Vanta"

    payload = {
        "model": config.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": config.temperature,
    }
    
    if config.max_tokens is not None:
        payload["max_tokens"] = config.max_tokens

    import asyncio
    max_retries = 3
    base_delay = 2.0

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(max_retries + 1):
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code == 429 and attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
                
            response.raise_for_status()
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
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Use openai base url even if using openrouter etc for standard openai embedding
        # Actually just use standard openai api URL for embeddings since this is hardcoded
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

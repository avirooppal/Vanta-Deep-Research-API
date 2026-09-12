from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.providers.openai import call_openai
from core.llm.providers.anthropic import call_anthropic


import asyncio
import hashlib

class LLMClient:
    def __init__(self, config: LLMConfig, low_complexity_config: LLMConfig | None = None, enable_cache: bool = True):
        self.config = config
        self.low_complexity_config = low_complexity_config
        self.enable_cache = enable_cache
        self.cache: dict[str, LLMResponse] = {}
        self.cache_hits = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.search_queries_issued = 0
        self.sources_fetched = 0
        concurrency_limit = config.max_concurrent or 3
        if config.provider == "openrouter" and "free" in (config.model or ""):
            concurrency_limit = min(concurrency_limit, 2)
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    async def complete(self, messages: list[Message], complexity: str = "high", timeout: int | None = None) -> LLMResponse:
        cfg = self.low_complexity_config if complexity == "low" and self.low_complexity_config else self.config
        provider = cfg.provider

        cache_key = None
        if self.enable_cache:
            key_raw = f"{provider}:{cfg.model}:" + "|".join(f"{m.role}:{m.content}" for m in messages)
            cache_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
            if cache_key in self.cache:
                self.cache_hits += 1
                return self.cache[cache_key]

        OPENAI_COMPAT_PROVIDERS = (
            "openai",
            "openai_compatible",
            "azure_openai",
            "openrouter",
            "ollama",
            "ollama_cloud",
            "groq",
            "deepseek",
            "mistral",
            "together",
            "xai",
            "cerebras",
        )

        async with self._semaphore:
            if provider in OPENAI_COMPAT_PROVIDERS:
                res = await call_openai(messages, cfg, timeout=timeout)
            elif provider == "anthropic":
                res = await call_anthropic(messages, cfg, timeout=timeout)
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        if cache_key:
            self.cache[cache_key] = res

        self.total_tokens_in += res.tokens_in
        self.total_tokens_out += res.tokens_out
        return res

    async def embed(self, text: str) -> list[float]:
        # Simple routing: use openai's text-embedding-3-small for now
        from core.llm.providers.openai import embed_openai
        return await embed_openai(text, self.config)

from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.providers.openai import call_openai
from core.llm.providers.anthropic import call_anthropic


class LLMClient:
    def __init__(self, config: LLMConfig, low_complexity_config: LLMConfig | None = None):
        self.config = config
        self.low_complexity_config = low_complexity_config
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.search_queries_issued = 0
        self.sources_fetched = 0

    async def complete(self, messages: list[Message], complexity: str = "high") -> LLMResponse:
        cfg = self.low_complexity_config if complexity == "low" and self.low_complexity_config else self.config
        provider = cfg.provider

        if provider in ("openai", "openai_compatible", "azure_openai", "openrouter", "ollama"):
            res = await call_openai(messages, cfg)
        elif provider == "anthropic":
            res = await call_anthropic(messages, cfg)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.total_tokens_in += res.tokens_in
        self.total_tokens_out += res.tokens_out
        return res

    async def embed(self, text: str) -> list[float]:
        # Simple routing: use openai's text-embedding-3-small for now
        from core.llm.providers.openai import embed_openai
        return await embed_openai(text, self.config)

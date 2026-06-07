from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.providers.openai import call_openai
from core.llm.providers.anthropic import call_anthropic


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.search_queries_issued = 0
        self.sources_fetched = 0

    async def complete(self, messages: list[Message]) -> LLMResponse:
        provider = self.config.provider

        if provider in ("openai", "openai_compatible", "azure_openai", "openrouter"):
            res = await call_openai(messages, self.config)
        elif provider == "anthropic":
            res = await call_anthropic(messages, self.config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.total_tokens_in += res.tokens_in
        self.total_tokens_out += res.tokens_out
        return res


    @classmethod
    def from_backend(cls, backend) -> "LLMClient":
        from core.security.encryption import decrypt
        api_key = decrypt(backend.api_key_encrypted) if backend.api_key_encrypted else None
        config = LLMConfig(
            provider=backend.provider,
            base_url=backend.base_url,
            api_key=api_key,
            model=backend.model,
            max_concurrent=backend.max_concurrent,
        )
        return cls(config)

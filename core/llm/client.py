from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.providers.openai import call_openai
from core.llm.providers.anthropic import call_anthropic


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    async def complete(self, messages: list[Message]) -> LLMResponse:
        provider = self.config.provider

        if provider in ("openai", "openai_compatible", "azure_openai", "openrouter"):
            return await call_openai(messages, self.config)
        elif provider == "anthropic":
            return await call_anthropic(messages, self.config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

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

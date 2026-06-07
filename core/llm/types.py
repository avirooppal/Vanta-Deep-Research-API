from dataclasses import dataclass, field


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int
    tokens_out: int


@dataclass
class LLMConfig:
    provider: str        # openai | anthropic | ollama | openai_compatible
    base_url: str
    api_key: str | None
    model: str
    max_concurrent: int = 3
    temperature: float = 0.2
    max_tokens: int | None = None

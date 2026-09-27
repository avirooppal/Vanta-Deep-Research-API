"""
LLMClient — thin facade that routes all calls through LLMGateway.

Agents continue to call llm.complete() as before;
the gateway handles rate limiting, retries, circuit breaking, and observability.

The plaintext api_key is still decrypted by the ARQ worker in Phase 1.
Phase 3 will move key resolution entirely inside the gateway / Credential Broker.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.request import LLMRequest, priority_for
from core.llm.gateway import LLMGateway, GatewayEventCallback, _noop_event
from core.llm.providers.openai import call_openai

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        config: LLMConfig,
        low_complexity_config: LLMConfig | None = None,
        enable_cache: bool = True,
        gateway: LLMGateway | None = None,
        credential_id: str = "",
        job_id: str | None = None,
        on_event: GatewayEventCallback = _noop_event,
    ):
        self.config = config
        self.low_complexity_config = low_complexity_config
        self.enable_cache = enable_cache
        self.cache: dict[str, LLMResponse] = {}
        self.cache_hits = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.search_queries_issued = 0
        self.sources_fetched = 0

        # credential_id is the opaque rate-limiter identity.
        # In Phase 1 it defaults to a hash of the api_key so existing BYOK
        # jobs get per-key limiting without any DB changes.
        self._credential_id = credential_id or _derive_cred_id(config)
        self._job_id = job_id
        self._budget = None  # set via attach_budget() by the engine

        # Gateway may be injected (e.g. shared across workers) or created lazily
        self._gateway = gateway or LLMGateway(redis_client=None, on_event=on_event)

    def attach_budget(self, budget) -> None:
        """Attach a ResearchBudget; token usage is auto-recorded after each call."""
        self._budget = budget

    async def complete(
        self,
        messages: list[Message],
        complexity: str = "high",
        timeout: int | None = None,
        agent_name: str = "",
    ) -> LLMResponse:
        cfg = self.low_complexity_config if complexity == "low" and self.low_complexity_config else self.config

        # In-process cache (SHA-256 of provider+model+messages)
        cache_key = None
        if self.enable_cache:
            raw = f"{cfg.provider}:{cfg.model}:" + "|".join(
                f"{m.role}:{m.content}" for m in messages
            )
            cache_key = hashlib.sha256(raw.encode()).hexdigest()
            if cache_key in self.cache:
                self.cache_hits += 1
                return self.cache[cache_key]

        req = LLMRequest(
            job_id=self._job_id,
            agent_name=agent_name,
            credential_id=self._credential_id,
            provider=cfg.provider,
            model=cfg.model,
            messages=messages,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_tokens,
            priority=priority_for(agent_name),
            complexity=complexity,
            timeout_override=float(timeout) if timeout else None,
        )

        result = await self._gateway.complete(req, cfg)

        if cache_key:
            self.cache[cache_key] = result

        self.total_tokens_in += result.tokens_in
        self.total_tokens_out += result.tokens_out

        # Auto-record into budget if one is attached (set by engine)
        if self._budget is not None:
            self._budget.record(result.tokens_in, result.tokens_out)

        return result

    async def embed(self, text: str) -> list[float]:
        from core.llm.providers.openai import embed_openai
        return await embed_openai(text, self.config)


def _derive_cred_id(config: LLMConfig) -> str:
    """
    Derive a stable opaque credential ID from the api_key.

    Used in Phase 1 so rate limiting is per-credential without a Broker.
    Never logs the key; only a SHA-256 prefix is stored.
    """
    key = config.api_key or ""
    provider = config.provider or ""
    digest = hashlib.sha256(f"{provider}:{key}".encode()).hexdigest()
    return f"cred_{digest[:24]}"

"""
Vanta LLM Gateway — Phase 3

Phase 3 changes:
  - Credential Broker resolution at the outbound boundary.
  - LLMConfig.api_key is now optional; gateway resolves key from broker.
  - Falls back to LLMConfig.api_key if no broker entry found (backward compat).
  - Agents and workers never receive or handle plaintext keys.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from core.llm.errors import (
    CircuitOpenError,
    ContextTooLargeError,
    InvalidAPIKeyError,
    LLMError,
    MalformedRequestError,
    ModelNotAvailableError,
    PermanentLLMError,
    PolicyViolationError,
    ProviderUnavailableError,
    QuotaExhaustedError,
    RateLimitError,
    RetryableLLMError,
    TimeoutError as LLMTimeoutError,
    ConnectionError as LLMConnectionError,
)
from core.llm.request import LLMRequest
from core.llm.types import LLMConfig, LLMResponse, Message
from core.llm.rate_limiter import (
    CredentialLimits,
    JobLimits,
    RateLimiter,
    ReservationToken,
)
from core.llm.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple token estimator (Phase 2 will add tiktoken/actual counting)
# ---------------------------------------------------------------------------

def _estimate_tokens(messages: list[Message]) -> int:
    """Rough 1-token-per-4-chars estimate. Good enough for pre-call budgeting."""
    total_chars = sum(len(m.content) for m in messages)
    return max(1, total_chars // 4)


# ---------------------------------------------------------------------------
# Timeout profiles (seconds) by agent name
# ---------------------------------------------------------------------------

_TIMEOUT_PROFILES: dict[str, dict[str, float]] = {
    "ValidatorAgent":      {"connect": 10, "read": 30,  "overall": 45},
    "SearchAgent":         {"connect": 10, "read": 30,  "overall": 45},
    "CoordinatorAgent":    {"connect": 10, "read": 60,  "overall": 90},
    "ExtractorAgent":      {"connect": 10, "read": 90,  "overall": 120},
    "ContradictionAgent":  {"connect": 10, "read": 90,  "overall": 120},
    "SynthesizerAgent":    {"connect": 10, "read": 180, "overall": 240},
    "CitationVerifierAgent": {"connect": 10, "read": 60, "overall": 90},
}
_DEFAULT_TIMEOUT = {"connect": 10, "read": 120, "overall": 150}


def _overall_timeout(agent_name: str, override: Optional[float] = None) -> float:
    if override is not None:
        return override
    return _TIMEOUT_PROFILES.get(agent_name, _DEFAULT_TIMEOUT)["overall"]


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------

_MAX_RETRIES = 4
_BASE_BACKOFF = 2.0      # seconds
_MAX_BACKOFF = 64.0


def _backoff(attempt: int, retry_after: Optional[float] = None) -> float:
    if retry_after is not None:
        return retry_after + random.uniform(0.5, 2.0)
    delay = min(_BASE_BACKOFF * (2 ** attempt), _MAX_BACKOFF)
    return delay + random.uniform(0.5, 1.5)


# ---------------------------------------------------------------------------
# Provider call dispatch — thin adapter layer (Phase 1: reuse existing fns)
# ---------------------------------------------------------------------------

OPENAI_COMPAT = frozenset({
    "openai", "openai_compatible", "azure_openai",
    "openrouter", "ollama", "ollama_cloud",
    "groq", "deepseek", "mistral", "together", "xai", "cerebras",
})


async def _call_provider(config: LLMConfig, messages: list[Message],
                          timeout: float) -> LLMResponse:
    """
    Dispatch to the appropriate low-level provider function.
    Wraps all errors into typed LLMError subclasses.
    """
    import httpx
    import core.llm.client as client_mod
    call_openai = getattr(client_mod, "call_openai", None)
    if call_openai is None:
        from core.llm.providers.openai import call_openai
    from core.llm.providers.anthropic import call_anthropic

    provider = config.provider
    try:
        if provider in OPENAI_COMPAT:
            raw = await call_openai(messages, config, timeout=int(timeout))
        elif provider == "anthropic":
            raw = await call_anthropic(messages, config, timeout=int(timeout))
        else:
            raise MalformedRequestError(
                f"Unsupported provider: {provider}", provider=provider
            )
        return raw

    except LLMError:
        raise  # already typed

    except RuntimeError as exc:
        # Existing providers raise bare RuntimeError with friendly messages.
        # Classify by message content.
        msg = str(exc)
        _raise_classified(msg, provider=provider, model=config.model)

    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(str(exc), provider=provider) from exc

    except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
        raise LLMConnectionError(str(exc), provider=provider) from exc


def _raise_classified(msg: str, *, provider: str, model: str = "") -> None:
    """Convert RuntimeError message text to a typed LLMError and raise it."""
    m = msg.lower()
    if "rate-limited" in m or "rate limit" in m or "429" in m or "resource_exhausted" in m:
        raise RateLimitError(msg, provider=provider, model=model)
    if "rejected api key" in m or "access denied" in m or "401" in m or "403" in m:
        raise InvalidAPIKeyError(msg, provider=provider, model=model)
    if "404" in m or "model or endpoint not found" in m:
        raise ModelNotAvailableError(msg, provider=provider, model=model)
    if "context" in m and ("too large" in m or "length" in m or "maximum" in m):
        raise ContextTooLargeError(msg, provider=provider, model=model)
    if "outage" in m or "50" in m:
        raise ProviderUnavailableError(msg, provider=provider, model=model)
    raise LLMError(msg, provider=provider, model=model)


# ---------------------------------------------------------------------------
# Event callback type (for SSE streaming)
# ---------------------------------------------------------------------------

GatewayEventCallback = Callable[[dict], Awaitable[None]]


async def _noop_event(event: dict) -> None:
    pass


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

@dataclass
class GatewayConfig:
    max_retries: int = _MAX_RETRIES
    # Concurrency / rate limits can be overridden here or per-request
    default_cred_limits: CredentialLimits = field(default_factory=CredentialLimits)
    default_job_limits: JobLimits = field(default_factory=JobLimits)
    # Circuit breaker tuning
    cb_failure_threshold: int = 5
    cb_half_open_after: float = 60.0


class LLMGateway:
    """
    Central gateway for all LLM calls in Vanta.

    Instantiate once per worker / application instance and share.
    Redis is required for multi-worker rate limiting; pass None to disable
    (single-process / test mode).
    """

    def __init__(
        self,
        redis_client=None,
        config: GatewayConfig = GatewayConfig(),
        on_event: GatewayEventCallback = _noop_event,
    ):
        self._cfg = config
        self._on_event = on_event
        self._rate_limiter = RateLimiter(redis_client)
        self._circuit = CircuitBreaker(
            redis_client,
            failure_threshold=config.cb_failure_threshold,
            half_open_after=config.cb_half_open_after,
        )

    async def _resolve_config(self, llm_config: LLMConfig, credential_id: str) -> LLMConfig:
        """
        Resolve the API key from the Credential Broker at the outbound boundary.

        Returns a NEW LLMConfig with the key populated.
        The key must not be stored, logged, or returned beyond _call_provider().
        Falls back to llm_config.api_key if no broker entry exists.
        """
        # Avoid importing at module level so broker is not required for tests
        try:
            from core.security.credentials.local_store import resolve_secret
            resolved = await resolve_secret(credential_id)
            if resolved is not None:
                return LLMConfig(
                    provider=resolved.provider or llm_config.provider,
                    base_url=resolved.base_url or llm_config.base_url,
                    api_key=resolved.api_key,        # plaintext — scope-limited
                    model=resolved.model or llm_config.model,
                    max_concurrent=llm_config.max_concurrent,
                    temperature=llm_config.temperature,
                    max_tokens=llm_config.max_tokens,
                )
        except Exception as exc:
            logger.warning("Credential broker lookup failed for %s: %s", credential_id, exc)

        # Fallback: use whatever is already in llm_config (Phase 1 compat)
        return llm_config


    async def complete(
        self,
        req: LLMRequest,
        llm_config: LLMConfig,
    ) -> LLMResponse:
        """
        Execute an LLM request through the full gateway pipeline.

        Phase 3: the gateway resolves the API key from the Credential Broker
        at the outbound boundary only. llm_config.api_key is used as a fallback
        for backward compatibility (e.g. tests, Ollama with no key).
        Agents and workers never see the resolved plaintext key.
        """
        provider = llm_config.provider
        credential_id = req.credential_id or f"anon_{provider}"
        prov_cb_key = self._circuit.provider_key(provider)
        cred_cb_key = self._circuit.cred_key(credential_id)
        timeout = _overall_timeout(req.agent_name, req.timeout_override)

        estimated = req.estimated_input_tokens or _estimate_tokens(req.messages)

        for attempt in range(self._cfg.max_retries + 1):
            req.attempt = attempt

            # 1. Circuit breakers
            if await self._circuit.is_open(prov_cb_key):
                raise CircuitOpenError(
                    f"Provider circuit OPEN: {provider}",
                    provider=provider, model=req.model, agent=req.agent_name,
                    request_id=req.request_id,
                )
            if await self._circuit.is_open(cred_cb_key):
                raise CircuitOpenError(
                    f"Credential circuit OPEN for {credential_id}",
                    provider=provider, model=req.model, agent=req.agent_name,
                    request_id=req.request_id,
                )

            # 2. Rate limit / concurrency reserve
            allowed, reason, token = await self._rate_limiter.reserve(
                credential_id=credential_id,
                provider=provider,
                job_id=req.job_id,
                estimated_tokens=estimated,
                cred_limits=self._cfg.default_cred_limits,
                job_limits=self._cfg.default_job_limits,
            )

            if not allowed:
                cooldown = await self._rate_limiter.cooldown_remaining(credential_id)
                wait = max(cooldown, _backoff(attempt))
                await self._on_event({
                    "type": "llm_waiting",
                    "reason": "rate_limit",
                    "provider": provider,
                    "retry_after_seconds": round(wait, 1),
                    "agent": req.agent_name,
                    "request_id": req.request_id,
                })
                logger.info(
                    "Gateway capacity unavailable (%s) for cred=%s job=%s attempt=%d; "
                    "back-off %.1fs",
                    reason, credential_id, req.job_id, attempt, wait,
                )
                if attempt < self._cfg.max_retries:
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(
                    f"Capacity unavailable after {attempt+1} attempts ({reason})",
                    provider=provider, model=req.model, agent=req.agent_name,
                    request_id=req.request_id,
                )

            # 3. Resolve credential at outbound boundary (Phase 3)
            #    Key never leaves this scope — not logged, not returned, not stored.
            resolved_config = await self._resolve_config(llm_config, credential_id)

            # 4. Execute provider call
            actual_tokens = 0
            try:
                t0 = time.monotonic()
                result = await _call_provider(resolved_config, req.messages, timeout)
                latency = time.monotonic() - t0
                actual_tokens = result.tokens_in + result.tokens_out

                # Ingest any rate-limit headers (none available from existing
                # providers in Phase 1 — they don't surface headers yet)
                await self._circuit.record_success(prov_cb_key)
                await self._circuit.record_success(cred_cb_key)

                logger.debug(
                    "LLM OK: provider=%s model=%s agent=%s tokens=%d latency=%.2fs "
                    "req=%s",
                    provider, req.model, req.agent_name,
                    actual_tokens, latency, req.request_id,
                )
                await self._on_event({
                    "type": "llm_ok",
                    "provider": provider,
                    "model": req.model,
                    "agent": req.agent_name,
                    "tokens": actual_tokens,
                    "latency_s": round(latency, 3),
                    "request_id": req.request_id,
                })
                return result

            except ContextTooLargeError:
                # Non-retryable — caller must rebuild context
                await self._rate_limiter.release(token, actual_tokens=0)
                raise

            except PermanentLLMError as exc:
                await self._circuit.record_failure(cred_cb_key, force_open=isinstance(exc, InvalidAPIKeyError))
                await self._rate_limiter.release(token, actual_tokens=0)
                logger.error(
                    "Permanent LLM error: %s req=%s", exc, req.request_id
                )
                raise

            except RateLimitError as exc:
                retry_after = exc.retry_after
                await self._rate_limiter.release(token, actual_tokens=0)
                if retry_after:
                    await self._rate_limiter.set_cooldown(credential_id, retry_after)

                await self._circuit.record_failure(cred_cb_key)
                wait = _backoff(attempt, retry_after)
                logger.warning(
                    "Rate limit on %s cred=%s attempt=%d/%d; back-off %.1fs",
                    provider, credential_id, attempt, self._cfg.max_retries, wait,
                )
                await self._on_event({
                    "type": "llm_waiting",
                    "reason": "rate_limit",
                    "provider": provider,
                    "retry_after_seconds": round(wait, 1),
                    "agent": req.agent_name,
                    "request_id": req.request_id,
                })
                if attempt < self._cfg.max_retries:
                    await asyncio.sleep(wait)
                    continue
                raise

            except RetryableLLMError as exc:
                await self._circuit.record_failure(
                    prov_cb_key if isinstance(exc, ProviderUnavailableError) else cred_cb_key
                )
                await self._rate_limiter.release(token, actual_tokens=0)
                wait = _backoff(attempt)
                logger.warning(
                    "Retryable error on %s attempt=%d/%d: %s; back-off %.1fs",
                    provider, attempt, self._cfg.max_retries, exc, wait,
                )
                if attempt < self._cfg.max_retries:
                    await asyncio.sleep(wait)
                    continue
                raise

            except Exception as exc:
                # Classify bare RuntimeError messages from existing provider adapters
                if isinstance(exc, RuntimeError):
                    await self._rate_limiter.release(token, actual_tokens=0)
                    _raise_classified(str(exc), provider=provider, model=req.model)
                # Unexpected — release reservation and surface
                await self._rate_limiter.release(token, actual_tokens=0)
                logger.exception("Unexpected error in LLM gateway: %s", exc)
                raise

            finally:
                # Reconcile only if the success path completed (token not yet released)
                if not token._released:
                    await self._rate_limiter.release(token, actual_tokens=actual_tokens)

        # Should be unreachable
        raise LLMError("Gateway retry loop exhausted", provider=provider)


# ---------------------------------------------------------------------------
# Module-level singleton (initialized lazily)
# ---------------------------------------------------------------------------

_gateway: Optional[LLMGateway] = None


def get_gateway(redis_client=None, on_event: GatewayEventCallback = _noop_event) -> LLMGateway:
    """Return (or lazily create) the process-wide gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway(redis_client=redis_client, on_event=on_event)
    return _gateway


def reset_gateway():
    """Force re-creation (test isolation)."""
    global _gateway
    _gateway = None

"""
Typed LLM error hierarchy for Vanta.

All provider adapters raise subtypes of LLMError so the gateway
can classify and route without string-matching.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base for all LLM-layer errors."""
    code: str = "LLM_ERROR"

    def __init__(self, message: str, *, provider: str = "", model: str = "",
                 agent: str = "", retry_after: Optional[float] = None,
                 request_id: str = ""):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.agent = agent
        self.retry_after = retry_after
        self.request_id = request_id

    def safe_dict(self) -> dict:
        """User-facing metadata — never contains secrets."""
        return {
            "code": self.code,
            "message": str(self),
            "provider": self.provider,
            "model": self.model,
            "agent": self.agent,
            "retry_after_seconds": self.retry_after,
            "request_id": self.request_id,
        }


# ---------------------------------------------------------------------------
# Retryable — gateway will back-off and retry
# ---------------------------------------------------------------------------

class RetryableLLMError(LLMError):
    """Transient error; the gateway should retry with back-off."""
    code = "RETRYABLE_ERROR"


class RateLimitError(RetryableLLMError):
    """Provider returned 429 or symbolic rate-limit signal."""
    code = "RATE_LIMITED"


class ProviderUnavailableError(RetryableLLMError):
    """5xx / connection failure from provider."""
    code = "PROVIDER_UNAVAILABLE"


class TimeoutError(RetryableLLMError):  # noqa: A001
    """Read / overall deadline exceeded."""
    code = "REQUEST_TIMEOUT"


class ConnectionError(RetryableLLMError):  # noqa: A001
    """Transport-level failure (TCP reset, DNS, etc.)."""
    code = "CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# Non-retryable — gateway gives up immediately
# ---------------------------------------------------------------------------

class PermanentLLMError(LLMError):
    """Non-transient error; retrying won't help."""
    code = "PERMANENT_ERROR"


class InvalidAPIKeyError(PermanentLLMError):
    """401/403 — bad or revoked key."""
    code = "API_KEY_INVALID"


class ModelNotAvailableError(PermanentLLMError):
    """404 or model-not-found."""
    code = "MODEL_NOT_AVAILABLE"


class MalformedRequestError(PermanentLLMError, ValueError):
    """400 — bad payload structure."""
    code = "MALFORMED_REQUEST"


class QuotaExhaustedError(PermanentLLMError):
    """Billing or hard quota is exhausted (not a transient 429)."""
    code = "PROVIDER_QUOTA_EXHAUSTED"


class PolicyViolationError(PermanentLLMError):
    """Provider content-policy block."""
    code = "POLICY_DENIED"


# ---------------------------------------------------------------------------
# Special — recoverable by restructuring the request
# ---------------------------------------------------------------------------

class ContextTooLargeError(LLMError):
    """Prompt exceeds model context window.

    Not retried as-is; the caller should rebuild a smaller context.
    """
    code = "CONTEXT_TOO_LARGE"


# ---------------------------------------------------------------------------
# Gateway-level
# ---------------------------------------------------------------------------

class CircuitOpenError(LLMError):
    """Circuit breaker is OPEN; request rejected without touching provider."""
    code = "CIRCUIT_OPEN"


class BudgetExhaustedError(LLMError):
    """Job token / cost budget consumed."""
    code = "BUDGET_EXHAUSTED"


class CapacityUnavailableError(RetryableLLMError):
    """Rate-limit / concurrency slot unavailable; will be deferred."""
    code = "CAPACITY_UNAVAILABLE"

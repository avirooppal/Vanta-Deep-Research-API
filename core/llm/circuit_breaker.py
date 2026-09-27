"""
Circuit breakers for Vanta LLM Gateway.

Two separate breaker namespaces:
  - per-provider  (shared across all credentials on that provider)
  - per-credential (isolated so one bad key doesn't condemn a provider)

States: CLOSED → OPEN → HALF_OPEN → CLOSED

Redis keys:
  vanta:llm:circuit:provider:{provider}   →  json {state, opened_at, failures}
  vanta:llm:circuit:cred:{credential_id} →  json {state, opened_at, failures}
"""
from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_DEFAULT_FAILURE_THRESHOLD = 5        # failures before opening
_DEFAULT_HALF_OPEN_AFTER = 60.0       # seconds before probing
_DEFAULT_SUCCESS_THRESHOLD = 2        # successes in HALF_OPEN before closing
_DEFAULT_TTL = 3600                   # Redis key TTL (seconds)


class CircuitBreaker:
    """
    Shared (Redis-backed) circuit breaker.

    Design: lightweight — state stored as JSON string in Redis.
    Each worker reads/writes atomically via WATCH/MULTI or simple SET
    (last-write-wins is acceptable for circuit state).
    """

    def __init__(
        self,
        redis_client=None,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        half_open_after: float = _DEFAULT_HALF_OPEN_AFTER,
        success_threshold: int = _DEFAULT_SUCCESS_THRESHOLD,
    ):
        self._redis = redis_client
        self.failure_threshold = failure_threshold
        self.half_open_after = half_open_after
        self.success_threshold = success_threshold

        # In-memory fallback when Redis is unavailable
        self._local: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def provider_key(self, provider: str) -> str:
        return f"vanta:llm:circuit:provider:{provider}"

    def cred_key(self, credential_id: str) -> str:
        return f"vanta:llm:circuit:cred:{credential_id}"

    async def is_open(self, key: str) -> bool:
        """True if the circuit is OPEN (requests should be rejected)."""
        state = await self._get_state(key)
        now = time.time()

        if state["state"] == CircuitState.OPEN:
            if now - state.get("opened_at", 0) >= self.half_open_after:
                # Transition to HALF_OPEN for a probe
                state["state"] = CircuitState.HALF_OPEN
                state["half_open_successes"] = 0
                await self._set_state(key, state)
                logger.info("Circuit %s → HALF_OPEN", key)
                return False  # allow one probe request
            return True

        return False

    async def record_success(self, key: str):
        state = await self._get_state(key)
        if state["state"] == CircuitState.HALF_OPEN:
            state["half_open_successes"] = state.get("half_open_successes", 0) + 1
            if state["half_open_successes"] >= self.success_threshold:
                state = self._closed_state()
                logger.info("Circuit %s → CLOSED (recovered)", key)
        elif state["state"] == CircuitState.CLOSED:
            # Reset failure count on success
            state["failures"] = 0
        await self._set_state(key, state)

    async def record_failure(self, key: str, force_open: bool = False):
        state = await self._get_state(key)
        state["failures"] = state.get("failures", 0) + 1

        should_open = force_open or state["failures"] >= self.failure_threshold
        if should_open and state["state"] != CircuitState.OPEN:
            state["state"] = CircuitState.OPEN
            state["opened_at"] = time.time()
            logger.warning(
                "Circuit %s → OPEN after %d failures", key, state["failures"]
            )
        elif state["state"] == CircuitState.HALF_OPEN:
            # Failed probe — reopen
            state["state"] = CircuitState.OPEN
            state["opened_at"] = time.time()
            logger.warning("Circuit %s → OPEN (probe failed)", key)

        await self._set_state(key, state)

    async def get_state(self, key: str) -> CircuitState:
        s = await self._get_state(key)
        return CircuitState(s["state"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _closed_state() -> dict:
        return {"state": CircuitState.CLOSED, "failures": 0, "opened_at": 0,
                "half_open_successes": 0}

    async def _get_state(self, key: str) -> dict:
        if self._redis is not None:
            raw = await self._redis.get(key)
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    pass
        return self._local.get(key, self._closed_state())

    async def _set_state(self, key: str, state: dict):
        if self._redis is not None:
            await self._redis.set(key, json.dumps(state), ex=_DEFAULT_TTL)
        else:
            self._local[key] = state

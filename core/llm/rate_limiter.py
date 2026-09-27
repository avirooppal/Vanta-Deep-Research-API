"""
Redis-backed per-credential rate limiter for Vanta LLM Gateway.

All state lives in Redis so multiple ARQ workers share consistent limits.
The limiter uses atomic Lua scripts to prevent TOCTOU races.

Redis key schema:
  vanta:llm:cred:{credential_id}:rpm       — sliding window request counter (EXPIRE = window)
  vanta:llm:cred:{credential_id}:tpm       — sliding window token counter
  vanta:llm:cred:{credential_id}:active    — current concurrent call count (INCR/DECR)
  vanta:llm:cred:{credential_id}:cooldown  — unix timestamp until which this cred is on cooldown
  vanta:llm:provider:{provider}:active     — global provider concurrency
  vanta:llm:job:{job_id}:active            — per-job concurrency
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua: atomic check-and-reserve for RPM + TPM + active slots
# ---------------------------------------------------------------------------

_LUA_RESERVE = """
local rpm_key    = KEYS[1]
local tpm_key    = KEYS[2]
local active_key = KEYS[3]
local cooldown_key = KEYS[4]

local max_rpm    = tonumber(ARGV[1])
local max_tpm    = tonumber(ARGV[2])
local max_active = tonumber(ARGV[3])
local est_tokens = tonumber(ARGV[4])
local now        = tonumber(ARGV[5])
local rpm_window = tonumber(ARGV[6])   -- seconds (60)

-- Check cooldown
local cooldown = redis.call('GET', cooldown_key)
if cooldown and tonumber(cooldown) > now then
    return {-1, 'cooldown', tonumber(cooldown)}
end

-- Check RPM
local cur_rpm = tonumber(redis.call('GET', rpm_key) or 0)
if max_rpm > 0 and cur_rpm >= max_rpm then
    return {-1, 'rpm', cur_rpm}
end

-- Check TPM
local cur_tpm = tonumber(redis.call('GET', tpm_key) or 0)
if max_tpm > 0 and cur_tpm + est_tokens > max_tpm then
    return {-1, 'tpm', cur_tpm}
end

-- Check concurrency
local cur_active = tonumber(redis.call('GET', active_key) or 0)
if max_active > 0 and cur_active >= max_active then
    return {-1, 'active', cur_active}
end

-- Reserve
local new_rpm = redis.call('INCR', rpm_key)
if new_rpm == 1 then
    redis.call('EXPIRE', rpm_key, rpm_window)
end
local new_tpm = redis.call('INCRBY', tpm_key, est_tokens)
if new_tpm == est_tokens then
    redis.call('EXPIRE', tpm_key, rpm_window)
end
redis.call('INCR', active_key)

return {1, 'ok', 0}
"""

_LUA_RELEASE = """
local active_key = KEYS[1]
local tpm_key    = KEYS[2]
local est_tokens = tonumber(ARGV[1])
local actual_tokens = tonumber(ARGV[2])

-- Decrement concurrency
local cur = tonumber(redis.call('GET', active_key) or 0)
if cur > 0 then
    redis.call('DECR', active_key)
end

-- Reconcile token estimate vs actual
local delta = actual_tokens - est_tokens
if delta ~= 0 then
    local new_tpm = redis.call('INCRBY', tpm_key, delta)
    -- Clamp to 0 — never go negative
    if tonumber(new_tpm) < 0 then
        redis.call('SET', tpm_key, 0)
    end
end

return 1
"""


@dataclass
class CredentialLimits:
    """Configurable limits per credential (or provider defaults)."""
    max_rpm: int = 0           # 0 = unlimited
    max_tpm: int = 0
    max_concurrent: int = 2
    rpm_window_seconds: int = 60


@dataclass
class ProviderLimits:
    max_concurrent: int = 16


@dataclass
class JobLimits:
    max_concurrent: int = 2


# Default limits per provider (conservative; override via config/BYOK metadata)
_PROVIDER_DEFAULTS: dict[str, ProviderLimits] = {
    "openai": ProviderLimits(max_concurrent=16),
    "anthropic": ProviderLimits(max_concurrent=8),
    "openrouter": ProviderLimits(max_concurrent=8),
    "ollama": ProviderLimits(max_concurrent=4),
    "groq": ProviderLimits(max_concurrent=4),
}


@dataclass
class ReservationToken:
    """Returned by reserve(); must be released via release() after the call."""
    credential_id: str
    provider: str
    job_id: Optional[str]
    estimated_tokens: int
    _released: bool = field(default=False, repr=False)


class RateLimiter:
    """
    Redis-backed per-credential rate limiter.

    Usage:
        token = await limiter.reserve(credential_id, provider, job_id, est_tokens, limits)
        try:
            result = await provider_call(...)
            await limiter.release(token, actual_tokens=result.tokens_in + result.tokens_out)
        except RateLimitError as e:
            await limiter.set_cooldown(credential_id, e.retry_after or 30)
            await limiter.release(token, actual_tokens=0)
            raise
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._reserve_script = None
        self._release_script = None

    def _cred_key(self, cid: str, suffix: str) -> str:
        return f"vanta:llm:cred:{cid}:{suffix}"

    def _provider_key(self, provider: str, suffix: str) -> str:
        return f"vanta:llm:provider:{provider}:{suffix}"

    def _job_key(self, job_id: str, suffix: str) -> str:
        return f"vanta:llm:job:{job_id}:{suffix}"

    async def _ensure_scripts(self):
        if self._redis is None:
            return
        if self._reserve_script is None:
            self._reserve_script = self._redis.register_script(_LUA_RESERVE)
        if self._release_script is None:
            self._release_script = self._redis.register_script(_LUA_RELEASE)

    async def reserve(
        self,
        credential_id: str,
        provider: str,
        job_id: Optional[str],
        estimated_tokens: int,
        cred_limits: CredentialLimits = CredentialLimits(),
        provider_limits: Optional[ProviderLimits] = None,
        job_limits: JobLimits = JobLimits(),
    ) -> tuple[bool, str, ReservationToken]:
        """
        Atomically check limits and reserve capacity.

        Returns (allowed, reason, token).
        If allowed=False, reason explains which limit was hit.
        Token is always returned; if allowed=False it's a no-op token.
        """
        token = ReservationToken(
            credential_id=credential_id,
            provider=provider,
            job_id=job_id,
            estimated_tokens=estimated_tokens,
        )

        if self._redis is None:
            # No Redis — pass-through (dev/test with no Redis)
            return True, "ok", token

        await self._ensure_scripts()

        pl = provider_limits or _PROVIDER_DEFAULTS.get(provider, ProviderLimits())
        now = int(time.time())

        # 1. Check + reserve credential-level limits
        result = await self._reserve_script(
            keys=[
                self._cred_key(credential_id, "rpm"),
                self._cred_key(credential_id, "tpm"),
                self._cred_key(credential_id, "active"),
                self._cred_key(credential_id, "cooldown"),
            ],
            args=[
                cred_limits.max_rpm,
                cred_limits.max_tpm,
                cred_limits.max_concurrent,
                estimated_tokens,
                now,
                cred_limits.rpm_window_seconds,
            ],
        )

        if result[0] != 1:
            reason = result[1] if len(result) > 1 else "unknown"
            logger.debug("Credential %s blocked by %s", credential_id, reason)
            token._released = True  # nothing was reserved
            return False, f"cred_{reason}", token

        # 2. Check provider concurrency (simpler INCR/GET check — acceptable
        #    slight race for provider-wide limits; not safety-critical)
        prov_active_key = self._provider_key(provider, "active")
        cur_prov = int(await self._redis.get(prov_active_key) or 0)
        if pl.max_concurrent > 0 and cur_prov >= pl.max_concurrent:
            # Roll back credential reservation
            await self._release_token_internal(credential_id, estimated_tokens, 0)
            token._released = True
            return False, "provider_active", token
        await self._redis.incr(prov_active_key)
        await self._redis.expire(prov_active_key, 300)

        # 3. Per-job concurrency
        if job_id:
            job_active_key = self._job_key(job_id, "active")
            cur_job = int(await self._redis.get(job_active_key) or 0)
            if job_limits.max_concurrent > 0 and cur_job >= job_limits.max_concurrent:
                await self._release_token_internal(credential_id, estimated_tokens, 0)
                await self._redis.decr(prov_active_key)
                token._released = True
                return False, "job_active", token
            await self._redis.incr(job_active_key)
            await self._redis.expire(job_active_key, 300)

        return True, "ok", token

    async def _release_token_internal(self, credential_id: str, estimated: int, actual: int):
        if self._redis is None:
            return
        await self._release_script(
            keys=[
                self._cred_key(credential_id, "active"),
                self._cred_key(credential_id, "tpm"),
            ],
            args=[estimated, actual],
        )

    async def release(
        self,
        token: ReservationToken,
        actual_tokens: int = 0,
    ):
        """Release reservation; reconcile estimated vs actual token use."""
        if token._released or self._redis is None:
            return
        token._released = True

        await self._release_token_internal(
            token.credential_id, token.estimated_tokens, actual_tokens
        )

        # Release provider slot
        prov_active_key = self._provider_key(token.provider, "active")
        cur = int(await self._redis.get(prov_active_key) or 0)
        if cur > 0:
            await self._redis.decr(prov_active_key)

        # Release job slot
        if token.job_id:
            job_active_key = self._job_key(token.job_id, "active")
            cur_j = int(await self._redis.get(job_active_key) or 0)
            if cur_j > 0:
                await self._redis.decr(job_active_key)

    async def set_cooldown(self, credential_id: str, seconds: float):
        """Place credential in cooldown (e.g. after 429 with Retry-After)."""
        if self._redis is None:
            return
        until = int(time.time()) + int(seconds) + 2  # +2s buffer
        await self._redis.set(
            self._cred_key(credential_id, "cooldown"),
            until,
            ex=int(seconds) + 10,
        )
        logger.info("Credential %s on cooldown for %.0fs", credential_id, seconds)

    async def clear_cooldown(self, credential_id: str):
        if self._redis is None:
            return
        await self._redis.delete(self._cred_key(credential_id, "cooldown"))

    async def cooldown_remaining(self, credential_id: str) -> float:
        """Seconds remaining in cooldown, or 0 if not cooling down."""
        if self._redis is None:
            return 0.0
        val = await self._redis.get(self._cred_key(credential_id, "cooldown"))
        if not val:
            return 0.0
        remaining = float(val) - time.time()
        return max(0.0, remaining)

    async def ingest_rate_limit_headers(
        self, credential_id: str, headers: dict
    ):
        """Parse provider response headers and update limiter state."""
        if self._redis is None:
            return

        # OpenAI-style headers
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                await self.set_cooldown(credential_id, float(retry_after))
            except ValueError:
                pass

        # x-ratelimit-remaining-requests / x-ratelimit-reset-requests
        rem_req = headers.get("x-ratelimit-remaining-requests")
        if rem_req is not None:
            try:
                if int(rem_req) <= 0:
                    reset = headers.get("x-ratelimit-reset-requests", "60s")
                    secs = _parse_reset_duration(reset)
                    await self.set_cooldown(credential_id, secs)
            except (ValueError, TypeError):
                pass


def _parse_reset_duration(s: str) -> float:
    """Parse '1.234s' or '1234ms' or plain int into seconds."""
    s = str(s).strip()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    if s.endswith("s"):
        return float(s[:-1])
    try:
        return float(s)
    except ValueError:
        return 60.0

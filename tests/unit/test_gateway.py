"""
Phase 1 tests — LLM Gateway, rate limiter, circuit breaker, error types.

All tests are pure-Python; no real HTTP calls or Redis.
Redis is mocked with a minimal in-memory dict.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from core.llm.errors import (
    CircuitOpenError,
    ContextTooLargeError,
    InvalidAPIKeyError,
    LLMError,
    ModelNotAvailableError,
    PermanentLLMError,
    RateLimitError,
    ProviderUnavailableError,
    RetryableLLMError,
)
from core.llm.request import LLMRequest, priority_for, STAGE_PRIORITY
from core.llm.types import LLMConfig, LLMResponse, Message
from core.llm.rate_limiter import RateLimiter, CredentialLimits, JobLimits
from core.llm.circuit_breaker import CircuitBreaker, CircuitState
from core.llm.gateway import LLMGateway, GatewayConfig, _estimate_tokens, _backoff
from core.llm.client import LLMClient, _derive_cred_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(api_key="sk-test", provider="openai", model="gpt-4o"):
    return LLMConfig(
        provider=provider,
        base_url="https://api.openai.com/v1",
        api_key=api_key,
        model=model,
    )


def _make_response(tokens_in=10, tokens_out=5):
    return LLMResponse(
        content="Test response",
        model="gpt-4o",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def _make_req(**kw):
    defaults = dict(
        job_id="job_123",
        agent_name="ExtractorAgent",
        credential_id="cred_abc",
        provider="openai",
        model="gpt-4o",
        messages=[Message(role="user", content="hello world")],
    )
    defaults.update(kw)
    return LLMRequest(**defaults)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class TestErrorTypes:
    def test_safe_dict_no_secrets(self):
        err = RateLimitError("rate limited", provider="openai", model="gpt-4o",
                             retry_after=30.0, request_id="req_1")
        d = err.safe_dict()
        assert d["code"] == "RATE_LIMITED"
        assert d["provider"] == "openai"
        assert d["retry_after_seconds"] == 30.0
        assert "sk-" not in str(d)

    def test_permanent_is_not_retryable(self):
        assert not isinstance(InvalidAPIKeyError("bad key"), RetryableLLMError)

    def test_rate_limit_is_retryable(self):
        assert isinstance(RateLimitError("429"), RetryableLLMError)

    def test_context_too_large_is_neither(self):
        e = ContextTooLargeError("too big")
        assert not isinstance(e, RetryableLLMError)
        assert not isinstance(e, PermanentLLMError)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class TestLLMRequest:
    def test_priority_for_synthesizer(self):
        assert priority_for("SynthesizerAgent") == 10

    def test_priority_for_unknown(self):
        assert priority_for("UnknownAgent") == 3

    def test_request_has_unique_id(self):
        r1 = LLMRequest()
        r2 = LLMRequest()
        assert r1.request_id != r2.request_id

    def test_request_no_plaintext_key(self):
        req = _make_req()
        # credential_id must not be a real key
        assert not req.credential_id.startswith("sk-")
        assert "Bearer" not in req.credential_id


# ---------------------------------------------------------------------------
# Token estimator
# ---------------------------------------------------------------------------

class TestTokenEstimator:
    def test_estimate_nonempty(self):
        msgs = [Message(role="user", content="a" * 400)]
        est = _estimate_tokens(msgs)
        assert est == 100

    def test_estimate_floor(self):
        assert _estimate_tokens([Message(role="user", content="")]) == 1


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------

class TestBackoff:
    def test_retry_after_dominates(self):
        b = _backoff(0, retry_after=45.0)
        assert b >= 45.0

    def test_exponential_growth(self):
        b0 = _backoff(0)
        b3 = _backoff(3)
        assert b3 > b0

    def test_bounded(self):
        b10 = _backoff(10)
        assert b10 <= 66.0   # max_backoff(64) + max_jitter(1.5) + margin


# ---------------------------------------------------------------------------
# Credential ID derivation
# ---------------------------------------------------------------------------

class TestCredentialId:
    def test_no_plaintext(self):
        cfg = _make_config(api_key="sk-super-secret-key")
        cid = _derive_cred_id(cfg)
        assert "sk-super-secret-key" not in cid
        assert cid.startswith("cred_")

    def test_same_key_same_id(self):
        cfg = _make_config(api_key="sk-abc")
        assert _derive_cred_id(cfg) == _derive_cred_id(cfg)

    def test_different_keys_different_ids(self):
        cfg1 = _make_config(api_key="sk-aaa")
        cfg2 = _make_config(api_key="sk-bbb")
        assert _derive_cred_id(cfg1) != _derive_cred_id(cfg2)


# ---------------------------------------------------------------------------
# Circuit Breaker (no Redis — in-memory mode)
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    @pytest.fixture
    def cb(self):
        return CircuitBreaker(
            redis_client=None,
            failure_threshold=3,
            half_open_after=0.01,  # tiny for fast tests
            success_threshold=2,
        )

    @pytest.mark.asyncio
    async def test_starts_closed(self, cb):
        assert not await cb.is_open("test_key")
        assert await cb.get_state("test_key") == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self, cb):
        key = "test_prov"
        for _ in range(3):
            await cb.record_failure(key)
        assert await cb.is_open(key)
        assert await cb.get_state(key) == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self, cb):
        key = "test_prov2"
        for _ in range(3):
            await cb.record_failure(key)
        assert await cb.is_open(key)
        await asyncio.sleep(0.02)   # past half_open_after
        # Next is_open call should transition to HALF_OPEN and return False
        assert not await cb.is_open(key)
        assert await cb.get_state(key) == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_probe_successes(self, cb):
        key = "test_prov3"
        for _ in range(3):
            await cb.record_failure(key)
        await asyncio.sleep(0.02)
        await cb.is_open(key)   # → HALF_OPEN
        await cb.record_success(key)
        await cb.record_success(key)
        assert await cb.get_state(key) == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, cb):
        key = "test_prov4"
        await cb.record_failure(key)
        await cb.record_failure(key)
        await cb.record_success(key)
        # Should not be open after only 2 failures + 1 success reset
        assert not await cb.is_open(key)


# ---------------------------------------------------------------------------
# Rate Limiter (no Redis)
# ---------------------------------------------------------------------------

class TestRateLimiterNoRedis:
    @pytest.fixture
    def rl(self):
        return RateLimiter(redis_client=None)

    @pytest.mark.asyncio
    async def test_passes_through_without_redis(self, rl):
        allowed, reason, token = await rl.reserve(
            credential_id="cred_x", provider="openai",
            job_id="job_1", estimated_tokens=100,
        )
        assert allowed
        assert reason == "ok"
        # Release should not error
        await rl.release(token, actual_tokens=80)

    @pytest.mark.asyncio
    async def test_cooldown_zero_without_redis(self, rl):
        await rl.set_cooldown("cred_x", 30)
        remaining = await rl.cooldown_remaining("cred_x")
        assert remaining == 0.0   # Redis is None, so always 0


# ---------------------------------------------------------------------------
# LLM Gateway — happy path
# ---------------------------------------------------------------------------

class TestGatewayHappyPath:
    @pytest.fixture
    def gateway(self):
        return LLMGateway(redis_client=None, config=GatewayConfig(max_retries=2))

    @pytest.mark.asyncio
    async def test_successful_call_returns_response(self, gateway):
        expected = _make_response()
        with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=expected)):
            result = await gateway.complete(_make_req(), _make_config())
        assert result.content == "Test response"

    @pytest.mark.asyncio
    async def test_tokens_not_logged_in_safe_event(self, gateway):
        events = []

        async def capture(e):
            events.append(e)

        gw = LLMGateway(redis_client=None, on_event=capture)
        with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=_make_response())):
            await gw.complete(_make_req(), _make_config())

        # No event should contain key material
        for ev in events:
            assert "sk-" not in str(ev)
            assert "api_key" not in str(ev).lower()


# ---------------------------------------------------------------------------
# LLM Gateway — retries and errors
# ---------------------------------------------------------------------------

class TestGatewayRetry:
    @pytest.fixture
    def gateway(self):
        return LLMGateway(redis_client=None, config=GatewayConfig(max_retries=3))

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self, gateway):
        calls = []

        async def flaky_provider(config, msgs, timeout):
            calls.append(len(calls))
            if len(calls) < 3:
                raise RateLimitError("429", provider="openai")
            return _make_response()

        with patch("core.llm.gateway._call_provider", new=flaky_provider):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await gateway.complete(_make_req(), _make_config())
        assert result.content == "Test response"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self, gateway):
        call_count = 0

        async def bad_key(config, msgs, timeout):
            nonlocal call_count
            call_count += 1
            raise InvalidAPIKeyError("bad key", provider="openai")

        with patch("core.llm.gateway._call_provider", new=bad_key):
            with pytest.raises(InvalidAPIKeyError):
                await gateway.complete(_make_req(), _make_config())

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_context_too_large_no_retry(self, gateway):
        count = 0

        async def too_big(config, msgs, timeout):
            nonlocal count
            count += 1
            raise ContextTooLargeError("too big")

        with patch("core.llm.gateway._call_provider", new=too_big):
            with pytest.raises(ContextTooLargeError):
                await gateway.complete(_make_req(), _make_config())

        assert count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self, gateway):
        async def always_429(config, msgs, timeout):
            raise RateLimitError("429", provider="openai", retry_after=0.001)

        with patch("core.llm.gateway._call_provider", new=always_429):
            with patch("asyncio.sleep", new=AsyncMock()):
                with pytest.raises(RateLimitError):
                    await gateway.complete(_make_req(), _make_config())


# ---------------------------------------------------------------------------
# LLM Gateway — circuit breaker integration
# ---------------------------------------------------------------------------

class TestGatewayCircuitBreaker:
    @pytest.mark.asyncio
    async def test_open_circuit_rejected_immediately(self):
        gw = LLMGateway(redis_client=None, config=GatewayConfig(
            max_retries=2, cb_failure_threshold=2
        ))
        req = _make_req(provider="openai", credential_id="cred_bad")
        cfg = _make_config()

        # Force open the provider circuit
        prov_key = gw._circuit.provider_key("openai")
        for _ in range(2):
            await gw._circuit.record_failure(prov_key)

        with pytest.raises(CircuitOpenError) as exc_info:
            with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=_make_response())):
                await gw.complete(req, cfg)

        assert exc_info.value.code == "CIRCUIT_OPEN"


# ---------------------------------------------------------------------------
# LLMClient integration
# ---------------------------------------------------------------------------

class TestLLMClientIntegration:
    @pytest.fixture
    def client(self):
        cfg = _make_config(api_key="sk-test-abc123")
        return LLMClient(cfg, job_id="job_456")

    @pytest.mark.asyncio
    async def test_complete_routes_through_gateway(self, client):
        expected = _make_response()
        with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=expected)):
            res = await client.complete([Message(role="user", content="hello")])
        assert res.content == "Test response"
        assert client.total_tokens_in == 10
        assert client.total_tokens_out == 5

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(self, client):
        expected = _make_response()
        with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=expected)) as mock_call:
            msgs = [Message(role="user", content="cached question")]
            await client.complete(msgs)
            await client.complete(msgs)
        # Provider called only once; second was cache hit
        assert mock_call.call_count == 1
        assert client.cache_hits == 1

    def test_credential_id_not_plaintext(self, client):
        assert "sk-test-abc123" not in client._credential_id
        assert client._credential_id.startswith("cred_")

    @pytest.mark.asyncio
    async def test_low_complexity_uses_alt_config(self):
        main = _make_config(model="gpt-4o")
        low = _make_config(model="gpt-4o-mini")
        client = LLMClient(main, low_complexity_config=low)

        captured_model = []

        async def capture_provider(config, msgs, timeout):
            captured_model.append(config.model)
            return _make_response()

        with patch("core.llm.gateway._call_provider", new=capture_provider):
            await client.complete([Message(role="user", content="q")], complexity="low")

        assert captured_model[0] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Error classification from RuntimeError messages (provider adapter shim)
# ---------------------------------------------------------------------------

class TestErrorClassification:
    @pytest.mark.asyncio
    async def test_rate_limit_classified(self):
        gw = LLMGateway(redis_client=None, config=GatewayConfig(max_retries=0))

        async def raises_runtime(config, msgs, timeout):
            raise RuntimeError("openai rate-limited the request (429).")

        with patch("core.llm.gateway._call_provider", new=raises_runtime):
            with pytest.raises(RateLimitError):
                await gw.complete(_make_req(), _make_config())

    @pytest.mark.asyncio
    async def test_invalid_key_classified(self):
        gw = LLMGateway(redis_client=None, config=GatewayConfig(max_retries=0))

        async def raises_runtime(config, msgs, timeout):
            raise RuntimeError("openai rejected API key / access denied (401).")

        with patch("core.llm.gateway._call_provider", new=raises_runtime):
            with pytest.raises(InvalidAPIKeyError):
                await gw.complete(_make_req(), _make_config())

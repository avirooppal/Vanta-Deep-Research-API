"""
Phase 3 tests — Credential Broker, local store, gateway resolution.
All tests are pure-Python; no real HTTP calls, no real Redis, no real Fernet.
Fernet encryption is real (uses test SECRET_KEY env).
"""
from __future__ import annotations

import asyncio
import os
import pytest

# Must set SECRET_KEY before importing encryption module
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32bytes!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from unittest.mock import AsyncMock, patch

from core.security.credentials import local_store
from core.security.credentials.types import CredentialMetadata, ResolvedCredential
from core.security.credentials import broker as cred_broker
from core.llm.types import LLMConfig, LLMResponse, Message
from core.llm.gateway import LLMGateway, GatewayConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(cred_id="cred_test123"):
    return CredentialMetadata(
        credential_id=cred_id,
        provider="openai",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
    )


def _make_response():
    return LLMResponse(content="broker test ok", model="gpt-4o", tokens_in=10, tokens_out=5)


# ---------------------------------------------------------------------------
# ResolvedCredential safety
# ---------------------------------------------------------------------------

class TestResolvedCredentialSafety:
    def test_repr_hides_key(self):
        rc = ResolvedCredential(
            credential_id="cred_abc",
            provider="openai",
            api_key="sk-super-secret",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
        r = repr(rc)
        assert "sk-super-secret" not in r
        assert "cred_abc" in r

    def test_metadata_safe_dict_no_key(self):
        meta = _make_meta()
        d = meta.safe_dict()
        assert "api_key" not in d
        assert d["provider"] == "openai"
        assert d["credential_id"] == "cred_test123"


# ---------------------------------------------------------------------------
# Local store: store → resolve → revoke
# ---------------------------------------------------------------------------

class TestLocalStore:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        """Isolate each test by clearing the in-memory store."""
        local_store._store.clear()
        yield
        local_store._store.clear()

    @pytest.mark.asyncio
    async def test_store_and_resolve(self):
        meta = _make_meta("cred_sr1")
        await local_store.store_credential("sk-test-key", meta)
        resolved = await local_store.resolve_secret("cred_sr1")
        assert resolved is not None
        assert resolved.api_key == "sk-test-key"
        assert resolved.provider == "openai"

    @pytest.mark.asyncio
    async def test_resolve_unknown_returns_none(self):
        result = await local_store.resolve_secret("cred_does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_blocks_resolve(self):
        meta = _make_meta("cred_rv1")
        await local_store.store_credential("sk-revoke-me", meta)
        await local_store.revoke_credential("cred_rv1")
        resolved = await local_store.resolve_secret("cred_rv1")
        assert resolved is None

    @pytest.mark.asyncio
    async def test_get_metadata(self):
        meta = _make_meta("cred_gm1")
        await local_store.store_credential("sk-any-key", meta)
        found = await local_store.get_metadata("cred_gm1")
        assert found is not None
        assert found.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_restore_from_encrypted_blob(self):
        """restore_credential stores without decryption."""
        from core.security.encryption import encrypt
        enc = encrypt("sk-restored-key")
        meta = _make_meta("cred_rest1")
        await local_store.restore_credential("cred_rest1", enc, meta)
        resolved = await local_store.resolve_secret("cred_rest1")
        assert resolved is not None
        assert resolved.api_key == "sk-restored-key"

    @pytest.mark.asyncio
    async def test_plaintext_not_in_store_values(self):
        """Verify the in-memory store holds only bytes (encrypted), not the raw str."""
        meta = _make_meta("cred_enc1")
        await local_store.store_credential("sk-should-be-encrypted", meta)
        encrypted_bytes, _ = local_store._store["cred_enc1"]
        assert b"sk-should-be-encrypted" not in encrypted_bytes

    @pytest.mark.asyncio
    async def test_concurrent_stores_isolated(self):
        """Multiple credentials stored concurrently don't cross-contaminate."""
        meta_a = _make_meta("cred_ca")
        meta_b = _make_meta("cred_cb")
        await asyncio.gather(
            local_store.store_credential("sk-key-a", meta_a),
            local_store.store_credential("sk-key-b", meta_b),
        )
        ra = await local_store.resolve_secret("cred_ca")
        rb = await local_store.resolve_secret("cred_cb")
        assert ra.api_key == "sk-key-a"
        assert rb.api_key == "sk-key-b"


# ---------------------------------------------------------------------------
# Broker public interface
# ---------------------------------------------------------------------------

class TestCredentialBroker:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        local_store._store.clear()
        yield
        local_store._store.clear()

    @pytest.mark.asyncio
    async def test_store_returns_cred_id(self):
        cid = await cred_broker.store(
            api_key="sk-byok",
            provider="openai",
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
        )
        assert cid.startswith("cred_")

    @pytest.mark.asyncio
    async def test_get_metadata_after_store(self):
        cid = await cred_broker.store("sk-meta-test", "openai", "gpt-4o", "https://api.openai.com/v1")
        meta = await cred_broker.get_metadata(cid)
        assert meta is not None
        assert meta.credential_id == cid
        assert meta.provider == "openai"

    @pytest.mark.asyncio
    async def test_revoke_via_broker(self):
        cid = await cred_broker.store("sk-revoke", "openai", "gpt-4o", "https://api.openai.com/v1")
        ok = await cred_broker.revoke(cid)
        assert ok
        resolved = await local_store.resolve_secret(cid)
        assert resolved is None

    @pytest.mark.asyncio
    async def test_broker_does_not_expose_resolve_secret(self):
        """resolve_secret must not be accessible as an attribute of the broker module."""
        assert not hasattr(cred_broker, "resolve_secret"), (
            "SECURITY VIOLATION: resolve_secret must not be exported from broker"
        )

    @pytest.mark.asyncio
    async def test_restore_from_encrypted_blob(self):
        from core.security.encryption import encrypt
        cid = "cred_restore_broker"
        enc = encrypt("sk-restored")
        await cred_broker.restore_from_encrypted_blob(
            cid, enc, "openai", "gpt-4o", "https://api.openai.com/v1"
        )
        resolved = await local_store.resolve_secret(cid)
        assert resolved is not None
        assert resolved.api_key == "sk-restored"


# ---------------------------------------------------------------------------
# Gateway credential resolution at outbound boundary
# ---------------------------------------------------------------------------

class TestGatewayCredentialResolution:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        local_store._store.clear()
        yield
        local_store._store.clear()

    @pytest.mark.asyncio
    async def test_gateway_resolves_from_broker(self):
        """Gateway uses broker-stored key, not LLMConfig.api_key."""
        from core.llm.request import LLMRequest

        meta = _make_meta("cred_gw1")
        await local_store.store_credential("sk-real-key", meta)

        gw = LLMGateway(redis_client=None, config=GatewayConfig(max_retries=0))
        captured_config = []

        async def capture_provider(cfg, msgs, timeout):
            captured_config.append(cfg)
            return _make_response()

        req = LLMRequest(
            job_id="job_gw",
            agent_name="ExtractorAgent",
            credential_id="cred_gw1",
            provider="openai",
            model="gpt-4o",
            messages=[Message(role="user", content="test")],
        )
        # LLMConfig has NO api_key — should be resolved from broker
        cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1",
                        api_key=None, model="gpt-4o")

        with patch("core.llm.gateway._call_provider", new=capture_provider):
            result = await gw.complete(req, cfg)

        assert result.content == "broker test ok"
        assert captured_config[0].api_key == "sk-real-key"

    @pytest.mark.asyncio
    async def test_gateway_falls_back_to_llm_config_when_no_broker_entry(self):
        """When no broker entry exists, gateway uses LLMConfig.api_key (Phase 1 compat)."""
        from core.llm.request import LLMRequest

        gw = LLMGateway(redis_client=None, config=GatewayConfig(max_retries=0))
        captured_config = []

        async def capture_provider(cfg, msgs, timeout):
            captured_config.append(cfg)
            return _make_response()

        req = LLMRequest(
            job_id="job_fallback",
            agent_name="SearchAgent",
            credential_id="cred_not_in_broker",
            provider="openai",
            model="gpt-4o",
            messages=[Message(role="user", content="fallback test")],
        )
        cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1",
                        api_key="sk-fallback-key", model="gpt-4o")

        with patch("core.llm.gateway._call_provider", new=capture_provider):
            result = await gw.complete(req, cfg)

        assert captured_config[0].api_key == "sk-fallback-key"

    @pytest.mark.asyncio
    async def test_gateway_does_not_log_key(self):
        """Events emitted by gateway must not contain the api_key."""
        from core.llm.request import LLMRequest

        meta = _make_meta("cred_log1")
        await local_store.store_credential("sk-must-not-log", meta)

        events = []

        async def capture_event(ev):
            events.append(ev)

        gw = LLMGateway(redis_client=None, on_event=capture_event)
        req = LLMRequest(
            credential_id="cred_log1",
            provider="openai",
            model="gpt-4o",
            messages=[Message(role="user", content="q")],
        )
        cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1",
                        api_key=None, model="gpt-4o")

        with patch("core.llm.gateway._call_provider", new=AsyncMock(return_value=_make_response())):
            await gw.complete(req, cfg)

        for ev in events:
            assert "sk-must-not-log" not in str(ev)
            assert "api_key" not in str(ev).lower()

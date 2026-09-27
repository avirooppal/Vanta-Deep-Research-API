"""
Encrypted local credential store for Vanta's Credential Broker.

Uses the existing Fernet key derived from SECRET_KEY.
Secrets are stored in-memory in an encrypted dict keyed by credential_id.
In production this backend should be replaced by HashiCorp Vault /
AWS Secrets Manager / GCP Secret Manager — the interface is identical.

Concurrency: asyncio-safe (single-process in-memory dict + asyncio.Lock).
Multi-process: each worker process has its own store; the API process
stores credentials and ARQ workers reconstruct from DB on job start.
Phase 3 migration keeps the encrypted blob in DB alongside credential_id.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from core.security.credentials.types import CredentialMetadata, ResolvedCredential
from core.security.encryption import encrypt, decrypt

logger = logging.getLogger(__name__)

# In-memory map: credential_id → (encrypted_key_bytes, CredentialMetadata)
_store: dict[str, tuple[bytes, CredentialMetadata]] = {}
_lock = asyncio.Lock()


async def store_credential(
    api_key: str,
    metadata: CredentialMetadata,
) -> str:
    """
    Encrypt and store the API key. Returns credential_id.
    The plaintext key is discarded after encryption.
    """
    encrypted = encrypt(api_key)
    async with _lock:
        _store[metadata.credential_id] = (encrypted, metadata)
    logger.info("Stored credential %s (provider=%s)", metadata.credential_id, metadata.provider)
    # Explicitly overwrite the string reference (best-effort; Python GC owns memory)
    api_key = "REDACTED"  # noqa: F841
    return metadata.credential_id


async def resolve_secret(credential_id: str) -> Optional[ResolvedCredential]:
    """
    Resolve the plaintext key for a given credential_id.

    ONLY callable by the LLM Gateway at the outbound boundary.
    Research agents must never call this directly.
    """
    async with _lock:
        entry = _store.get(credential_id)
    if not entry:
        return None
    encrypted_bytes, meta = entry
    if meta.revoked:
        logger.warning("Attempted to resolve revoked credential %s", credential_id)
        return None
    plaintext = decrypt(encrypted_bytes)
    return ResolvedCredential(
        credential_id=credential_id,
        provider=meta.provider,
        api_key=plaintext,
        model=meta.model,
        base_url=meta.base_url,
    )


async def revoke_credential(credential_id: str) -> bool:
    async with _lock:
        entry = _store.get(credential_id)
        if not entry:
            return False
        encrypted, meta = entry
        meta.revoked = True
        _store[credential_id] = (encrypted, meta)
    logger.info("Revoked credential %s", credential_id)
    return True


async def get_metadata(credential_id: str) -> Optional[CredentialMetadata]:
    async with _lock:
        entry = _store.get(credential_id)
    return entry[1] if entry else None


async def restore_credential(
    credential_id: str,
    encrypted_key_bytes: bytes,
    metadata: CredentialMetadata,
) -> None:
    """
    Restore a credential from persisted encrypted bytes (e.g. from DB on worker startup).
    The encrypted blob is never decrypted here — only stored.
    """
    async with _lock:
        _store[credential_id] = (encrypted_key_bytes, metadata)
    logger.debug("Restored credential %s into local store", credential_id)

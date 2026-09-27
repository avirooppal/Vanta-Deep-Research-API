"""
Vanta Credential Broker — public interface.

This is the ONLY module that research agents may import from
core.security.credentials. It exposes only:
  - store()        → credential_id (API layer calls this)
  - revoke()       → bool
  - get_metadata() → CredentialMetadata | None

resolve_for_service() is intentionally NOT exported here.
It lives in local_store and is called only from core.llm.gateway.

ACL enforcement:
  Phase 3: enforced by Python module boundary (agents have no import path to
  local_store.resolve_secret). Phase 6 will add process isolation.
"""
from __future__ import annotations

from typing import Optional

from core.security.credentials.types import CredentialMetadata
from core.security.credentials import local_store


async def store(
    api_key: str,
    provider: str,
    model: str,
    base_url: str,
    hint_max_rpm: int = 0,
    hint_max_tpm: int = 0,
    hint_max_concurrent: int = 2,
) -> str:
    """
    Store a BYOK API key securely.

    Returns an opaque credential_id.
    The plaintext key is encrypted immediately and discarded.
    Never call this from research agents.
    """
    cred_id = CredentialMetadata.new_id()
    meta = CredentialMetadata(
        credential_id=cred_id,
        provider=provider,
        model=model,
        base_url=base_url,
        hint_max_rpm=hint_max_rpm,
        hint_max_tpm=hint_max_tpm,
        hint_max_concurrent=hint_max_concurrent,
    )
    return await local_store.store_credential(api_key, meta)


async def revoke(credential_id: str) -> bool:
    return await local_store.revoke_credential(credential_id)


async def get_metadata(credential_id: str) -> Optional[CredentialMetadata]:
    return await local_store.get_metadata(credential_id)


async def restore_from_encrypted_blob(
    credential_id: str,
    encrypted_bytes: bytes,
    provider: str,
    model: str,
    base_url: str,
) -> None:
    """
    Restore a credential on worker startup from a DB-persisted encrypted blob.
    Avoids decrypting the key at startup — only stores encrypted form.
    """
    meta = CredentialMetadata(
        credential_id=credential_id,
        provider=provider,
        model=model,
        base_url=base_url,
    )
    await local_store.restore_credential(credential_id, encrypted_bytes, meta)

"""
Credential type definitions for Vanta's Credential Broker.
No secrets live here — only metadata about a stored credential.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CredentialMetadata:
    """Non-secret metadata about a stored API credential.

    This is safe to log, serialize, and pass to agents.
    The actual secret lives only in the encrypted store.
    """
    credential_id: str
    provider: str
    model: str
    base_url: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked: bool = False
    # Hint for rate limiter (0 = use global defaults)
    hint_max_rpm: int = 0
    hint_max_tpm: int = 0
    hint_max_concurrent: int = 2

    @classmethod
    def new_id(cls) -> str:
        return f"cred_{uuid.uuid4().hex[:20]}"

    def safe_dict(self) -> dict:
        """Safe-to-log representation — never contains the secret."""
        return {
            "credential_id": self.credential_id,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "created_at": self.created_at.isoformat(),
            "revoked": self.revoked,
        }


@dataclass
class ResolvedCredential:
    """
    Ephemeral secret resolved only at the outbound boundary (inside gateway).

    This object must NEVER be:
    - logged
    - serialized to JSON
    - stored in Redis
    - passed to any agent
    - returned from any API endpoint

    It exists only for the milliseconds between credential resolution
    and the HTTP call to the provider.
    """
    credential_id: str
    provider: str
    api_key: str        # plaintext — handle with extreme care
    model: str
    base_url: str

    def __repr__(self) -> str:
        # Prevent accidental logging of the key
        return f"ResolvedCredential(credential_id={self.credential_id!r}, provider={self.provider!r})"

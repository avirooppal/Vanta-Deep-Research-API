"""
Vanta Phase 5 — Provenance Metadata for Untrusted Content.

All fetched web pages, downloaded documents, and search snippets are tagged
with cryptographic and contextual provenance metadata.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.security.data_classification import DataLabel


@dataclass
class ProvenanceMetadata:
    """Cryptographic and origin metadata for an external content asset."""
    source_url: str
    source_type: str = "webpage"                     # "webpage" | "document" | "search_snippet" | "api"
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    job_id: Optional[str] = None
    content_hash: str = ""                           # SHA-256 hex digest of raw content
    trust_score: int = 50
    data_label: DataLabel = DataLabel.UNTRUSTED_EXTERNAL
    has_injection_signals: bool = False
    injection_signals: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        raw_text: str,
        source_url: str,
        job_id: Optional[str] = None,
        source_type: str = "webpage",
        trust_score: int = 50,
        injection_signals: Optional[list[str]] = None,
    ) -> ProvenanceMetadata:
        content_hash = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()
        signals = injection_signals or []
        return cls(
            source_url=source_url,
            source_type=source_type,
            job_id=job_id,
            content_hash=content_hash,
            trust_score=trust_score,
            data_label=DataLabel.UNTRUSTED_EXTERNAL,
            has_injection_signals=bool(signals),
            injection_signals=signals,
        )

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at,
            "job_id": self.job_id,
            "content_hash": self.content_hash,
            "trust_score": self.trust_score,
            "data_label": self.data_label.value if hasattr(self.data_label, "value") else str(self.data_label),
            "has_injection_signals": self.has_injection_signals,
            "injection_signals": self.injection_signals,
        }

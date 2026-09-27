"""
Vanta Phase 6 — Typed Agent Results & Degraded Completion Lifecycle.

Defines status types and container models for agent execution results.
Allows optional stages (e.g. secondary validation, contradiction analysis, citation verification)
to degrade gracefully with explicit warnings instead of aborting the entire research job.
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class AgentResultStatus(str, Enum):
    """Execution status for an individual agent stage."""
    SUCCESS = "SUCCESS"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    SKIPPED_OPTIONAL = "SKIPPED_OPTIONAL"


@dataclass
class AgentResult:
    """Standardized result returned by or wrapping agent execution."""
    status: AgentResultStatus
    agent_name: str
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    tokens_used: int = 0

    @classmethod
    def success(cls, agent_name: str, data: Any = None, tokens_used: int = 0) -> AgentResult:
        return cls(
            status=AgentResultStatus.SUCCESS,
            agent_name=agent_name,
            data=data,
            tokens_used=tokens_used,
        )

    @classmethod
    def skipped_optional(cls, agent_name: str, reason: str) -> AgentResult:
        return cls(
            status=AgentResultStatus.SKIPPED_OPTIONAL,
            agent_name=agent_name,
            warnings=[f"[{agent_name}] Skipped: {reason}"],
            error=reason,
        )

    @classmethod
    def retryable_failure(cls, agent_name: str, error: str) -> AgentResult:
        return cls(
            status=AgentResultStatus.RETRYABLE_FAILURE,
            agent_name=agent_name,
            error=error,
            warnings=[f"[{agent_name}] Transient error: {error}"],
        )

    @classmethod
    def permanent_failure(cls, agent_name: str, error: str) -> AgentResult:
        return cls(
            status=AgentResultStatus.PERMANENT_FAILURE,
            agent_name=agent_name,
            error=error,
            warnings=[f"[{agent_name}] Permanent failure: {error}"],
        )

    @property
    def is_success(self) -> bool:
        return self.status == AgentResultStatus.SUCCESS

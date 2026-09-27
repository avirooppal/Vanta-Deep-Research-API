"""
Typed LLM request object for Vanta's central LLM Gateway.

Agents build an LLMRequest and pass it to LLMGateway.complete().
The plaintext API key is NEVER placed in this object.
The gateway resolves the credential internally at the outbound boundary.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.llm.types import Message


# Stage priorities — higher = served first when capacity is scarce
STAGE_PRIORITY: dict[str, int] = {
    "SynthesizerAgent": 10,
    "CitationVerifierAgent": 9,
    "ContradictionAgent": 6,
    "ExtractorAgent": 5,
    "CoordinatorAgent": 5,
    "ValidatorAgent": 4,
    "SearchAgent": 3,
}

DEFAULT_PRIORITY = 3


def priority_for(agent_name: str) -> int:
    return STAGE_PRIORITY.get(agent_name, DEFAULT_PRIORITY)


@dataclass
class LLMRequest:
    """A fully-typed, gateway-routable LLM invocation.

    credential_id references a stored secret in the Credential Broker
    (future) or is used as the rate-limiter identity today.
    Never store a plaintext key here.
    """

    # Identity
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:16]}")
    job_id: Optional[str] = None
    agent_name: str = ""

    # Routing
    credential_id: str = ""          # opaque ID; never a raw key
    provider: str = "openai"
    model: str = "gpt-4o"

    # Payload
    messages: list[Message] = field(default_factory=list)
    temperature: float = 0.2
    max_output_tokens: Optional[int] = None

    # Token budget hints (estimated before call; reconciled after)
    estimated_input_tokens: int = 0
    estimated_total_tokens: int = 0

    # Scheduling
    priority: int = DEFAULT_PRIORITY
    deadline: Optional[datetime] = None          # absolute wall-clock deadline
    attempt: int = 0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Complexity hint for model-tier selection ("high" | "low")
    complexity: str = "high"

    # Timeout overrides (seconds; None → gateway default)
    timeout_override: Optional[float] = None

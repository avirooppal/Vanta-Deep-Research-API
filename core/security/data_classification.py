"""
Vanta Phase 5 — Data Classification & Information Flow Control.

Defines information classification labels and security invariants
governing what data may flow to LLMs, logs, storage, or external networks.

Core Design Principle:
- The model is NEVER the security authority.
- SECRET data is strictly blocked from LLM prompts, logs, and arbitrary network calls.
- UNTRUSTED_EXTERNAL data must never be treated as instruction authority.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from core.llm.errors import PolicyViolationError


class DataLabel(str, Enum):
    """Data sensitivity classification labels."""
    PUBLIC = "PUBLIC"
    UNTRUSTED_EXTERNAL = "UNTRUSTED_EXTERNAL"
    USER_PRIVATE = "USER_PRIVATE"
    SECRET = "SECRET"


class DataDestination(str, Enum):
    """Valid data destinations in the Vanta architecture."""
    LLM = "llm"
    INTERNET = "internet"
    LOGS = "logs"
    STORAGE = "storage"


def check_data_flow(
    label: DataLabel | str,
    destination: DataDestination | str,
    allow_private_to_llm: bool = True,
) -> bool:
    """
    Evaluate whether data with the given classification label is allowed
    to flow to the specified destination.

    Invariants:
      SECRET:
        - LLM: DENIED unconditionally. Secrets must never enter prompts.
        - LOGS: DENIED unconditionally. Secrets must never be logged.
        - INTERNET: DENIED unconditionally. Secrets cannot egress to arbitrary hosts.
        - STORAGE: ALLOWED (must be encrypted at rest via Broker).

      USER_PRIVATE:
        - LLM: ALLOWED if allow_private_to_llm=True (user approved provider).
        - INTERNET: DENIED by default (no data exfiltration).
        - LOGS: DENIED by default (privacy protection).
        - STORAGE: ALLOWED.

      UNTRUSTED_EXTERNAL:
        - LLM: ALLOWED ONLY under strict prompt-framing (evidence only, not instruction).
        - INTERNET: ALLOWED.
        - LOGS: ALLOWED (sanitized).
        - STORAGE: ALLOWED.

      PUBLIC:
        - Allowed to all destinations subject to network egress policy.
    """
    if isinstance(label, str):
        label = DataLabel(label)
    if isinstance(destination, str):
        destination = DataDestination(destination)

    if label == DataLabel.SECRET:
        if destination in (DataDestination.LLM, DataDestination.LOGS, DataDestination.INTERNET):
            return False
        return True  # STORAGE is allowed (encrypted)

    if label == DataLabel.USER_PRIVATE:
        if destination == DataDestination.LLM:
            return allow_private_to_llm
        if destination in (DataDestination.INTERNET, DataDestination.LOGS):
            return False
        return True

    if label == DataLabel.UNTRUSTED_EXTERNAL:
        return True

    if label == DataLabel.PUBLIC:
        return True

    return False


def assert_safe_for_llm(data: Any, label: DataLabel | str) -> None:
    """
    Guard function: raises PolicyViolationError if data with this label
    is forbidden from entering an LLM prompt.
    """
    if not check_data_flow(label, DataDestination.LLM):
        raise PolicyViolationError(
            f"Data classified as {label} cannot be sent to an LLM prompt.",
            provider="",
            model="",
        )


def assert_safe_for_logs(data: Any, label: DataLabel | str) -> None:
    """
    Guard function: raises PolicyViolationError if data with this label
    is forbidden from being written to system logs.
    """
    if not check_data_flow(label, DataDestination.LOGS):
        raise PolicyViolationError(
            f"Data classified as {label} cannot be written to logs.",
            provider="",
            model="",
        )

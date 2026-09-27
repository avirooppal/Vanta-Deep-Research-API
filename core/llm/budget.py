"""
ResearchBudget — token/cost/time budget for a single research job.

Tracks consumption across the full pipeline.
CRITICAL: reserves finalization tokens before exploration consumes them.

Usage in engine:
    budget = ResearchBudget.from_config(mode_config)
    state.budget = budget
    ...
    if budget.should_stop_exploring():
        break  # → finalization
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


# Estimated tokens per stage for finalization reserve
_SYNTH_RESERVE_TOKENS  = 8_000   # synthesis: heavy generation
_CITE_RESERVE_TOKENS   = 2_000   # citation verifier: lightweight
_FINALIZATION_RESERVE  = _SYNTH_RESERVE_TOKENS + _CITE_RESERVE_TOKENS


@dataclass
class ResearchBudget:
    # Hard limits (0 = unlimited)
    max_input_tokens:   int = 0
    max_output_tokens:  int = 0
    max_total_tokens:   int = 0
    max_requests:       int = 0
    max_cost_usd:       float = 0.0
    max_duration_s:     float = 0.0

    # Finalization reserve (tokens that must remain for synthesis + citation)
    finalization_reserve_tokens: int = _FINALIZATION_RESERVE

    # Consumed so far
    used_input_tokens:  int = 0
    used_output_tokens: int = 0
    used_requests:      int = 0
    estimated_cost_usd: float = 0.0

    _started_at: float = field(default_factory=time.monotonic, repr=False)

    # ------------------------------------------------------------------ #

    def record(self, tokens_in: int, tokens_out: int, cost_usd: float = 0.0):
        self.used_input_tokens  += tokens_in
        self.used_output_tokens += tokens_out
        self.used_requests      += 1
        self.estimated_cost_usd += cost_usd

    @property
    def used_total_tokens(self) -> int:
        return self.used_input_tokens + self.used_output_tokens

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._started_at

    # ------------------------------------------------------------------ #
    # Soft limit checks                                                   #
    # ------------------------------------------------------------------ #

    def _token_headroom(self) -> int:
        """Remaining tokens before hard limit, ignoring reserve."""
        if self.max_total_tokens <= 0:
            return 999_999_999
        return max(0, self.max_total_tokens - self.used_total_tokens)

    def headroom_after_reserve(self) -> int:
        """Tokens available for exploration (hard limit minus reserve)."""
        return max(0, self._token_headroom() - self.finalization_reserve_tokens)

    def should_stop_exploring(self) -> bool:
        """True when the budget is too low to safely allow another search round.

        Triggered when:
        - token headroom < finalization reserve
        - request count exhausted
        - wall-clock time exhausted
        """
        # Token check
        if self.max_total_tokens > 0 and self.headroom_after_reserve() <= 0:
            return True

        # Request check — leave room for at least 2 finalization calls
        if self.max_requests > 0 and self.used_requests >= self.max_requests - 2:
            return True

        # Duration check
        if self.max_duration_s > 0 and self.elapsed_s >= self.max_duration_s:
            return True

        return False

    def can_afford(self, estimated_tokens: int) -> bool:
        """True if estimated_tokens fit in the available headroom (with reserve)."""
        if self.max_total_tokens <= 0:
            return True
        return self.headroom_after_reserve() >= estimated_tokens

    def is_hard_exhausted(self) -> bool:
        """True when we must stop even finalization — absolute limit hit."""
        if self.max_total_tokens > 0 and self.used_total_tokens >= self.max_total_tokens:
            return True
        if self.max_requests > 0 and self.used_requests >= self.max_requests:
            return True
        return False

    # ------------------------------------------------------------------ #
    # Factory                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def unlimited(cls) -> "ResearchBudget":
        """No limits — used by default / quality mode."""
        return cls()

    @classmethod
    def from_env_or_default(cls, max_total_tokens: int = 0,
                            max_requests: int = 0,
                            max_duration_s: float = 0.0) -> "ResearchBudget":
        return cls(
            max_total_tokens=max_total_tokens,
            max_requests=max_requests,
            max_duration_s=max_duration_s,
        )

    # ------------------------------------------------------------------ #
    # Diagnostics (safe — no secrets)                                    #
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "used_input_tokens":    self.used_input_tokens,
            "used_output_tokens":   self.used_output_tokens,
            "used_total_tokens":    self.used_total_tokens,
            "used_requests":        self.used_requests,
            "elapsed_s":            round(self.elapsed_s, 1),
            "headroom_after_reserve": self.headroom_after_reserve(),
            "should_stop_exploring":  self.should_stop_exploring(),
        }

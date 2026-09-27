"""
Phase 2 tests — ResearchBudget, agent_name routing, budget integration.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from core.llm.budget import ResearchBudget, _FINALIZATION_RESERVE
from core.llm.types import LLMConfig, LLMResponse, Message
from core.llm.client import LLMClient
from core.llm.gateway import LLMGateway, GatewayConfig
from core.llm.request import priority_for


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(tokens_in=100, tokens_out=50):
    return LLMResponse(content="ok", model="gpt-4o", tokens_in=tokens_in, tokens_out=tokens_out)


def _make_client():
    cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1",
                    api_key="sk-test", model="gpt-4o")
    return LLMClient(cfg)


# ---------------------------------------------------------------------------
# ResearchBudget
# ---------------------------------------------------------------------------

class TestResearchBudget:
    def test_unlimited_never_stops(self):
        b = ResearchBudget.unlimited()
        b.record(1_000_000, 1_000_000)
        assert not b.should_stop_exploring()
        assert not b.is_hard_exhausted()

    def test_stops_when_reserve_threatened(self):
        b = ResearchBudget(max_total_tokens=20_000)
        # consume up to just past the reserve threshold
        used = 20_000 - _FINALIZATION_RESERVE + 1
        b.used_input_tokens = used
        assert b.should_stop_exploring()

    def test_does_not_stop_before_reserve_threatened(self):
        b = ResearchBudget(max_total_tokens=100_000)
        b.used_input_tokens = 1_000
        assert not b.should_stop_exploring()

    def test_headroom_after_reserve(self):
        b = ResearchBudget(max_total_tokens=50_000)
        b.used_input_tokens = 10_000
        expected = 50_000 - 10_000 - _FINALIZATION_RESERVE
        assert b.headroom_after_reserve() == expected

    def test_headroom_unlimited(self):
        b = ResearchBudget.unlimited()
        assert b.headroom_after_reserve() > 1_000_000

    def test_can_afford_within_headroom(self):
        b = ResearchBudget(max_total_tokens=50_000)
        assert b.can_afford(1_000)

    def test_cannot_afford_exceeds_headroom(self):
        b = ResearchBudget(max_total_tokens=11_000)
        # reserve=10000, headroom=1000, can't afford 2000
        b.used_input_tokens = 0
        assert not b.can_afford(2_000)

    def test_request_count_stop(self):
        b = ResearchBudget(max_requests=10)
        b.used_requests = 9  # 1 left, but need 2 for finalization
        assert b.should_stop_exploring()

    def test_record_accumulates(self):
        b = ResearchBudget.unlimited()
        b.record(100, 50)
        b.record(200, 100)
        assert b.used_input_tokens == 300
        assert b.used_output_tokens == 150
        assert b.used_requests == 2

    def test_hard_exhausted_on_token_limit(self):
        b = ResearchBudget(max_total_tokens=100)
        b.used_input_tokens = 100
        assert b.is_hard_exhausted()

    def test_safe_summary_no_secrets(self):
        b = ResearchBudget.unlimited()
        b.record(50, 25)
        s = b.summary()
        assert "used_total_tokens" in s
        assert s["used_total_tokens"] == 75
        assert "api_key" not in str(s)


# ---------------------------------------------------------------------------
# agent_name threads through to gateway (priority routing)
# ---------------------------------------------------------------------------

class TestAgentNameRouting:
    @pytest.mark.asyncio
    async def test_agent_name_sets_priority(self):
        cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1",
                        api_key="sk-test", model="gpt-4o")
        client = LLMClient(cfg)
        captured = []

        async def capture_req(req, llm_cfg):
            captured.append(req)
            return _make_response()

        gw = LLMGateway(redis_client=None)
        gw.complete = capture_req
        client._gateway = gw

        await client.complete(
            [Message(role="user", content="test")],
            agent_name="SynthesizerAgent",
        )
        assert captured[0].priority == priority_for("SynthesizerAgent")
        assert captured[0].agent_name == "SynthesizerAgent"

    @pytest.mark.asyncio
    async def test_low_priority_for_search(self):
        assert priority_for("SearchAgent") < priority_for("SynthesizerAgent")

    @pytest.mark.asyncio
    async def test_synthesizer_highest_priority(self):
        assert priority_for("SynthesizerAgent") >= priority_for("CitationVerifierAgent")
        assert priority_for("SynthesizerAgent") >= priority_for("ExtractorAgent")


# ---------------------------------------------------------------------------
# Budget auto-recording via LLMClient
# ---------------------------------------------------------------------------

class TestBudgetAutoRecord:
    @pytest.mark.asyncio
    async def test_budget_records_after_call(self):
        client = _make_client()
        budget = ResearchBudget.unlimited()
        client.attach_budget(budget)

        with patch("core.llm.gateway._call_provider",
                   new=AsyncMock(return_value=_make_response(tokens_in=200, tokens_out=80))):
            await client.complete([Message(role="user", content="hello")], agent_name="ExtractorAgent")

        assert budget.used_input_tokens == 200
        assert budget.used_output_tokens == 80
        assert budget.used_requests == 1

    @pytest.mark.asyncio
    async def test_budget_accumulates_across_calls(self):
        client = _make_client()
        budget = ResearchBudget.unlimited()
        client.attach_budget(budget)

        with patch("core.llm.gateway._call_provider",
                   new=AsyncMock(return_value=_make_response(tokens_in=100, tokens_out=50))):
            await client.complete([Message(role="user", content="q1")], agent_name="SearchAgent")
            # different content so no cache hit
            await client.complete([Message(role="user", content="q2")], agent_name="ValidatorAgent")

        assert budget.used_requests == 2
        assert budget.used_input_tokens == 200

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_double_record(self):
        client = _make_client()
        budget = ResearchBudget.unlimited()
        client.attach_budget(budget)

        msg = [Message(role="user", content="same question")]
        with patch("core.llm.gateway._call_provider",
                   new=AsyncMock(return_value=_make_response(tokens_in=100, tokens_out=50))):
            await client.complete(msg)
            await client.complete(msg)  # cache hit

        # Only one real call → one budget record
        assert budget.used_requests == 1

    @pytest.mark.asyncio
    async def test_no_budget_attached_is_fine(self):
        """Client without a budget should work normally."""
        client = _make_client()
        with patch("core.llm.gateway._call_provider",
                   new=AsyncMock(return_value=_make_response())):
            result = await client.complete([Message(role="user", content="hello")])
        assert result.content == "ok"


# ---------------------------------------------------------------------------
# Budget stop-exploring integration (simulated engine loop)
# ---------------------------------------------------------------------------

class TestBudgetEngineIntegration:
    def test_stop_exploring_blocks_additional_rounds(self):
        """Simulate engine loop checking budget before each round."""
        budget = ResearchBudget(max_total_tokens=12_000)
        # Consume everything except less than finalization reserve
        budget.used_input_tokens = 12_000 - _FINALIZATION_RESERVE + 500
        rounds_run = 0
        for _ in range(10):
            if budget.should_stop_exploring():
                break
            rounds_run += 1
            budget.record(100, 50)
        # Should have stopped at round 0
        assert rounds_run == 0

    def test_unlimited_budget_runs_all_rounds(self):
        budget = ResearchBudget.unlimited()
        rounds_run = 0
        for _ in range(5):
            if budget.should_stop_exploring():
                break
            rounds_run += 1
            budget.record(10_000, 5_000)
        assert rounds_run == 5

"""
Phase 6 tests — Degraded Completion, Typed AgentResult & Resilient Lifecycle.
Pure-Python; no network, no DB, no Redis.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.research.results import AgentResult, AgentResultStatus
from core.research.agents.synthesizer import ReportOutput
from core.research.state import ResearchState, Finding, ValidatedSource
from core.research.engine import run_research
from core.llm.types import LLMResponse, LLMConfig
from core.llm.gateway import LLMGateway, GatewayConfig
from core.llm.request import LLMRequest
from core.llm.errors import RateLimitError


# ---------------------------------------------------------------------------
# Typed AgentResult Tests
# ---------------------------------------------------------------------------

class TestTypedAgentResult:
    def test_agent_result_success(self):
        res = AgentResult.success("ExtractorAgent", data={"facts": "ok"}, tokens_used=120)
        assert res.status == AgentResultStatus.SUCCESS
        assert res.is_success is True
        assert res.agent_name == "ExtractorAgent"
        assert res.tokens_used == 120
        assert not res.warnings

    def test_agent_result_skipped_optional(self):
        res = AgentResult.skipped_optional("ValidatorAgent", "low priority domain")
        assert res.status == AgentResultStatus.SKIPPED_OPTIONAL
        assert res.is_success is False
        assert len(res.warnings) == 1
        assert "Skipped: low priority domain" in res.warnings[0]

    def test_agent_result_retryable_failure(self):
        res = AgentResult.retryable_failure("ContradictionAgent", "rate limit exceeded")
        assert res.status == AgentResultStatus.RETRYABLE_FAILURE
        assert res.error == "rate limit exceeded"
        assert "Transient error" in res.warnings[0]

    def test_agent_result_permanent_failure(self):
        res = AgentResult.permanent_failure("SynthesizerAgent", "context too large")
        assert res.status == AgentResultStatus.PERMANENT_FAILURE
        assert res.error == "context too large"
        assert "Permanent failure" in res.warnings[0]


# ---------------------------------------------------------------------------
# Degraded Engine Completion Tests
# ---------------------------------------------------------------------------

class TestEngineDegradedCompletion:
    @pytest.mark.asyncio
    async def test_synthesis_failure_falls_back_with_warnings(self):
        """When final synthesis raises an exception, the engine produces a fallback report and status completed_with_warnings."""
        mock_llm = AsyncMock()
        mock_llm.search_queries_issued = 0
        mock_llm.sources_fetched = 0
        mock_llm.total_tokens_in = 0
        mock_llm.total_tokens_out = 0
        mock_llm.attach_budget = MagicMock()

        # Mock coordinator to stop immediately to enter final report assembly
        with patch("core.research.engine._create_plan", return_value="Plan"), \
             patch("core.research.engine._classify_category", return_value="research"), \
             patch("core.research.engine.CoordinatorAgent.run", return_value="SYNTHESIZE"), \
             patch("core.research.engine.SynthesizerAgent.run", side_effect=RuntimeError("Synthesis model timeout")), \
             patch("core.research.engine.CitationVerifierAgent.run", side_effect=lambda state, rpt: rpt):

            # Inject a finding so fallback report can compile
            async def on_progress(_):
                pass

            # Pre-populate findings via a patched coordinator or state
            with patch("core.research.engine.ResearchState") as MockState:
                state_instance = MagicMock()
                state_instance.question = "Test question"
                state_instance.max_rounds = 1
                state_instance.current_round = 1
                state_instance.is_done = False
                state_instance.budget = None
                state_instance.evolving_report = "Evolving draft from rounds"
                state_instance.findings = [
                    Finding(url="https://a.com", title="A", facts="Fact 1", round_number=1, summary="Fact 1 summary")
                ]
                state_instance.warnings = []
                MockState.return_value = state_instance

                report = await run_research(
                    question="Test question",
                    llm=mock_llm,
                    searxng_url="http://test",
                    max_rounds=1,
                    on_progress=on_progress,
                )

            assert report.status == "completed_with_warnings"
            assert any("Synthesizer failed" in w for w in report.warnings)
            assert "Fact 1" in report.body_md

    @pytest.mark.asyncio
    async def test_citation_verifier_failure_completes_with_warnings(self):
        """When CitationVerifierAgent fails, report is returned with completed_with_warnings."""
        mock_llm = AsyncMock()
        mock_llm.search_queries_issued = 0
        mock_llm.sources_fetched = 0
        mock_llm.total_tokens_in = 0
        mock_llm.total_tokens_out = 0
        mock_llm.attach_budget = MagicMock()

        valid_report = ReportOutput(
            query="Test",
            summary="Summary",
            body_md="# Test Report",
            citations=[{"id": "src_1", "url": "https://a.com", "title": "A"}],
            status="completed",
        )

        with patch("core.research.engine._create_plan", return_value="Plan"), \
             patch("core.research.engine._classify_category", return_value="research"), \
             patch("core.research.engine.CoordinatorAgent.run", return_value="SYNTHESIZE"), \
             patch("core.research.engine.SynthesizerAgent.run", return_value=valid_report), \
             patch("core.research.engine.CitationVerifierAgent.run", side_effect=RuntimeError("Citation model down")):

            async def on_progress(_):
                pass

            with patch("core.research.engine.ResearchState") as MockState:
                state_instance = MagicMock()
                state_instance.question = "Test"
                state_instance.max_rounds = 1
                state_instance.current_round = 1
                state_instance.is_done = False
                state_instance.budget = None
                state_instance.evolving_report = "Evolving"
                state_instance.findings = [
                    Finding(url="https://a.com", title="A", facts="F", round_number=1)
                ]
                state_instance.warnings = []
                MockState.return_value = state_instance

                report = await run_research(
                    question="Test",
                    llm=mock_llm,
                    searxng_url="http://test",
                    max_rounds=1,
                    on_progress=on_progress,
                )

            assert report.status == "completed_with_warnings"
            assert any("Citation verification failed" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# SSE Events on Rate-Limit & Backoff
# ---------------------------------------------------------------------------

class TestSSEEvents:
    @pytest.mark.asyncio
    async def test_gateway_emits_llm_waiting_event(self):
        """Gateway emits structured llm_waiting event with retry_after and agent details."""
        events = []

        async def capture_event(ev: dict):
            events.append(ev)

        gw = LLMGateway(redis_client=None, config=GatewayConfig(max_retries=1), on_event=capture_event)
        req = LLMRequest(
            job_id="job_sse_test",
            agent_name="ExtractorAgent",
            credential_id="cred_test",
            provider="openai",
            model="gpt-4o",
            messages=[],
        )
        cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")

        with patch("core.llm.gateway._call_provider", side_effect=RateLimitError("Rate limit", retry_after=5.0)):
            with pytest.raises(RateLimitError):
                await gw.complete(req, cfg)

        waiting_events = [e for e in events if e.get("type") == "llm_waiting"]
        assert len(waiting_events) >= 1
        ev = waiting_events[0]
        assert ev["reason"] == "rate_limit"
        assert ev["agent"] == "ExtractorAgent"
        assert ev["provider"] == "openai"
        assert ev["retry_after_seconds"] >= 5.0

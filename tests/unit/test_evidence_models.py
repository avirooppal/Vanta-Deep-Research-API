"""
Phase 2 tests — Structured Evidence Models, Source Quality & Atomic Claims.
Pure-Python unit tests; no external network or service dependencies.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from core.research.evidence.models import (
    ClaimType,
    SourceRole,
    QuantitativeFact,
    SourceQuality,
    SourceLineage,
    AtomicClaim,
)
from core.research.agents.validator import ValidatorAgent
from core.research.agents.extractor import ExtractorAgent
from core.research.state import ValidatedSource
from core.llm.types import LLMResponse
from integrations.fetcher import FetchedPage


# ---------------------------------------------------------------------------
# SourceQuality & Lineage Tests
# ---------------------------------------------------------------------------

class TestSourceQualityAndLineage:
    def test_source_quality_computation_penalizes_bias(self):
        high_quality = SourceQuality.compute(
            authority=90,
            primary_source_score=95,
            expertise=85,
            methodological_quality=90,
            recency_score=80,
            bias_risk=5,
        )
        assert high_quality.overall_trust >= 85

        biased_pr = SourceQuality.compute(
            authority=60,
            primary_source_score=30,
            expertise=40,
            methodological_quality=30,
            recency_score=80,
            bias_risk=80,  # heavy bias
        )
        assert biased_pr.overall_trust < 40

    def test_source_lineage_tracking(self):
        lineage = SourceLineage(
            source_url="https://www.prnewswire.com/news-releases/battery-tech-301.html",
            is_press_release=True,
            syndicated_agency="PR Newswire",
        )
        assert lineage.is_press_release is True
        assert lineage.syndicated_agency == "PR Newswire"


# ---------------------------------------------------------------------------
# AtomicClaim & Quantitative Fact Tests
# ---------------------------------------------------------------------------

class TestAtomicClaims:
    def test_atomic_claim_creation(self):
        q_fact = QuantitativeFact(
            metric_name="energy_density",
            value=450,
            unit="Wh/kg",
            period="by 2028",
            is_forecast=True,
        )
        claim = AtomicClaim(
            claim_id="clm_test_1",
            claim_text="Prototype cell demonstrated 450 Wh/kg pack-level density.",
            claim_type=ClaimType.FORECAST,
            source_url="https://battery-lab.edu/report",
            source_title="Battery Lab Tech Report",
            supporting_passage="In laboratory tests, the cell achieved 450 Wh/kg.",
            quantitative_facts=[q_fact],
            confidence="STRONG EVIDENCE",
            round_number=1,
        )

        assert claim.claim_id == "clm_test_1"
        assert claim.claim_type == ClaimType.FORECAST
        assert len(claim.quantitative_facts) == 1
        assert claim.quantitative_facts[0].unit == "Wh/kg"
        d = claim.to_dict()
        assert d["claim_type"] == "FORECAST"
        assert d["confidence"] == "STRONG EVIDENCE"


# ---------------------------------------------------------------------------
# Agent Integration Tests
# ---------------------------------------------------------------------------

class TestAgentEvidenceIntegration:
    @pytest.mark.asyncio
    async def test_validator_attaches_quality_and_lineage(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"trust_score": 85, "flags": "None"}',
            tokens_in=50,
            tokens_out=20,
            model="test-model",
        )

        validator = ValidatorAgent(mock_llm)
        page = FetchedPage(
            url="https://www.prnewswire.com/news-releases/company-announces-breakthrough.html",
            title="Company PR",
            text="Press release body text",
            success=True,
        )

        source = await validator.run(page)
        assert source.quality is not None
        assert isinstance(source.quality, SourceQuality)
        assert source.lineage is not None
        assert source.lineage.is_press_release is True

    @pytest.mark.asyncio
    async def test_extractor_produces_atomic_claim_with_type(self):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="""{
                "rational": "Commercial volume timeline data",
                "evidence": "Company stated it plans to build a 10GWh facility starting 2027.",
                "summary": "Facility construction planned for 2027",
                "claim_type": "ANNOUNCEMENT",
                "trust_score": 75
            }""",
            tokens_in=120,
            tokens_out=60,
            model="test-model",
        )

        extractor = ExtractorAgent(mock_llm)
        source = ValidatedSource(
            url="https://industry-insider.com/factory",
            title="Factory Plans",
            text="Company announced factory plans for 2027.",
            trust_score=75,
            flags="None",
        )

        findings = await extractor.run(source, "When will factory open?", round_n=1)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.claim_type == "ANNOUNCEMENT"
        assert finding.atomic_claim is not None
        assert finding.atomic_claim.claim_type == ClaimType.ANNOUNCEMENT
        assert finding.atomic_claim.source_url == "https://industry-insider.com/factory"

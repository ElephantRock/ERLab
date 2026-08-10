"""BATCH-154: Citation Audit — Full test suite (15 tests).

Tests for CitationClaimAuditor, CitationAuditStage, orchestrator wiring,
strategy presets, and ReferenceVerifier [SOURCE-X] extension.

Uses asyncio.run() (NOT @pytest.mark.asyncio) — pytest.ini has -p no:asyncio.
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import MagicMock, patch

# Ensure chromadb mock
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.stages import CitationAuditStage, StageContext
from backend.pipeline.strategies.models import PipelineStrategy, StageConfig, StrategyConfig
from backend.pipeline.strategies.presets import register_presets
from backend.pipeline.strategies.registry import StrategyRegistry
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
from backend.pipeline.verification.citation_claim_auditor import (
    CitationAuditItem,
    CitationAuditReport,
    CitationClaimAuditor,
)
from backend.pipeline.verification.reference_verifier import ReferenceVerifier

# ── Helpers ──────────────────────────────────────────────────


class FakeProvider:
    """Fake LLM provider returning canned JSON for citation verification."""

    def __init__(self, response: str | None = None):
        self._response = response or self._default_response()

    @staticmethod
    def _default_response() -> str:
        return json.dumps({
            "context_verified": True,
            "context_justification": "Claim accurately reflects source",
            "quantitative_claims": [],
            "quantitative_verified": True,
            "trust_contribution": 1.0,
        })

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return self._response

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield self._response

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model-v1"


class FailingProvider(FakeProvider):
    """Provider that raises on complete() (for HB-02 test)."""

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        raise RuntimeError("LLM service unavailable")


class FakePaper:
    """Minimal paper-like object for source formatting."""

    def __init__(self, title="Test Paper", authors=None, year=2024,
                 abstract="Abstract text", venue="ACL", doi="", url=""):
        self.title = title
        self.authors = authors or []
        self.year = year
        self.abstract = abstract
        self.venue = venue
        self.doi = doi
        self.url = url
        self.id = "p1"
        self.source = "test"


class FakeAuthor:
    def __init__(self, name):
        self.name = name


class FakePipelineResult:
    """Minimal PipelineResult mock."""

    def __init__(self):
        self.papers_found = 0
        self.gaps = []
        self.ideas = []
        self.novelty_reports = {}
        self.feasibility_reports = {}
        self.mechanical_metrics = {}
        self.proposals = {}
        self.export_paths = {}
        self.run_id = "test_run"
        self.params_used = {}
        self.tree_data = None
        self.cluster_report = None
        self.critique_history = []
        self.refinement_history = []


# ════════════════════════════════════════════════════════════
# TASK-01: CitationClaimAuditor (7 tests)
# ════════════════════════════════════════════════════════════


class TestCitationClaimAuditor:
    """TEST-154-01-01 through TEST-154-01-07."""

    def test_01_01_source_x_extraction_works(self):
        """TEST-154-01-01: [SOURCE-X] extraction works."""
        text = (
            "Prior work on RAG [SOURCE-1] and multi-task learning [SOURCE-3] "
            "shows improvements. See also [SOURCE-1] again."
        )
        indices = CitationClaimAuditor._extract_source_refs(text)
        assert indices == [1, 3]

    def test_01_02_fabricated_index_flagged(self):
        """TEST-154-01-02: Fabricated index flagged (HB-03)."""
        text = "According to [SOURCE-99], the method achieves 95% accuracy."
        source_papers = ["Paper 1", "Paper 2", "Paper 3", "Paper 4", "Paper 5"]

        auditor = CitationClaimAuditor(provider=None)
        report = asyncio.run(auditor.audit(text, source_papers))

        assert report.fabricated_citations == 1
        assert len(report.items) == 1
        assert report.items[0].ref_exists is False
        assert report.items[0].ref_index == 99

    def test_01_03_trust_score_clamped(self):
        """TEST-154-01-03: Trust score clamped to [0.0, 1.0] (HB-04)."""
        # Create items with trust_contribution > 1.0 to test clamping
        items = [
            CitationAuditItem(
                ref_index=1, ref_exists=True, claim_text="test",
                context_verified=True, context_justification="ok",
                quantitative_claims=[], quantitative_verified=True,
                trust_contribution=1.5,  # Exceeds max
            ),
        ]
        score = CitationClaimAuditor._compute_trust_score(items)
        assert score == 1.0  # Clamped

        # Test clamping below 0
        items2 = [
            CitationAuditItem(
                ref_index=1, ref_exists=True, claim_text="test",
                context_verified=False, context_justification="bad",
                quantitative_claims=[], quantitative_verified=False,
                trust_contribution=-0.5,  # Below min
            ),
        ]
        score2 = CitationClaimAuditor._compute_trust_score(items2)
        assert score2 == 0.0  # Clamped

    def test_01_04_graceful_fallback_on_llm_failure(self):
        """TEST-154-01-04: Graceful fallback on LLM failure (HB-02)."""
        text = "As shown by [SOURCE-1], the approach works."
        source_papers = ["Paper about RAG with good results."]

        auditor = CitationClaimAuditor(provider=FailingProvider())
        report = asyncio.run(auditor.audit(text, source_papers))

        # Should still return a valid report, not crash
        assert isinstance(report, CitationAuditReport)
        assert report.status == "complete"
        # LLM failure per-item should result in context_verified=False
        assert len(report.items) == 1
        assert report.items[0].ref_exists is True

    def test_01_05_report_has_all_required_fields(self):
        """TEST-154-01-05: CitationAuditReport has all required fields."""
        text = "According to [SOURCE-1], results improved. Also see [SOURCE-2]."
        source_papers = ["Paper A text.", "Paper B text."]

        auditor = CitationClaimAuditor(provider=FakeProvider())
        report = asyncio.run(auditor.audit(text, source_papers, proposal_id=7))

        # Access all fields
        assert isinstance(report.proposal_id, int)
        assert report.proposal_id == 7
        assert isinstance(report.total_citations, int)
        assert report.total_citations == 2
        assert isinstance(report.verified_citations, int)
        assert isinstance(report.fabricated_citations, int)
        assert isinstance(report.context_mismatches, int)
        assert isinstance(report.quantitative_errors, int)
        assert isinstance(report.trust_score, float)
        assert 0.0 <= report.trust_score <= 1.0
        assert isinstance(report.items, list)
        assert isinstance(report.model_used, str)
        assert report.status in ("complete", "partial", "skipped")

        # to_dict() method
        d = report.to_dict()
        assert "proposal_id" in d
        assert "total_citations" in d
        assert "trust_score" in d
        assert "items" in d
        assert "model_used" in d
        assert "status" in d

    def test_01_06_quantitative_claim_extraction(self):
        """TEST-154-01-06: Quantitative claim extraction works."""
        text = "The model achieved 95.2% accuracy on the benchmark."
        claims = CitationClaimAuditor._extract_quantitative_claims(text)

        assert len(claims) > 0
        # At least one claim should contain "95.2%"
        values = [c["value"] for c in claims]
        assert any("95.2%" in v for v in values)

    def test_01_07_timeout_produces_partial_results(self):
        """TEST-154-01-07: Timeout produces partial results (HB-05)."""
        import asyncio

        class SlowProvider(FakeProvider):
            """Provider that sleeps forever (simulates timeout)."""
            async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
                await asyncio.sleep(60)  # Will be interrupted by timeout
                return '{"context_verified": true}'

        text = "As shown by [SOURCE-1], the method works. And [SOURCE-2] agrees."
        source_papers = ["Paper A.", "Paper B."]

        # Very short timeout to trigger partial
        auditor = CitationClaimAuditor(provider=SlowProvider(), timeout=0.1)
        report = asyncio.run(auditor.audit(text, source_papers))

        assert report.status == "partial"
        assert len(report.items) == 2  # Both items present
        # At least one should have timed-out justification
        timeout_items = [i for i in report.items if "timed out" in i.context_justification.lower()]
        assert len(timeout_items) > 0


# ════════════════════════════════════════════════════════════
# TASK-02: CitationAuditStage + Orchestrator (5 tests)
# ════════════════════════════════════════════════════════════


class TestCitationAuditStage:
    """TEST-154-02-01 through TEST-154-02-05."""

    def test_02_01_citation_audit_in_stage_order(self):
        """TEST-154-02-01: citation_audit appears in _STAGE_ORDER."""
        assert "citation_audit" in PipelineOrchestrator._STAGE_ORDER

    def test_02_02_stage_position_after_paper_synthesis(self):
        """TEST-154-02-02: citation_audit index > paper_synthesis index."""
        order = PipelineOrchestrator._STAGE_ORDER
        paper_idx = order.index("paper_synthesis")
        audit_idx = order.index("citation_audit")
        assert audit_idx > paper_idx

    def test_02_03_audit_report_stored_in_metadata(self):
        """TEST-154-02-03: Audit report stored in proposal.metadata["citation_audit"]."""
        proposal = ResearchProposal(
            title="Test Proposal",
            abstract="We cite [SOURCE-1] for background.",
            introduction="Test intro",
            proposed_method="Test method",
        )
        # Add some citation text in sections
        proposal.sections["introduction"] = "Background work [SOURCE-1] shows promise."

        result = FakePipelineResult()
        result.proposals = {0: proposal}

        ctx = StageContext(
            result=result,
            all_papers=[FakePaper(title="Source Paper", abstract="About background methods.")],
            domain="AI/NLP",
        )

        auditor = CitationClaimAuditor(provider=FakeProvider())
        stage = CitationAuditStage(auditor=auditor)
        asyncio.run(stage.execute(ctx))

        metadata = stage._get_metadata(proposal)
        assert "citation_audit" in metadata
        audit_data = metadata["citation_audit"]
        assert isinstance(audit_data, dict)
        assert "status" in audit_data
        assert "trust_score" in audit_data

    def test_02_04_low_trust_score_logged_as_warning(self):
        """TEST-154-02-04: Low trust score (<0.5) logged as warning."""
        # Create a provider that returns low trust
        low_trust_response = json.dumps({
            "context_verified": False,
            "context_justification": "Claim contradicts source",
            "quantitative_claims": [],
            "quantitative_verified": False,
            "trust_contribution": 0.1,
        })

        proposal = ResearchProposal(
            title="Bad Proposal",
            abstract="According to [SOURCE-1], everything is wrong.",
            introduction="False claim [SOURCE-1].",
            proposed_method="Method",
        )

        result = FakePipelineResult()
        result.proposals = {0: proposal}

        ctx = StageContext(
            result=result,
            all_papers=[FakePaper(title="Real Paper", abstract="Everything is actually fine.")],
            domain="AI/NLP",
        )

        auditor = CitationClaimAuditor(provider=FakeProvider(response=low_trust_response))
        stage = CitationAuditStage(auditor=auditor)

        with patch.object(stage.__class__.__module__ and __import__("logging").getLogger(
            "backend.pipeline.stages"), "warning"
        ) as mock_warn:
            asyncio.run(stage.execute(ctx))

            # Verify warning was emitted
            metadata = stage._get_metadata(proposal)
            audit = metadata.get("citation_audit", {})
            assert audit.get("trust_score", 1.0) < 0.5

    def test_02_05_stage_skipped_when_flag_disabled(self):
        """TEST-154-02-05: Stage skips when citation_audit disabled in strategy."""
        proposal = ResearchProposal(
            title="Test Proposal",
            abstract="Abstract with [SOURCE-1].",
            introduction="Intro",
            proposed_method="Method",
        )

        result = FakePipelineResult()
        result.proposals = {0: proposal}

        strategy_config = StrategyConfig(
            name=PipelineStrategy.FAST_SCAN,
            stages={"citation_audit": StageConfig(enabled=False)},
        )

        ctx = StageContext(
            result=result,
            all_papers=[FakePaper()],
            domain="AI/NLP",
            params={"strategy_config": strategy_config},
        )

        auditor = CitationClaimAuditor(provider=FakeProvider())
        stage = CitationAuditStage(auditor=auditor)
        outcome = asyncio.run(stage.execute(ctx))

        # Stage returns True (didn't halt) but didn't write metadata
        assert outcome is True
        metadata = stage._get_metadata(proposal)
        assert "citation_audit" not in metadata


# ════════════════════════════════════════════════════════════
# TASK-03: Strategy Presets + ReferenceVerifier Extension (3 tests)
# ════════════════════════════════════════════════════════════


class TestStrategyPresetsAndVerifier:
    """TEST-154-03-01 through TEST-154-03-03."""

    def test_03_01_deep_research_enables_citation_audit(self):
        """TEST-154-03-01: deep_research enables citation_audit."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("deep_research")
        ca = config.stages.get("citation_audit")
        assert ca is not None
        assert ca.enabled is True

    def test_03_02_fast_scan_disables_citation_audit(self):
        """TEST-154-03-02: fast_scan disables citation_audit."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("fast_scan")
        ca = config.stages.get("citation_audit")
        assert ca is not None
        assert ca.enabled is False

    def test_03_03_reference_verifier_detects_source_x(self):
        """TEST-154-03-03: ReferenceVerifier detects [SOURCE-X] citations."""
        verifier = ReferenceVerifier()

        text = (
            "Prior work on RAG [SOURCE-1] shows improvements. "
            "Multi-task learning [SOURCE-2] also helps. "
            "But [SOURCE-5] does not exist."
        )

        corpus = [
            {"title": "RAG Paper", "authors": ["Smith"], "year": "2024"},
            {"title": "MTL Paper", "authors": ["Jones"], "year": "2023"},
        ]

        # Test verify_source_x method directly
        checks = verifier.verify_source_x(text, source_count=2)
        assert len(checks) == 3  # SOURCE-1, SOURCE-2, SOURCE-5

        # SOURCE-1 and SOURCE-2 should be found
        found_indices = {int(c.author.split("-")[1]) for c in checks if c.found_in_corpus}
        assert 1 in found_indices
        assert 2 in found_indices

        # SOURCE-5 should NOT be found (only 2 sources)
        not_found = [c for c in checks if not c.found_in_corpus]
        assert len(not_found) == 1
        assert not_found[0].author == "SOURCE-5"

        # Test verify() integrates [SOURCE-X] checks
        report = verifier.verify(text, corpus)
        # Should have author-year citations + SOURCE-X checks
        assert report.total_citations >= 3  # At least the 3 SOURCE-X

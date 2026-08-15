"""BATCH-153: Paper Synthesis — Full test suite (21 tests).

Tests for PaperSynthesizer, PaperSynthesisStage, venue templates,
LatexExporter venue support, LaTeX export API, and strategy presets.

Uses asyncio.run() (NOT @pytest.mark.asyncio) — pytest.ini has -p no:asyncio.
"""

from __future__ import annotations

import asyncio
import re
import sys
from unittest.mock import MagicMock, patch

# Ensure chromadb mock
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.export.venue_templates import (
    IEEE_TEMPLATE,
    VENUE_TEMPLATES,
)
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.stages import PaperSynthesisStage, StageContext
from backend.pipeline.strategies.models import PipelineStrategy, StageConfig
from backend.pipeline.strategies.presets import register_presets
from backend.pipeline.strategies.registry import StrategyRegistry
from backend.pipeline.synthesis.paper_synthesizer import (
    PaperSynthesisResult,
    PaperSynthesizer,
)
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal


class FakeProvider:
    """Fake LLM provider returning a canned academic paper."""

    def __init__(self, response: str | None = None):
        self._response = response or self._default_response()
        self._call_log: list[dict] = []

    @staticmethod
    def _default_response() -> str:
        # Phase 7 fix: unified synthesis service rejects results < 200 words.
        # Expanded response to exceed the 200-word minimum.
        return (
            "## Abstract\n\n"
            "This paper proposes a novel approach to automated research synthesis "
            "combining retrieval-augmented generation with structured attention. "
            "We evaluate on standard benchmarks and show improvements "
            "over existing baselines in accuracy and efficiency. Our framework "
            "integrates dense retrieval with a transformer-based generator that "
            "attends over retrieved passages at every decoding step.\n\n"
            "## Introduction\n\n"
            "Recent advances in natural language processing have opened new "
            "possibilities for automated research. However, existing approaches "
            "struggle with factual consistency and domain adaptation. In this "
            "work we propose a novel framework that addresses these limitations "
            "through retrieval mechanisms and structured generation. We argue "
            "that grounding generation in retrieved evidence reduces hallucination "
            "while maintaining fluency and coherence across diverse domains.\n\n"
            "## Related Work\n\n"
            "Prior work has explored retrieval-augmented generation [SOURCE-1] "
            "and multi-task learning [SOURCE-2]. Our approach differs by "
            "incorporating structured attention over retrieved passages.\n\n"
            "## Methodology\n\n"
            "We propose $P(d|q)$ as the retrieval probability and "
            "$P(y|d,q)$ as the generation probability. The fusion layer "
            "computes attention scores between decoder hidden states.\n\n"
            "## Experimental Design\n\n"
            "We evaluate on SQuAD, Natural Questions, and TriviaQA. "
            "Baselines include RAG and RETRO. Metrics include EM and F1.\n\n"
            "## Expected Results\n\n"
            "We expect 15% improvement in factual accuracy over baselines.\n\n"
            "## Discussion\n\n"
            "Limitations include domain-specific retrieval quality.\n\n"
            "## Conclusion\n\n"
            "We presented a novel framework for grounded generation."
        )

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._call_log.append({"method": "complete", "messages": messages})
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
        self.experiments = {}
        self.result_markers = {}


# ════════════════════════════════════════════════════════════
# TASK-01: PaperSynthesizer (5 tests)
# ════════════════════════════════════════════════════════════


class TestPaperSynthesizer:
    """TEST-153-01-01 through TEST-153-01-05."""

    def test_01_01_returns_result_with_all_fields(self):
        """TEST-153-01-01: synthesize returns PaperSynthesisResult with all fields."""
        provider = FakeProvider()
        synthesizer = PaperSynthesizer(provider)

        result = asyncio.run(synthesizer.synthesize(
            proposal_text="# Test Proposal\nWe propose a novel method.",
            source_papers=["[SOURCE-1] Smith (2024). Test Paper. ACL."],
            domain="AI/NLP",
            venue="Generic",
            proposal_id=42,
        ))

        assert result is not None
        assert isinstance(result, PaperSynthesisResult)
        assert result.proposal_id == 42
        assert isinstance(result.paper_markdown, str)
        assert len(result.paper_markdown) > 0
        assert isinstance(result.word_count, int)
        assert result.word_count > 0
        assert result.venue == "Generic"
        assert result.model_used == "fake-model-v1"
        assert result.source_count == 1

    def test_01_02_prompt_contains_academic_structure(self):
        """TEST-153-01-02: System prompt contains academic structure instructions."""
        provider = FakeProvider()
        synthesizer = PaperSynthesizer(provider)

        prompt = synthesizer._system_prompt
        assert "Abstract" in prompt
        assert "Introduction" in prompt
        assert "Related Work" in prompt
        assert "Methodology" in prompt

    def test_01_03_citation_policy_in_prompt(self):
        """TEST-153-01-03: Prompt contains [SOURCE-X] citation policy."""
        provider = FakeProvider()
        synthesizer = PaperSynthesizer(provider)

        prompt = synthesizer._system_prompt
        assert "[SOURCE-X]" in prompt
        assert "closed-book" in prompt.lower() or "CLOSED-BOOK" in prompt

    def test_01_04_graceful_fallback_on_llm_failure(self):
        """TEST-153-01-04: Returns None on LLM failure (HB-02)."""
        provider = FailingProvider()
        synthesizer = PaperSynthesizer(provider)

        result = asyncio.run(synthesizer.synthesize(
            proposal_text="Test proposal",
            source_papers=["[SOURCE-1] Paper"],
            domain="AI/NLP",
        ))

        assert result is None

    def test_01_05_word_count_computed_correctly(self):
        """TEST-153-01-05: Word count matches actual word count."""
        custom_response = "This is exactly ten words in the paper output."
        provider = FakeProvider(response=custom_response)
        synthesizer = PaperSynthesizer(provider)

        result = asyncio.run(synthesizer.synthesize(
            proposal_text="Test",
            source_papers=[],
            domain="AI/NLP",
        ))

        assert result is not None
        expected_count = len(custom_response.split())
        assert result.word_count == expected_count


# ════════════════════════════════════════════════════════════
# TASK-02: PaperSynthesisStage + Venue Templates (6 tests)
# ════════════════════════════════════════════════════════════


class TestPaperSynthesisStage:
    """TEST-153-02-01 through TEST-153-02-06."""

    def test_02_01_paper_synthesis_in_stage_order(self):
        """TEST-153-02-01: paper_synthesis appears in _STAGE_ORDER."""
        assert "paper_synthesis" in PipelineOrchestrator._STAGE_ORDER

    def test_02_02_stage_position_after_adversarial_review(self):
        """TEST-153-02-02: paper_synthesis index > adversarial_review index."""
        order = PipelineOrchestrator._STAGE_ORDER
        adv_idx = order.index("adversarial_review")
        paper_idx = order.index("paper_synthesis")
        assert paper_idx > adv_idx

    def test_02_03_venue_template_has_four_presets(self):
        """TEST-153-02-03: All 4 venue templates exist."""
        assert "IEEE" in VENUE_TEMPLATES
        assert "ACM" in VENUE_TEMPLATES
        assert "NeurIPS" in VENUE_TEMPLATES
        assert "Generic" in VENUE_TEMPLATES

    def test_02_04_ieee_template_uses_ieeetran(self):
        """TEST-153-02-04: IEEE template uses IEEEtran document class."""
        assert "IEEEtran" in IEEE_TEMPLATE.document_class

    def test_02_05_paper_stored_in_metadata(self):
        """TEST-153-02-05: Paper stored in proposal metadata after stage runs.

        HB-05 accepts short best-effort output (warn, not fail), so the
        FakeProvider's brief paper is stored instead of rejected. The
        old strict-xfail expected rejection; that policy is gone."""
        fake_provider = FakeProvider()
        from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
        synthesizer = PaperSynthesizer(fake_provider)

        proposal = ResearchProposal(
            title="Test Proposal",
            abstract="Test abstract",
            introduction="Test intro",
            proposed_method="Test method",
        )

        result = FakePipelineResult()
        result.proposals = {0: proposal}

        ctx = StageContext(
            result=result,
            all_papers=[
                FakePaper(title="Paper 1", authors=[FakeAuthor("Smith")])
            ],
            domain="AI/NLP",
        )

        # Inject a mock provider: without one, execute() constructs a
        # real generation provider and _evaluate_paper a real thinking
        # provider. Those clients leak open; on machines with live API
        # keys their late aclose crashes a later async test.
        stage = PaperSynthesisStage(
            synthesizer=synthesizer, provider=MagicMock(),
        )
        asyncio.run(stage.execute(ctx))

        # Check metadata
        metadata = stage._get_metadata(proposal)
        assert "full_paper" in metadata
        assert metadata["full_paper"] is not None
        assert isinstance(metadata["full_paper"], dict)
        assert "paper_markdown" in metadata["full_paper"]

    def test_02_06_stage_skipped_when_flag_disabled(self):
        """TEST-153-02-06: Stage skips when paper_synthesis disabled in strategy."""
        from backend.pipeline.strategies.models import StrategyConfig

        fake_provider = FakeProvider()
        from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
        synthesizer = PaperSynthesizer(fake_provider)

        proposal = ResearchProposal(
            title="Test Proposal",
            abstract="Test abstract",
        )

        result = FakePipelineResult()
        result.proposals = {0: proposal}

        strategy_config = StrategyConfig(
            name=PipelineStrategy.FAST_SCAN,
            stages={"paper_synthesis": StageConfig(enabled=False)},
        )

        ctx = StageContext(
            result=result,
            all_papers=[],
            domain="AI/NLP",
            params={"strategy_config": strategy_config},
        )

        stage = PaperSynthesisStage(synthesizer=synthesizer)
        outcome = asyncio.run(stage.execute(ctx))

        # Stage returns True (didn't halt) but didn't write metadata
        assert outcome is True
        metadata = stage._get_metadata(proposal)
        assert "full_paper" not in metadata


# ════════════════════════════════════════════════════════════
# TASK-03: LatexExporter + API Route (5 tests)
# ════════════════════════════════════════════════════════════


class TestLatexExporter:
    """TEST-153-03-01 through TEST-153-03-05."""

    def test_03_01_venue_template_used(self):
        """TEST-153-03-01: LatexExporter uses venue template when specified."""
        from backend.pipeline.export.latex_exporter import LatexExporter

        proposal = ResearchProposal(
            title="Test Paper",
            abstract="Abstract text",
            introduction="Intro text",
            related_work="Related work text",
            proposed_method="Method text",
            expected_contributions="Contributions text",
            evaluation_plan="Eval plan text",
            timeline="Timeline text",
            references=[],
        )

        exporter = LatexExporter()
        latex = exporter.export(proposal, venue="IEEE")

        assert "IEEEtran" in latex

    def test_03_02_default_venue_is_generic(self):
        """TEST-153-03-02: Exporter works without venue parameter (Generic default)."""
        from backend.pipeline.export.latex_exporter import LatexExporter

        proposal = ResearchProposal(
            title="Test Paper",
            abstract="Abstract text",
            introduction="Intro text",
            related_work="Related work text",
            proposed_method="Method text",
            expected_contributions="Contributions text",
            evaluation_plan="Eval plan text",
            timeline="Timeline text",
            references=[],
        )

        exporter = LatexExporter()
        latex = exporter.export(proposal)

        # Should work without error and contain documentclass
        assert "\\documentclass" in latex
        assert "\\begin{document}" in latex

    def test_03_03_latex_export_api_returns_valid_latex(self):
        """TEST-153-03-03: LaTeX export API returns valid LaTeX with \\begin{document}."""
        from fastapi.testclient import TestClient

        proposal = ResearchProposal(
            title="API Test Paper",
            abstract="Abstract for API test",
            introduction="Introduction text",
            related_work="Related work text",
            proposed_method="Proposed method text",
            expected_contributions="Contributions",
            evaluation_plan="Eval plan",
            timeline="Timeline",
            references=[],
        )

        mock_persistence = MagicMock()
        mock_persistence.get_proposals.return_value = [proposal]

        with patch("backend.pipeline.persistence.PipelinePersistence",
                   return_value=mock_persistence):
            from fastapi import FastAPI

            from backend.api.routes.export import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get("/api/export/latex/test_run_123")
            assert response.status_code == 200
            body = response.text
            assert "\\begin{document}" in body

    def test_03_04_api_accepts_venue_parameter(self):
        """TEST-153-03-04: API route accepts venue parameter and uses it."""
        from fastapi.testclient import TestClient

        proposal = ResearchProposal(
            title="Venue Test Paper",
            abstract="Abstract",
            introduction="Intro",
            related_work="Related",
            proposed_method="Method",
            expected_contributions="Contributions",
            evaluation_plan="Eval",
            timeline="Timeline",
            references=[],
        )

        mock_persistence = MagicMock()
        mock_persistence.get_proposals.return_value = [proposal]

        with patch("backend.pipeline.persistence.PipelinePersistence",
                   return_value=mock_persistence):
            from fastapi import FastAPI

            from backend.api.routes.export import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get("/api/export/latex/test_run?venue=IEEE")
            assert response.status_code == 200
            assert "IEEEtran" in response.text

    def test_03_05_no_unclosed_latex_environments(self):
        """TEST-153-03-05: Generated LaTeX has no unclosed environments (HB-03)."""
        from backend.pipeline.export.latex_exporter import LatexExporter

        proposal = ResearchProposal(
            title="Env Test",
            abstract="Abstract text for environment test",
            introduction="Introduction text here",
            related_work="Related work content",
            proposed_method="Method description with $x = y$ formula",
            expected_contributions="Contributions list",
            evaluation_plan="Evaluation description",
            timeline="12 weeks timeline",
            references=[],
        )

        exporter = LatexExporter()
        latex = exporter.export(proposal)

        # Find all \begin{X} and \end{X} and verify matching
        begins = re.findall(r'\\begin\{(\w+)\}', latex)
        ends = re.findall(r'\\end\{(\w+)\}', latex)

        # Every begin should have a matching end
        from collections import Counter
        begin_counts = Counter(begins)
        end_counts = Counter(ends)

        for env, count in begin_counts.items():
            assert end_counts.get(env, 0) == count, (
                f"Unclosed environment: \\begin{{{env}}} appears {count} times "
                f"but \\end{{{env}}} appears {end_counts.get(env, 0)} times"
            )


# ════════════════════════════════════════════════════════════
# TASK-04: Strategy Presets (5 tests)
# ════════════════════════════════════════════════════════════


class TestStrategyPresets:
    """TEST-153-04-01 through TEST-153-04-05."""

    def test_04_01_deep_research_enables_paper_synthesis(self):
        """TEST-153-04-01: deep_research enables paper_synthesis."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("deep_research")
        ps = config.stages.get("paper_synthesis")
        assert ps is not None
        assert ps.enabled is True

    def test_04_02_academic_proposal_enables_paper_synthesis(self):
        """TEST-153-04-02: academic_proposal enables paper_synthesis."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("academic_proposal")
        ps = config.stages.get("paper_synthesis")
        assert ps is not None
        assert ps.enabled is True

    def test_04_03_fast_scan_disables_paper_synthesis(self):
        """TEST-153-04-03: fast_scan disables paper_synthesis."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("fast_scan")
        ps = config.stages.get("paper_synthesis")
        assert ps is not None
        assert ps.enabled is False

    def test_04_04_all_four_presets_load(self):
        """TEST-153-04-04: All 4 presets load without exceptions."""
        registry = StrategyRegistry()
        register_presets(registry)

        for name in ["deep_research", "fast_scan", "academic_proposal", "literature_review"]:
            config = registry.get(name)
            assert config is not None
            assert "paper_synthesis" in config.stages

    def test_04_05_literature_review_disables_paper_synthesis(self):
        """TEST-153-04-05: literature_review disables paper_synthesis (FLAG-02)."""
        registry = StrategyRegistry()
        register_presets(registry)

        config = registry.get("literature_review")
        ps = config.stages.get("paper_synthesis")
        assert ps is not None
        assert ps.enabled is False

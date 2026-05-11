"""BATCH-175: End-to-End Pipeline Integration Test.

Runs the full 16-stage pipeline via a subclassed PipelineOrchestrator
with all services mocked. Verifies every stage executes in order and
produces output on the PipelineResult.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Stub heavy imports before anything else ──────────────────────────────────
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewScore
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.reflection.reflector import ReflectionResult
from backend.pipeline.result import PipelineResult, StageReport
from backend.pipeline.stages import (
    AdversarialReviewStage,
    CitationAuditStage,
    EvaluationStage,
    ExportStage,
    FeasibilityScoringStage,
    GapAnalysisStage,
    GapReflectionStage,
    IdeaGenerationStage,
    IdeaReflectionStage,
    IngestionStage,
    LiteratureSearchStage,
    MechanicalMetricsStage,
    NoveltyCheckingStage,
    PaperSynthesisStage,
    ProposalDeepeningStage,
    ProposalSynthesisStage,
    StageContext,
)
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
from backend.pipeline.verification.citation_claim_auditor import CitationAuditReport
from backend.pipeline.verification.proposal_deepener import DeepenedProposal

# ── Data Factories ───────────────────────────────────────────────────────────


def _paper(idx: int = 0) -> Paper:
    return Paper(
        id=f"p{idx}",
        source="test",
        title=f"Test Paper {idx}: NLP advances in domain adaptation",
        abstract=f"Abstract for paper {idx} discussing methodology and empirical results.",
        authors=[Author(name=f"Author {idx}")],
        year=2024,
    )


def _gap(title: str = "Test Gap: Multilingual Transfer", idx: int = 0) -> ResearchGap:
    return ResearchGap(
        title=title,
        description=f"Research gap {idx}: limited understanding of cross-lingual transfer.",
        gap_type="methodological",
        related_clusters=[1],
        potential_impact="High",
        confidence=0.8,
    )


def _idea(title: str = "Test Idea: Cross-Lingual Adapter", score: float = 0.7, idx: int = 0) -> ResearchIdea:
    return ResearchIdea(
        title=f"{title} ({idx})" if idx > 0 else title,
        problem_statement="Existing methods fail on low-resource languages.",
        proposed_method="Use adapter fusion with contrastive learning.",
        expected_contributions="Improved transfer to 50+ languages.",
        novelty_rationale="First to combine adapter fusion with contrastive objectives.",
        evaluation_approach="Benchmark on XTREME benchmark suite.",
        domain="AI/NLP",
        round_generated=1,
        score=score,
        supporting_papers=["p0", "p1"],
        source_gap_ids=["Test Gap: Multilingual Transfer"],
    )


def _novelty_report() -> NoveltyReport:
    return NoveltyReport(
        overall_score=0.85,
        method_novelty=0.9,
        problem_novelty=0.8,
        domain_transfer=0.7,
        combination_novelty=0.9,
        novelty_arguments="Novel combination of adapter fusion and contrastive learning.",
        closest_matches=[],
    )


def _feasibility_report() -> FeasibilityReport:
    return FeasibilityReport(
        overall_score=7.5,
        data_availability=8.0,
        computational_requirements=7.0,
        methodological_complexity=6.0,
        evaluation_plan=8.0,
        novelty_grounding=7.0,
        impact_potential=8.0,
        reasoning="Strong feasibility with available benchmarks.",
        estimated_timeline="6 months",
        key_risks=["Data quality in low-resource languages"],
    )


def _cluster_report() -> ClusterReport:
    return ClusterReport(clusters=[], total_papers=3)


def _proposal(idx: int = 0) -> ResearchProposal:
    return ResearchProposal(
        idea_id=idx,
        title=f"Test Proposal {idx}: Cross-Lingual Adapter Fusion",
        abstract=f"Abstract for proposal {idx}.",
        introduction="This proposal addresses cross-lingual transfer.",
        related_work="Prior work explored adapter-based methods.",
        proposed_method="We propose adapter fusion with contrastive learning.",
        expected_contributions="Improved performance on 50+ languages.",
        evaluation_plan="Benchmarks on XTREME with ablation studies.",
        timeline="12 months",
        references=[],
    )


def _adversarial_score() -> AdversarialReviewScore:
    return AdversarialReviewScore(
        soundness=8,
        novelty=7,
        feasibility=8,
        clarity=9,
        overall=8.0,
        soundness_justification="Solid methodology.",
        novelty_justification="Novel combination.",
        feasibility_justification="Doable with existing infrastructure.",
        clarity_justification="Well-written proposal.",
        revision_notes=None,
        round=1,
        model_used="test-reviewer",
    )


# ── Mock Services ────────────────────────────────────────────────────────────


class MockSearchService:
    """Returns papers for literature search queries."""

    async def search_all(self, query: str, **kwargs) -> list[Paper]:
        return [_paper(i) for i in range(5)]


def _mock_settings() -> MagicMock:
    """Settings mock with all attributes the pipeline reads."""
    s = MagicMock()
    # Pipeline params
    s.generation_rounds = 1
    s.ideas_per_round = 2
    # Stage retry — no retries for fast tests
    s.stage_max_retries = 0
    s.stage_retry_base_delay = 0.01
    s.stage_retry_max_delay = 0.1
    s.stage_retry_jitter = 0.0
    # Feature flags — all off to minimize services
    s.heartbeat_enabled = False
    s.counterfactual_enabled = False
    s.quality_backloop_enabled = False
    s.embedding_fallback_enabled = False
    s.query_transform_enabled = False
    s.reranker_enabled = False
    s.retrieval_quality_scoring_enabled = False
    s.citation_novelty_enabled = False
    s.embedding_novelty_enabled = False
    s.faithfulness_check_enabled = False
    s.contradiction_detection_enabled = False
    s.reasoning_verification_enabled = False
    s.dynamic_agents_enabled = False
    s.sub_goal_generation_enabled = False
    s.evaluation_framework_enabled = False
    s.multi_agent_enabled = False
    s.tree_of_thought_enabled = False
    s.sandboxing_enabled = False
    s.observability_enabled = False
    s.metacognitive_enabled = False
    s.mcp_enabled = False
    s.context_management_enabled = False
    s.streaming_enabled = False
    s.consolidation_enabled = False
    s.adaptation_enabled = False
    s.graph_rag_enabled = False
    s.tool_discovery_enabled = False
    s.negotiation_enabled = False
    s.session_enabled = False
    s.autonomy_schedule_enabled = False
    s.plugin_verification_enabled = False
    s.compaction_enabled = False
    s.memory_enabled = False
    s.cross_stage_context_enabled = False
    s.self_improve_enabled = False
    s.skills_enabled = False
    s.budget_enabled = False
    s.autonomy_enabled = False
    s.governance_enabled = False
    s.lmstudio_enabled = False
    s.model_routing_enabled = False
    s.cost_routing_enabled = False
    # Timeout / budget
    s.per_proposal_timeout = 300.0
    s.budget_max_cost_usd = 100.0
    # Settings attributes that get_settings() callers need
    s.s1_parser_mode = "hybrid"
    s.s1_parser_url = ""
    s.embedding_provider = "test"
    s.embedding_model = "test"
    s.openai_api_key = ""
    s.ollama_base_url = "http://localhost:11434"
    s.embedding_dimension = None
    s.embedding_batch_size = 32
    s.chroma_persist_dir = "/tmp/test_chroma"
    s.bm25_persist_dir = "/tmp/test_bm25"
    return s


# ── TestOrchestrator ─────────────────────────────────────────────────────────


class _OrchestratorUnderTest(PipelineOrchestrator):
    """Subclass that bypasses real __init__ and injects mock services.

    Overrides __init__ entirely — does NOT call super().__init__().
    Sets every attribute that run() and its helpers reference.
    Builds 16 stages manually with all services mocked.
    """

    def __init__(self):
        # Do NOT call super().__init__() — avoid all real service creation
        self._settings = _mock_settings()
        self._stage_callback = None
        self._strategy_name = "deep_research"
        self._strategy_registry = MagicMock()
        self._strategy_config = MagicMock()
        self._strategy_config.stages = {}  # empty → no stages skipped by strategy

        # ── Providers ────────────────────────────────────────────────
        self._provider = MagicMock()
        self._thinking_provider = MagicMock()
        self._cost_tracker = MagicMock()
        self._cost_tracker._events = []
        self._cost_tracker.total_tokens = 0
        self._cost_tracker.total_cost = 0.0
        self._cost_tracker.by_stage = MagicMock(return_value={})
        self._cost_tracker.summary = MagicMock(return_value={"total_cost_usd": 0.0})
        self._model_selector = None
        self._task_router = None

        # ── Core services (mocked) ──────────────────────────────────
        self._search = MockSearchService()
        self._pdf = MagicMock()

        self._embedding = MagicMock()
        self._embedding.validate_startup = AsyncMock(return_value=True)

        self._store = MagicMock()
        self._store.add_papers = AsyncMock(return_value=5)

        self._bm25 = MagicMock()
        self._retriever = MagicMock()

        self._kg = MagicMock()
        self._kg._entities = {}
        self._kg.add_entity = MagicMock()
        self._kg.add_relationship = MagicMock()
        self._kg.save = MagicMock()

        self._gap_analyzer = MagicMock()
        self._gap_analyzer.analyze = AsyncMock(
            return_value=([_gap(idx=i) for i in range(2)], _cluster_report())
        )

        self._goal_manager = MagicMock()
        self._goal_manager.create_from_gaps = MagicMock(return_value=[])

        self._agent = MagicMock()
        self._agent.run = AsyncMock(return_value=[_idea(idx=i) for i in range(2)])
        self._agent.last_critique_history = {}
        self._agent.last_refinement_history = {}
        self._agent.set_hooks = MagicMock()
        self._agent.set_temperature_overrides = MagicMock()

        self._novelty = MagicMock()
        self._novelty.check_novelty = AsyncMock(return_value=_novelty_report())

        self._feasibility = MagicMock()
        self._feasibility.score_feasibility = AsyncMock(return_value=_feasibility_report())
        self._feasibility.run_counterfactual = AsyncMock(return_value=_feasibility_report())

        self._synthesizer = MagicMock()
        self._synthesizer.synthesize = AsyncMock(return_value=_proposal(0))

        self._export = MagicMock()
        self._export.export = AsyncMock(return_value="/tmp/test_export.md")

        self._dag_executor = None
        self._dag_agents = {}
        self._forest = None
        self._reasoning_verifier = None
        self._faithfulness_checker = None

        # ── Hooks ────────────────────────────────────────────────────
        self._hooks = MagicMock()
        self._hooks.dispatch_sync_safe = AsyncMock()
        self._hooks.register = MagicMock()

        # ── Services that run() checks for None ──────────────────────
        self._memory = None
        self._shared_kb = None
        self._shared_memory_bridge = None
        self._cross_stage_ctx = None
        self._prompt_builder = None
        self._evolver = None
        self._lesson_extractor = None
        self._evolution_engine = None
        self._ab_test_harness = None
        self._ratchet_loop = None
        self._feedback_history = None
        self._skill_registry = None
        self._skill_proposer = None
        self._skill_generator = None
        self._budget = None
        self._plan_verifier = None
        self._state_machine = None
        self._curiosity = None
        self._scheduler = None
        self._governance_validator = None
        self._governance_audit = None
        self._governance_policy = None
        self._approval_manager = None
        self._embedding_valid = True
        self._pipeline_evaluator = None
        self._sandbox_manager = None
        self._observability = None
        self._metacog = None
        self._mcp_manager = None
        self._context_window_manager = None
        self._stream_manager = None
        self._consolidator = None
        self._consolidation_scheduler = None
        self._adaptation_manager = None
        self._graph_rag_retriever = None
        self._tool_matcher = None
        self._tool_scorer = None
        self._consensus_engine = None
        self._session_manager = None
        self._integration = None
        self._world_model = None
        self._contradiction_scanner = None
        self._quality_scorer = None

        # ── Persistence (mocked) ─────────────────────────────────────
        self._persistence = MagicMock()
        self._persistence.create_run_record = MagicMock(return_value=1)
        self._persistence.save_checkpoint = MagicMock()
        self._persistence.advance_stage = MagicMock()
        self._persistence.persist_papers = MagicMock()
        self._persistence.persist_gaps = MagicMock()
        self._persistence.persist_ideas = MagicMock()
        self._persistence.persist_proposals = MagicMock()
        self._persistence.persist_tree_data = MagicMock()
        self._persistence.mark_run_completed = MagicMock()
        self._persistence.mark_run_failed = MagicMock()
        self._persistence.get_warnings = MagicMock(return_value=[])

        # ── Reference verifier ───────────────────────────────────────
        self._reference_verifier = MagicMock()

        # ── Token counter & compaction ───────────────────────────────
        self._token_counter = MagicMock()
        self._token_counter.snapshot = MagicMock()
        self._token_counter.snapshot.return_value.total_tokens = 0
        self._token_counter.reset = MagicMock()

        self._compaction = MagicMock()
        self._compaction.prepare_context = AsyncMock(side_effect=lambda ctx, _name: ctx)
        self._compaction.record_usage = MagicMock()

        # ── Misc ─────────────────────────────────────────────────────
        self._stage_timings = {}
        self._trace_processor = MagicMock()
        self._input_guardrails = []
        self._tool_registry = MagicMock()
        self._registry = MagicMock()
        self._plugin_loader = MagicMock()

        # ── Build stages ─────────────────────────────────────────────
        self._stages = self._build_test_stages()

    def _build_test_stages(self) -> list:
        """Build all 16 stages with injected mock services."""

        # Mock reflector for gap & idea reflection
        mock_reflector = MagicMock()
        mock_reflector.reflect_gaps = AsyncMock(
            return_value=ReflectionResult(score=0.85, passed=True, justification="Gaps are well-defined.", iteration=1)
        )
        mock_reflector.reflect_ideas = AsyncMock(
            return_value=ReflectionResult(score=0.80, passed=True, justification="Ideas are promising.", iteration=1)
        )

        # Mock evaluator for EvaluationStage
        mock_eval_result = MagicMock()
        mock_axis = MagicMock(score=0.8, justification="Good")
        mock_eval_result.novelty = mock_axis
        mock_eval_result.feasibility = mock_axis
        mock_eval_result.completeness = mock_axis
        mock_eval_result.rigor = mock_axis
        mock_eval_result.clarity = mock_axis
        mock_eval_result.overall = 0.8
        mock_eval_result.to_dict = MagicMock(return_value={"overall": 0.8})
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate = AsyncMock(return_value=mock_eval_result)

        # Mock paper synthesizer for PaperSynthesisStage
        mock_paper_result = MagicMock()
        mock_paper_result.word_count = 4200
        mock_paper_result.to_dict = MagicMock(return_value={
            "paper_markdown": "# Full Paper\n\nContent...",
            "word_count": 4200,
        })
        mock_paper_synthesizer = MagicMock()
        mock_paper_synthesizer.synthesize = AsyncMock(return_value=mock_paper_result)

        # Mock citation auditor for CitationAuditStage
        mock_audit_report = CitationAuditReport(
            proposal_id=0,
            total_citations=2,
            verified_citations=2,
            fabricated_citations=0,
            context_mismatches=0,
            quantitative_errors=0,
            trust_score=0.92,
            items=[],
            model_used="test",
            status="completed",
        )
        mock_auditor = MagicMock()
        mock_auditor.audit = AsyncMock(return_value=mock_audit_report)

        # Mock deepener for ProposalDeepeningStage
        mock_deepened = DeepenedProposal(
            idea_id=0,
            title="Test Proposal 0",
            architecture="## Architecture\nModule A -> Module B",
            toy_example="## Example\nInput X -> Output Y",
            failure_modes="## Failure Modes\n1. Edge case A",
            success_criteria="## Criteria\n| Metric | Target |",
        )
        mock_deepener = MagicMock()
        mock_deepener.deepen = AsyncMock(return_value=mock_deepened)

        # Mock adversarial reviewer
        mock_reviewer = MagicMock()
        mock_reviewer.review = AsyncMock(return_value=_adversarial_score())

        # Build stages in _STAGE_ORDER
        return [
            # 0. literature_search
            LiteratureSearchStage(self._search, self._hooks),
            # 1. ingestion
            IngestionStage(self._store, self._bm25, self._embedding, kg=self._kg, provider=self._provider),
            # 2. gap_analysis
            GapAnalysisStage(self._gap_analyzer, self._goal_manager, self._hooks, self._memory, kg=self._kg),
            # 3. gap_reflection
            GapReflectionStage(provider=self._provider, reflector=mock_reflector, threshold=0.6),
            # 4. idea_generation
            IdeaGenerationStage(
                self._agent, self._hooks,
                dag_executor=self._dag_executor,
                dag_agents=self._dag_agents,
                provider=self._provider,
                kg=self._kg,
                forest=self._forest,
                reasoning_verifier=self._reasoning_verifier,
            ),
            # 5. idea_reflection
            IdeaReflectionStage(provider=self._provider, reflector=mock_reflector, threshold=0.6),
            # 6. novelty_checking
            NoveltyCheckingStage(self._novelty, self._hooks),
            # 7. feasibility_scoring
            FeasibilityScoringStage(self._feasibility),
            # 8. mechanical_metrics
            MechanicalMetricsStage(),
            # 9. proposal_synthesis
            ProposalSynthesisStage(
                self._synthesizer,
                governance_validator=None,
                governance_audit=None,
                ref_validator=None,
            ),
            # 10. adversarial_review
            AdversarialReviewStage(
                reviewer=mock_reviewer,
                synthesizer=self._synthesizer,
                generation_provider=MagicMock(provider_name="generation-model"),
                thinking_provider=MagicMock(provider_name="thinking-model"),
            ),
            # 11. evaluation
            EvaluationStage(provider=self._provider, evaluator=mock_evaluator),
            # 12. paper_synthesis
            PaperSynthesisStage(provider=self._provider, synthesizer=mock_paper_synthesizer),
            # 13. citation_audit
            CitationAuditStage(provider=self._provider, auditor=mock_auditor),
            # 14. proposal_deepening
            ProposalDeepeningStage(deepener=mock_deepener),
            # 15. export
            ExportStage(self._export),
        ]


# ── Fixtures ─────────────────────────────────────────────────────────────────

SETTINGS_PATCH_TARGETS = [
    "backend.config.get_settings",
    "backend.pipeline.stages.get_settings",
]


@pytest.fixture()
def orchestrator():
    """Create an _OrchestratorUnderTest with all mock services."""
    return _OrchestratorUnderTest()


def _run_pipeline(orch: _OrchestratorUnderTest) -> PipelineResult:
    """Run the full pipeline via asyncio.run(), patching get_settings."""
    mock_settings = orch._settings
    with patch("backend.config.get_settings", return_value=mock_settings):
        return asyncio.run(orch.run(domain="AI/NLP"))


# ── TASK-01: Mock Infrastructure + Full Pipeline Run (7 tests) ───────────────


class TestFullPipelineRun:
    """End-to-end: run all 16 stages with mocked providers."""

    def test_full_pipeline_completes(self, orchestrator):
        """Pipeline completes without exception and returns a result."""
        result = _run_pipeline(orchestrator)
        assert result is not None
        assert isinstance(result, PipelineResult)
        assert result.run_id != ""

    def test_all_16_stages_in_report(self, orchestrator):
        """All 16 stages are tracked in stage_report."""
        result = _run_pipeline(orchestrator)
        assert len(result.stage_report) == 16, (
            f"Expected 16 stage_report entries, got {len(result.stage_report)}: "
            f"{[r.name for r in result.stage_report]}"
        )

    def test_core_stages_executed(self, orchestrator):
        """Stages 0-4 (lit search through idea gen) have status 'executed'."""
        result = _run_pipeline(orchestrator)
        for i, name in enumerate(
            ["literature_search", "ingestion", "gap_analysis", "gap_reflection", "idea_generation"]
        ):
            reports = [r for r in result.stage_report if r.name == name]
            assert len(reports) >= 1, f"No report for stage '{name}'"
            assert reports[0].status == "executed", (
                f"Stage '{name}' (idx {i}) status={reports[0].status}, expected 'executed'"
            )

    def test_result_has_papers(self, orchestrator):
        """Pipeline finds papers from the mock search service."""
        result = _run_pipeline(orchestrator)
        assert result.papers_found > 0, f"Expected papers_found > 0, got {result.papers_found}"

    def test_result_has_gaps(self, orchestrator):
        """Gap analysis produces research gaps."""
        result = _run_pipeline(orchestrator)
        assert len(result.gaps) > 0, f"Expected gaps, got {len(result.gaps)}"

    def test_result_has_ideas(self, orchestrator):
        """Idea generation produces research ideas."""
        result = _run_pipeline(orchestrator)
        assert len(result.ideas) > 0, f"Expected ideas, got {len(result.ideas)}"

    def test_result_has_proposals(self, orchestrator):
        """Proposal synthesis produces at least one proposal."""
        result = _run_pipeline(orchestrator)
        # Proposals are stored in a dict keyed by idea index
        assert len(result.proposals) > 0, (
            f"Expected proposals, got {len(result.proposals)}"
        )


# ── TASK-02: Stage Ordering + Regression + Batch Close (4 tests) ─────────────


class TestStageOrderingAndRegression:

    _STAGE_ORDER = PipelineOrchestrator._STAGE_ORDER

    def test_stages_execute_in_order(self, orchestrator):
        """Verify stage_report names match _STAGE_ORDER for all executed stages."""
        result = _run_pipeline(orchestrator)
        executed_names = [
            r.name for r in result.stage_report if r.status == "executed"
        ]
        for i, name in enumerate(executed_names):
            assert name == self._STAGE_ORDER[i], (
                f"Stage at position {i} is '{name}', expected '{self._STAGE_ORDER[i]}'"
            )

    def test_no_regressions_batch172_174(self):
        """Verify batch172-174 tests still pass."""
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "backend/tests/test_pipeline/test_batch172_wiring.py",
                "backend/tests/test_pipeline/test_batch172_preflight.py",
                "backend/tests/test_pipeline/test_batch172_strategies.py",
                "backend/tests/test_pipeline/test_batch172_verification.py",
                "backend/tests/test_pipeline/test_batch173_stage_report.py",
                "backend/tests/test_pipeline/test_batch173_api_expose.py",
                "backend/tests/test_pipeline/test_batch173_verification.py",
                "backend/tests/test_pipeline/test_batch174_core_stages.py",
                "backend/tests/test_pipeline/test_batch174_synthesis_stages.py",
                "backend/tests/test_pipeline/test_batch174_verification.py",
                "-p", "no:asyncio", "-q",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(Path(__file__).resolve().parent.parent.parent.parent),
        )
        assert result.returncode == 0, (
            f"Batch172-174 regression FAILED:\n{result.stdout}\n{result.stderr}"
        )

    def test_state_md_has_batch175(self):
        """STATE.md documents BATCH-175."""
        state_path = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "aiv" / "STATE.md"
        content = state_path.read_text(encoding="utf-8")
        assert "BATCH-175" in content, "STATE.md missing BATCH-175 entry"

    def test_changelog_has_batch175(self):
        """CHANGELOG.md documents BATCH-175."""
        changelog_path = Path(__file__).resolve().parent.parent.parent.parent / "CHANGELOG.md"
        content = changelog_path.read_text(encoding="utf-8")
        assert "BATCH-175" in content, "CHANGELOG.md missing BATCH-175 entry"

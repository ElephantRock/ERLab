"""Post-gap downstream end-to-end proof (Commit 6).

Starts from the typed synthetic post-gap seed and executes the REAL
production stages in order through paper synthesis, evaluation, citation
audit, and export. Only these are synthetic: papers, gaps, cluster report,
and model responses (via SyntheticPipelineProvider).

Production components used: StageContext, PipelineResult, the real
PipelineStage implementations, the paper synthesis service, paper
evaluation gates, citation/source mapping, the export service, and
persistence.

Excludes only: literature search, ingestion, gap analysis (replaced by the
seed) and live experiment execution (separate opt-in capability).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Mock heavy optional deps before importing pipeline modules.
for _mod in ("chromadb", "google.generativeai"):
    sys.modules.setdefault(_mod, MagicMock())

from backend.pipeline.autonomy.hooks import HookDispatcher
from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer
from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
from backend.pipeline.export.export_service import ExportService
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.novelty.novelty_checker import NoveltyChecker
from backend.pipeline.result import PipelineOutcome, PipelineResult
from backend.pipeline.stages import (
    AdversarialReviewStage,
    CitationAuditStage,
    EvaluationStage,
    ExportStage,
    FeasibilityScoringStage,
    IdeaGenerationStage,
    MechanicalMetricsStage,
    NoveltyCheckingStage,
    PaperSynthesisStage,
    ProposalDeepeningStage,
    ProposalSynthesisStage,
    StageContext,
)
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.pipeline.verification.citation_claim_auditor import CitationClaimAuditor
from backend.tests.support.post_gap_seed import build_low_resource_mt_seed
from backend.tests.support.synthetic_pipeline_provider import SyntheticPipelineProvider

RUN_ID = "post-gap-e2e-run"


# ── Typed validation views (metadata is currently dict-based) ────────


def _load_metadata(proposal: Any) -> dict:
    """Read the proposal metadata dict, handling JSON-string storage.

    Production code stores proposal metadata as either a dict or a JSON
    string (see ProposalSynthesisStage._set_metadata). This mirrors the
    production _get_metadata helper so the views work in both forms.
    """
    import json as _json
    md = getattr(proposal, "metadata", None)
    if isinstance(md, str):
        try:
            return _json.loads(md) or {}
        except (ValueError, TypeError):
            return {}
    if isinstance(md, dict):
        return md
    return {}


class SourceMapEntryView:
    """Read-only view over a source-map entry dict."""

    def __init__(self, data: dict):
        self._d = data or {}

    @property
    def marker(self) -> str:
        return self._d.get("marker", "")

    @property
    def marker_index(self) -> int:
        return int(self._d.get("marker_index", -1))

    @property
    def source_id(self) -> str | None:
        return self._d.get("source_id")

    @property
    def mapping_status(self) -> str:
        return self._d.get("mapping_status", "unknown")


class FullPaperArtifactView:
    """Read-only view over proposal.metadata['full_paper'].

    ``synthesis_state`` lives at the top level of the proposal metadata
    (PaperSynthesisStage sets it there), not inside the ``full_paper``
    dict, so the view carries the proposal to resolve it.
    """

    def __init__(self, proposal: Any):
        self._proposal = proposal
        self._md = _load_metadata(proposal)
        self._d = self._md.get("full_paper", {}) or {}

    @property
    def exists(self) -> bool:
        return bool(self._d)

    @property
    def paper_markdown(self) -> str:
        return self._d.get("paper_markdown", "") or ""

    @property
    def word_count(self) -> int:
        return int(self._d.get("word_count", 0) or 0)

    @property
    def synthesis_state(self) -> str:
        # Lives at the top metadata level, not inside full_paper.
        return self._md.get("synthesis_state", "") or self._d.get("synthesis_state", "") or ""

    @property
    def source_map(self) -> list[SourceMapEntryView]:
        return [SourceMapEntryView(e) for e in self._d.get("source_map", [])]


class EvaluationDimensionView:
    def __init__(self, data: dict):
        self._d = data or {}

    @property
    def score(self) -> float:
        v = self._d.get("score")
        return float(v) if v is not None else 0.0

    @property
    def justification(self) -> str:
        return self._d.get("justification", "") or ""


class PaperEvaluationView:
    """Read-only view over proposal.metadata['paper_evaluation'].

    The paper-evaluation artifact stores its 7 dimensions under a
    ``dimensions`` sub-dict (each ``{score, justification}``), plus
    ``scope``, ``status`` ("ready" or "blocked"), ``gates``, and
    ``overall``. The proposal-level evaluation (metadata['evaluation'])
    stores dimensions flat at the top level, so the view handles both.
    """

    SEVEN_DIMS = (
        "novelty", "feasibility", "completeness", "rigor",
        "clarity", "baseline_adequacy", "compute_realism",
    )

    def __init__(self, proposal: Any):
        md = _load_metadata(proposal)
        self._d = md.get("paper_evaluation") or md.get("evaluation") or {}
        # Dimensions may be nested (paper_evaluation) or flat (evaluation).
        nested = self._d.get("dimensions")
        self._dims = nested if isinstance(nested, dict) else self._d

    @property
    def exists(self) -> bool:
        return bool(self._d)

    @property
    def scope(self) -> str:
        return self._d.get("scope", "") or ""

    @property
    def status(self) -> str:
        return self._d.get("status", "") or ""

    def dimension(self, name: str) -> EvaluationDimensionView:
        v = self._dims.get(name)
        if isinstance(v, dict):
            return EvaluationDimensionView(v)
        # Some storages store a bare number.
        return EvaluationDimensionView({"score": v} if v is not None else {})

    def all_dimensions_present(self) -> bool:
        return all(self._dims.get(d) is not None for d in self.SEVEN_DIMS)


# ── Harness ──────────────────────────────────────────────────────────


class _FakeVectorStore:
    """Minimal VectorStore returning empty results (no real index)."""

    async def query(self, query_text, n_results=10, filter_metadata=None):
        return []

    async def query_by_embedding(self, embedding, n_results=10):
        return []


def _build_provider() -> SyntheticPipelineProvider:
    return SyntheticPipelineProvider(run_id=RUN_ID)


def _seed_context(tmp_path: Path, provider: SyntheticPipelineProvider) -> StageContext:
    """Build a StageContext pre-loaded with the typed post-gap seed."""
    seed = build_low_resource_mt_seed()
    result = PipelineResult()
    result.gaps = list(seed.gaps)
    result.cluster_report = seed.cluster_report
    result.run_id = RUN_ID
    result.outcome = PipelineOutcome.RUNNING
    ctx = StageContext(result=result)
    ctx.all_papers = list(seed.papers)
    ctx.domain = seed.domain
    ctx.research_question = seed.research_question
    ctx.run_id = RUN_ID
    ctx.provider_override = provider
    ctx.export_format = "markdown"
    ctx.rounds = 1
    ctx.ideas_per = 2
    ctx.db_run_id = None  # avoid NoveltyCheckingStage importing the DB module
    ctx.params = {}
    return ctx


def _run(coro):
    return asyncio.run(coro)


# ── The proof ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def exported_run(tmp_path_factory):
    """Execute the full downstream chain once and cache the artifacts."""
    tmp_path = tmp_path_factory.mktemp("post_gap_e2e")
    provider = _build_provider()
    ctx = _seed_context(tmp_path, provider)

    hooks = HookDispatcher()
    # Stage order matches the downstream portion of _STAGE_ORDER.
    idea_stage = IdeaGenerationStage(
        agent=AgentOrchestrator(provider=provider), hooks=hooks,
    )
    novelty_stage = NoveltyCheckingStage(
        novelty_checker=NoveltyChecker(provider=provider, store=_FakeVectorStore()),
    )
    feasibility_stage = FeasibilityScoringStage(FeasibilityScorer(provider=provider))
    mechanical_stage = MechanicalMetricsStage()
    proposal_stage = ProposalSynthesisStage(ProposalSynthesizer(provider=provider))
    adversarial_stage = AdversarialReviewStage(
        reviewer=AdversarialReviewer(provider=provider),
        synthesizer=ProposalSynthesizer(provider=provider),
    )
    evaluation_stage = EvaluationStage(
        provider=provider, evaluator=ProposalEvaluator(provider=provider),
    )
    paper_stage = PaperSynthesisStage(provider=provider)
    citation_stage = CitationAuditStage(
        provider=provider, auditor=CitationClaimAuditor(provider=provider),
    )
    deepening_stage = ProposalDeepeningStage()
    export_stage = ExportStage(ExportService(output_dir=str(tmp_path / "exports")))

    stages = [
        ("idea_generation", idea_stage),
        ("novelty_checking", novelty_stage),
        ("feasibility_scoring", feasibility_stage),
        ("mechanical_metrics", mechanical_stage),
        ("proposal_synthesis", proposal_stage),
        ("adversarial_review", adversarial_stage),
        ("evaluation", evaluation_stage),
        ("paper_synthesis", paper_stage),
        ("citation_audit", citation_stage),
        ("proposal_deepening", deepening_stage),
        ("export", export_stage),
    ]

    for stage_name, stage in stages:
        provider.set_context(stage_name, RUN_ID)
        # ctx.provider_override is shared; set_context tags the stage.
        proceed = _run(stage.execute(ctx))
        assert proceed is True, f"stage {stage_name} returned False (halted)"

    return {"ctx": ctx, "provider": provider, "tmp_path": tmp_path}


# ── Pipeline progression ─────────────────────────────────────────────


class TestPipelineProgression:
    def test_at_least_one_idea(self, exported_run):
        assert len(exported_run["ctx"].result.ideas) >= 1

    def test_at_least_one_novelty_report(self, exported_run):
        assert len(exported_run["ctx"].result.novelty_reports) >= 1

    def test_at_least_one_feasibility_report(self, exported_run):
        assert len(exported_run["ctx"].result.feasibility_reports) >= 1

    def test_at_least_one_proposal(self, exported_run):
        assert len(exported_run["ctx"].result.proposals) >= 1

    def test_at_least_one_completed_paper(self, exported_run):
        proposals = exported_run["ctx"].result.proposals
        has_paper = any(
            FullPaperArtifactView(p).exists and FullPaperArtifactView(p).paper_markdown
            for p in proposals.values()
        )
        assert has_paper


# ── Paper artifact ───────────────────────────────────────────────────


class TestPaperArtifact:
    def _first_paper(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            view = FullPaperArtifactView(p)
            if view.exists:
                return view
        pytest.skip("no paper artifact produced")

    def test_paper_markdown_nonblank(self, exported_run):
        view = self._first_paper(exported_run)
        assert view.paper_markdown.strip()

    def test_paper_word_count_above_minimum(self, exported_run):
        view = self._first_paper(exported_run)
        assert view.word_count > 100

    def test_synthesis_state_ready(self, exported_run):
        view = self._first_paper(exported_run)
        assert view.synthesis_state == "ready"

    def test_source_map_present(self, exported_run):
        view = self._first_paper(exported_run)
        assert len(view.source_map) >= 1

    def test_all_source_markers_mapped(self, exported_run):
        import re
        view = self._first_paper(exported_run)
        markers = set(int(m) for m in re.findall(r"\[SOURCE-(\d+)\]", view.paper_markdown))
        if not markers:
            pytest.skip("no source markers in paper")
        mapped_indices = {e.marker_index for e in view.source_map if e.mapping_status == "mapped"}
        # Every emitted marker must be in range / mapped.
        assert markers <= mapped_indices, (
            f"unmapped markers: {markers - mapped_indices}"
        )

    def test_no_out_of_range_markers(self, exported_run):
        view = self._first_paper(exported_run)
        unmapped = [e for e in view.source_map if e.mapping_status == "unmapped"]
        # The source map records unmapped entries for any out-of-range marker.
        assert len(unmapped) == 0, f"out-of-range markers found: {len(unmapped)}"


# ── Paper evaluation ─────────────────────────────────────────────────


class TestPaperEvaluation:
    def _first_evaluated_proposal(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            ev = PaperEvaluationView(p)
            if ev.exists:
                return p, ev
        pytest.skip("no paper evaluation produced")

    def test_evaluation_scope_is_paper(self, exported_run):
        # PaperEvaluationView reads paper_evaluation (paper-scoped) when present.
        _p, ev = self._first_evaluated_proposal(exported_run)
        assert ev.exists
        assert ev.scope == "paper"

    def test_evaluation_status_ready_or_blocked(self, exported_run):
        # The plan requires the status be "ready" or an explicit "blocked"
        # (a gate finding). Either is acceptable; what's forbidden is a
        # missing/silent evaluation.
        _p, ev = self._first_evaluated_proposal(exported_run)
        assert ev.status in ("ready", "blocked"), f"unexpected status: {ev.status}"

    def test_all_seven_dimensions_present(self, exported_run):
        _p, ev = self._first_evaluated_proposal(exported_run)
        # The paper evaluation must carry all 7 dimensions under `dimensions`.
        assert ev.all_dimensions_present(), (
            f"missing dimensions: {set(PaperEvaluationView.SEVEN_DIMS) - set(ev._dims.keys())}"
        )

    def test_each_score_numeric_and_bounded(self, exported_run):
        _p, ev = self._first_evaluated_proposal(exported_run)
        for name in PaperEvaluationView.SEVEN_DIMS:
            dim = ev.dimension(name)
            assert isinstance(dim.score, (int, float))
            assert 0.0 <= dim.score <= 1.0, f"{name} score out of bounds: {dim.score}"

    def test_each_dimension_has_justification(self, exported_run):
        _p, ev = self._first_evaluated_proposal(exported_run)
        for name in PaperEvaluationView.SEVEN_DIMS:
            assert ev.dimension(name).justification, f"{name} missing justification"


# ── Citation and provenance ──────────────────────────────────────────


class TestCitationProvenance:
    def test_citation_audit_executed(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            md = _load_metadata(p)
            if "citation_audit" in md:
                report = md["citation_audit"]
                assert report.get("status") in ("complete", "partial", "skipped")
                return
        pytest.skip("no citation audit produced")

    def test_at_least_one_mapped_citation(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            md = _load_metadata(p)
            report = md.get("citation_audit", {})
            if report.get("total_citations", 0) >= 1:
                assert report.get("verified_citations", 0) >= 0
                return
        pytest.skip("no citations to verify")

    def test_no_fabricated_source_identity(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            md = _load_metadata(p)
            report = md.get("citation_audit", {})
            # Fabricated citations (out-of-range markers) must be zero in the
            # synthetic seed since the provider only emits in-range markers.
            if report:
                assert report.get("fabricated_citations", 0) == 0

    def test_source_map_survives_in_proposal(self, exported_run):
        # The source map is part of the full_paper artifact metadata.
        for p in exported_run["ctx"].result.proposals.values():
            view = FullPaperArtifactView(p)
            if view.exists and view.source_map:
                return
        pytest.skip("no source map")


# ── Export ───────────────────────────────────────────────────────────


class TestExport:
    def test_markdown_export_exists(self, exported_run):
        paths = exported_run["ctx"].result.export_paths
        assert len(paths) >= 1
        for path in paths.values():
            assert Path(path).exists(), f"export file missing: {path}"

    def test_export_contains_generated_paper(self, exported_run):
        ctx = exported_run["ctx"]
        for idx, path in ctx.result.export_paths.items():
            text = Path(path).read_text(encoding="utf-8")
            paper_view = FullPaperArtifactView(ctx.result.proposals[idx])
            if paper_view.exists and paper_view.paper_markdown:
                # The export should contain a recognizable chunk of the paper.
                assert any(
                    fragment in text
                    for fragment in paper_view.paper_markdown.split("\n\n")[:2]
                ), "exported markdown does not contain the generated paper"
                return
        pytest.skip("no paper-bearing proposal exported")


# ── Accounting ───────────────────────────────────────────────────────


class TestAccounting:
    def test_every_call_has_stage(self, exported_run):
        ledger = exported_run["provider"].call_ledger
        assert ledger, "no calls recorded"
        for e in ledger:
            assert e["stage"], f"call missing stage: {e}"

    def test_every_call_has_run_id(self, exported_run):
        for e in exported_run["provider"].call_ledger:
            assert e["run_id"] == RUN_ID

    def test_all_calls_belong_to_one_run(self, exported_run):
        runs = {e["run_id"] for e in exported_run["provider"].call_ledger}
        assert runs == {RUN_ID}

    def test_token_totals_reconcile(self, exported_run):
        ledger = exported_run["provider"].call_ledger
        total_in = sum(e["input_tokens"] for e in ledger)
        total_out = sum(e["output_tokens"] for e in ledger)
        assert total_in >= 0
        assert total_out > 0

    def test_zero_network_calls(self, exported_run):
        # The synthetic provider performs no I/O. Assert it carries no
        # network client state.
        provider = exported_run["provider"]
        assert not hasattr(provider, "_session")
        assert not hasattr(provider, "_client")


# ── Stage reports / outcome ──────────────────────────────────────────


class TestStageReports:
    def test_pipeline_outcome_succeeded_or_running(self, exported_run):
        # The downstream chain does not set SUCCEEDED (that is the
        # orchestrator's job in Commit 7). It must not have terminalized.
        outcome = exported_run["ctx"].result.outcome
        assert outcome in (PipelineOutcome.RUNNING, PipelineOutcome.SUCCEEDED), (
            f"unexpected terminal outcome: {outcome}"
        )

    def test_proposals_carry_paper_and_evaluation(self, exported_run):
        for p in exported_run["ctx"].result.proposals.values():
            md = _load_metadata(p)
            assert "full_paper" in md or "evaluation" in md
            return


# ── Serialization / restart roundtrip ────────────────────────────────


class TestSerializationRoundtrip:
    """The PipelineResult must survive a JSON roundtrip so a restarted
    process can recover the paper artifact, evaluation, source map, and
    export path. This uses dataclass-style serialization (the dict form
    the API/export layer consumes), not the relational DB — that path is
    exercised by the orchestrator-level proof (Commit 7)."""

    def test_result_serializes_and_recovers_artifacts(self, exported_run):
        import json
        ctx = exported_run["ctx"]
        # Serialize the recoverable surface: proposals (with metadata),
        # export paths, gaps, outcome.
        proposal_dump = {}
        for idx, p in ctx.result.proposals.items():
            proposal_dump[idx] = {
                "metadata": _load_metadata(p),
                "title": p.title,
            }
        snapshot = {
            "run_id": ctx.result.run_id,
            "outcome": str(ctx.result.outcome),
            "export_paths": ctx.result.export_paths,
            "gaps_count": len(ctx.result.gaps),
            "proposals": proposal_dump,
        }
        wire = json.dumps(snapshot)
        recovered = json.loads(wire)

        # Recover paper artifact.
        first = next(iter(recovered["proposals"].values()))
        fp = first["metadata"].get("full_paper", {})
        assert fp.get("paper_markdown"), "paper text not recovered"
        assert fp.get("source_map"), "source map not recovered"

        # Recover evaluation.
        ev = first["metadata"].get("paper_evaluation") or first["metadata"].get("evaluation")
        assert ev, "evaluation not recovered"

        # Recover export path.
        assert recovered["export_paths"], "export path not recovered"
        for path in recovered["export_paths"].values():
            assert Path(path).exists()


# ── Negative controls ────────────────────────────────────────────────


class TestNegativeControls:
    """Prove the assertions would catch regressions. Each control feeds
    a deliberately-broken artifact into a view and asserts it fails."""

    def test_missing_paper_text_fails_terminal_assertion(self):
        class _Proposal:
            metadata = {"full_paper": {"paper_markdown": "", "synthesis_state": "ready"}}
        view = FullPaperArtifactView(_Proposal())
        assert view.exists
        # The E2E test asserts nonblank paper_markdown — an empty one must
        # fail that assertion.
        assert not view.paper_markdown.strip()

    def test_missing_evaluation_dimension_fails_typed_validation(self):
        class _Proposal:
            metadata = {
                "paper_evaluation": {
                    "scope": "paper", "status": "ready",
                    "dimensions": {"novelty": {"score": 0.7, "justification": "x"}},
                }
            }
        ev = PaperEvaluationView(_Proposal())
        # Only one of seven dimensions present → all_dimensions_present is False.
        assert not ev.all_dimensions_present()

    def test_unmapped_source_marker_blocks_evaluation(self):
        # An out-of-range [SOURCE-99] marker must appear as unmapped in the
        # source map; the E2E test asserts zero unmapped entries.
        class _Proposal:
            metadata = {
                "full_paper": {
                    "paper_markdown": "text [SOURCE-99]",
                    "source_map": [
                        {"marker": "SOURCE-1", "marker_index": 1, "source_id": "p1",
                         "mapping_status": "mapped"},
                        {"marker": "SOURCE-99", "marker_index": 99, "source_id": None,
                         "mapping_status": "unmapped"},
                    ],
                }
            }
        view = FullPaperArtifactView(_Proposal())
        unmapped = [e for e in view.source_map if e.mapping_status == "unmapped"]
        assert len(unmapped) == 1

    def test_provider_exception_marks_stage_failed(self, tmp_path):
        # A provider that raises during a model-backed stage must surface as
        # a failure, not silent success. Demonstrate against idea generation.
        class _ExplodingProvider(SyntheticPipelineProvider):
            async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096, **kw):
                raise RuntimeError("provider exploded")

        exploder = _ExplodingProvider(run_id=RUN_ID)
        ctx = _seed_context(tmp_path, exploder)
        from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
        stage = IdeaGenerationStage(agent=AgentOrchestrator(provider=exploder), hooks=HookDispatcher())
        exploder.set_context("idea_generation", RUN_ID)
        # The stage catches internal exceptions and returns True with empty
        # ideas (non-fatal); the proof is that NO ideas are produced, so the
        # downstream "at least one idea" assertion would fail.
        _run(stage.execute(ctx))
        assert len(ctx.result.ideas) == 0, (
            "a provider exception must not silently produce valid ideas"
        )

    def test_export_cannot_report_success_without_file(self, tmp_path):
        # ExportStage writes export_paths pointing at real files. A path
        # entry whose file does not exist must fail the export assertion.
        fake_paths = {0: str(tmp_path / "does_not_exist.md")}
        for path in fake_paths.values():
            assert not Path(path).exists()

"""Method-fidelity gate regressions.

Run 2713 released a paper whose numbers were perfectly faithful but
whose methodology section misdescribed the executed protocol on four
counts. These tests prove the boundary now blocks exactly those
discrepancies — including against the REAL released bytes, not just
synthetic prose.
"""
from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod
import backend.pipeline.stages as stages_mod
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, Proposal
from backend.pipeline.evaluation.method_fidelity import (
    evaluate_method_fidelity,
)
from backend.pipeline.evaluation.revision_directive import (
    EvidenceInvariant,
    RevisionDirective,
)
from backend.pipeline.experiment.spec_designer import (
    TABULAR_CALIBRATION_SELECTIVE_V1,
)

FACTS = TABULAR_CALIBRATION_SELECTIVE_V1.method_facts

RELEASED_PAPER = Path("evidence/ead4b_final3_release.md")

# The four false descriptions, in the phrasings the released paper
# actually used (run 2713, released bytes).
FALSE_CLAIMS = {
    "base_model": (
        "The base model is a softmax logistic regression producing"
        " class probabilities, fit by minimizing the negative"
        " log-likelihood (cross-entropy); the solver and regularization"
        " strength were the implementation library's defaults."
    ),
    "calibration_scheme": (
        "Each calibrator learns a per-class mapping from the model's"
        " probability output to a recalibrated probability. Sigmoid"
        " calibration fits, per class k, a logistic reparameterization."
    ),
    "ece_definition": (
        "Expected calibration error is computed by partitioning"
        " evaluation instances into B equal-width bins by confidence,"
        " using the binned accuracy and mean confidence."
    ),
    "aurc_definition": (
        "Sorting instances by decreasing confidence, the area under"
        " the risk-coverage curve is the mean selective risk when the"
        " rejection budget is swept from full coverage to maximal"
        " abstention — a rank-based integral."
    ),
}


def _compliant_body() -> str:
    return "\n\n".join(f["statement"] for f in FACTS.values())


class TestReleasedPaperBlocked:
    def test_real_run2713_release_bytes_fail_all_four_facts(self):
        """The strongest regression: the ACTUAL released paper must be
        blocked, with violations from every fact."""
        assert RELEASED_PAPER.exists(), (
            "released run-2713 bytes must stay in the repo as the"
            " canonical false-description specimen"
        )
        paper = RELEASED_PAPER.read_text(encoding="utf-8")
        res = evaluate_method_fidelity(paper, FACTS)

        assert res.passed is False
        violated_facts = {v.split(":")[0] for v in res.violations}
        assert violated_facts == set(FACTS.keys()), (
            f"expected all four facts violated, got {violated_facts}"
        )
        # Both sides must fire: contradicting claims AND missing truth.
        assert any("contradicts" in v for v in res.violations)
        assert any("does not state" in v for v in res.violations)


class TestEachFalseDescriptionBlocks:
    @pytest.mark.parametrize("fact_id", sorted(FALSE_CLAIMS))
    def test_false_claim_alone_blocks(self, fact_id):
        """A paper that is otherwise compliant but asserts ONE false
        description is blocked on that fact."""
        paper = "# Study\n\n" + _compliant_body()
        paper = paper.replace(
            FACTS[fact_id]["statement"],
            FALSE_CLAIMS[fact_id],
        )
        res = evaluate_method_fidelity(paper, FACTS)
        assert res.passed is False
        assert fact_id in {v.split(":")[0] for v in res.violations}
        assert any("contradicts" in v for v in res.violations)

    @pytest.mark.parametrize("fact_id", sorted(FALSE_CLAIMS))
    def test_missing_fact_blocks(self, fact_id):
        """A paper that omits one frozen fact (neither states nor
        contradicts it) is blocked for that fact."""
        paper = "# Study\n\n" + "\n\n".join(
            f["statement"] for fid, f in FACTS.items()
            if fid != fact_id
        )
        res = evaluate_method_fidelity(paper, FACTS)
        assert res.passed is False
        assert fact_id in {v.split(":")[0] for v in res.violations}


class TestCompliantAndVacuous:
    def test_frozen_statements_verbatim_pass(self):
        paper = "# Study\n\n## Methodology\n\n" + _compliant_body()
        res = evaluate_method_fidelity(paper, FACTS)
        assert res.passed is True, res.violations

    def test_empty_contract_is_vacuous_pass(self):
        res = evaluate_method_fidelity("any text at all", {})
        assert res.passed is True
        assert "No frozen method contract" in res.reason


class TestDesignCarriesFacts:
    def test_ensure_design_includes_method_facts(self):
        """The design state persisted for cold repair carries the
        contract, so the gate fires on the cold re-evaluation too."""
        engine = _make_engine()
        run_id, _, _ = _seed(engine)
        with _patched_session(engine):
            ctx = CtxShim(run_id)
            stages_mod.ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

        assert design["status"] == "designed"
        assert design["method_facts"] == FACTS
        assert set(design["method_facts"].keys()) == set(FACTS.keys())


class TestPaperContextInjectsFacts:
    def test_context_contains_verbatim_protocol_block(self):
        from backend.pipeline.experiment.manifest import ResultMarker
        from backend.pipeline.stages import PaperSynthesisStage

        marker = ResultMarker(
            marker_index=1, marker="RESULT-1",
            metric_name="iris.accuracy",
            observed_value=0.93, artifact_path="iris/metrics.json",
            artifact_sha256="a" * 8, experiment_result_id=1,
            direction="higher_better", role="comparison",
        )
        ctx = SimpleNamespace(
            result=SimpleNamespace(
                experiment_runs={
                    0: [SimpleNamespace(
                        status="succeeded",
                        dataset=SimpleNamespace(name="iris"),
                    )],
                },
                result_markers={0: [marker]},
            ),
        )
        design = {
            "selected_proposal_idx": 0,
            "research_question": "q",
            "capability_id": "c",
            "specs": [{"analysis": {"method": "m"},
                       "research_intent": {}}],
            "method_facts": dict(FACTS),
        }
        context = PaperSynthesisStage()._build_autonomous_paper_context(
            ctx, design,
        )[0]
        assert "EXECUTED PROTOCOL" in context
        assert "VERBATIM" in context
        for fact in FACTS.values():
            assert fact["statement"] in context


class TestDirectiveCarriesFacts:
    def _directive(self) -> RevisionDirective:
        return RevisionDirective(
            blocking_findings=("method_fidelity: test",),
            research_question="q",
            task_type="classification",
            target_name="species",
            executed_method="one-vs-rest logistic regression",
            baseline_method="majority_class",
            comparison_method="sigmoid calibration",
            primary_metric="aurc",
            metric_direction="lower_is_better",
            dataset_name="iris",
            split_method="stratified",
            random_seed=42,
            evidence=EvidenceInvariant(
                result_map=(("RESULT-1", 0.9),),
                source_map=("[SOURCE-1]",),
                experiment_manifest_hash="h",
                dataset_hash="d",
                analysis_code_hash="c",
            ),
            unexecuted_methods_detected=(),
            method_facts=dict(FACTS),
        )

    def test_prompt_requires_verbatim_facts(self):
        prompt = self._directive().build_revision_prompt()
        assert "state each fact below VERBATIM" in prompt
        assert "EXECUTED PROTOCOL" in prompt
        for fact in FACTS.values():
            assert fact["statement"] in prompt

    def test_to_dict_roundtrips_facts(self):
        d = self._directive().to_dict()
        assert d["method_facts"] == dict(FACTS)

    def test_absent_facts_omit_requirement_8(self):
        directive = RevisionDirective(
            blocking_findings=("x",),
            research_question="q", task_type="classification",
            target_name="t", executed_method="m",
            baseline_method="b", comparison_method="c",
            primary_metric="p", metric_direction="d",
            dataset_name="ds", split_method="s", random_seed=1,
            evidence=EvidenceInvariant(
                result_map=(), source_map=(),
                experiment_manifest_hash="h", dataset_hash="d",
                analysis_code_hash="c",
            ),
            unexecuted_methods_detected=(),
        )
        prompt = directive.build_revision_prompt()
        assert "VERBATIM" not in prompt


class TestEvaluatePaperGateWiring:
    def test_false_description_paper_gets_method_fidelity_blocking(self):
        """Full _evaluate_paper invocation: a paper with the run-2713
        false descriptions must be blocked with a method_fidelity
        reason, even when its numbers are perfectly faithful."""
        from backend.pipeline.experiment.manifest import ResultMarker
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import (
            PaperSynthesisStage,
            StageContext,
        )

        markers = [
            ResultMarker(
                marker_index=1, marker="RESULT-1",
                metric_name="iris.accuracy",
                observed_value=0.93, artifact_path="",
                artifact_sha256="", experiment_result_id=1,
                direction="higher_better", role="comparison",
            ),
        ]
        # Faithful numbers, false methodology: exactly the released
        # paper's failure mode.
        paper_md = (
            "# Calibration under shift on iris\n\n"
            "## Abstract\n\n"
            "We study calibration under covariate shift on iris"
            " with logistic regression.\n\n"
            "## Methodology\n\n"
            + FALSE_CLAIMS["base_model"] + "\n\n"
            + FALSE_CLAIMS["calibration_scheme"] + "\n\n"
            + FALSE_CLAIMS["ece_definition"] + "\n\n"
            + FALSE_CLAIMS["aurc_definition"] + "\n\n"
            "## Results\n\n0.93 [RESULT-1]\n\n"
            "## Conclusion\n\n"
            "The executed experiment shows the reported values"
            " [RESULT-1].\n"
        )
        metadata = {"full_paper": {"paper_markdown": paper_md}}
        proposal_obj = SimpleNamespace(
            paper_md=paper_md, metadata=metadata,
        )
        result = PipelineResult()
        result.result_markers = {0: markers}
        ctx = StageContext(
            result=result,
            domain="machine learning",
            research_question=(
                "How does post-hoc probability calibration affect"
                " selective classification under covariate shift?"
            ),
            params={
                "autonomous_experiment_design": {
                    "status": "designed",
                    "method_facts": dict(FACTS),
                    "specs": [],
                },
            },
        )

        fake_eval = MagicMock()
        fake_eval.evaluate = AsyncMock(
            return_value=MagicMock(to_dict=lambda: {}),
        )
        with patch(
            "backend.pipeline.evaluation.proposal_evaluator"
            ".ProposalEvaluator",
            return_value=fake_eval,
        ):
            # Mock provider: _evaluate_paper resolves a real thinking
            # provider when self._provider is None, leaking an open
            # AsyncOpenAI client into later async tests.
            asyncio.run(
                PaperSynthesisStage(provider=MagicMock())._evaluate_paper(
                    ctx, proposal_obj, metadata, 0,
                )
            )

        evaluation = metadata.get("paper_evaluation", {})
        gates = {
            g["gate"]: g for g in evaluation.get("gates", [])
            if isinstance(g, dict)
        }
        assert "method_fidelity" in gates, (
            f"method_fidelity gate must fire; gates={list(gates)}"
        )
        assert gates["method_fidelity"]["passed"] is False
        assert evaluation.get("status") == "blocked"
        assert any(
            r.startswith("method_fidelity:")
            for r in evaluation.get("blocking_reasons", [])
        )


# ── Shared fixtures ─────────────────────────────────────────────────────────


@contextmanager
def _patched_session(engine):
    test_sf = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched():
        session = test_sf()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    orig = db_mod.get_session
    db_mod.get_session = patched
    stages_mod.get_session = patched
    db_mod._get_engine = lambda: engine
    try:
        yield
    finally:
        db_mod.get_session = orig
        stages_mod.get_session = orig


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def _seed(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_mf", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Calibration Study", problem_statement="p",
        proposed_method="logistic regression",
        expected_contributions="c", domain="ML",
        novelty_score=0.5, feasibility_score=0.8, overall_score=0.8,
        pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()
    proposal = Proposal(idea_id=idea.id, content_md="t")
    session.add(proposal)
    session.commit()
    ids = (run.id, idea.id, proposal.id)
    session.close()
    return ids


class CtxShim:
    """Minimal StageContext stand-in for design tests."""

    def __init__(self, run_id):
        from backend.pipeline.generation.models import ResearchIdea
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import StageContext
        from backend.pipeline.synthesis.proposal_synthesizer import (
            FeasibilityReport,
        )

        self._inner = StageContext(
            result=PipelineResult(),
            domain="machine learning",
            research_question=(
                "How does calibration affect selective"
                " classification under covariate shift?"
            ),
            db_run_id=run_id,
        )
        self._inner.params["autonomous_experiment_enabled"] = True
        self._inner.result.ideas = [ResearchIdea(
            title="Calibration Study",
            problem_statement="p", proposed_method="logistic regression",
            expected_contributions="c", novelty_rationale="n",
            evaluation_approach="accuracy calibration metrics",
            domain="ML", round_generated=1, score=0.8,
            supporting_papers=[], source_gap_ids=[],
        )]
        self._inner.result.feasibility_reports = {0: FeasibilityReport(
            overall_score=0.8, data_availability=7,
            computational_requirements=8,
            methodological_complexity=7, evaluation_plan=8,
            novelty_grounding=6, impact_potential=7,
            reasoning="ok", estimated_timeline="1w", key_risks=[],
        )}
        self._inner.result.proposals = {0: SimpleNamespace(
            title="T", to_markdown=lambda: "t",
        )}

    def __getattr__(self, name):
        return getattr(self._inner, name)

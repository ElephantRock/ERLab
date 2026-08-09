"""R1 — Assurance integrity: non-vacuous experiment-alignment after remediation.

Regression tests proving that _evaluate_paper() hydrates persisted result
markers when the live StageContext doesn't carry them, so the
experiment-alignment gate performs a real check rather than passing vacuously.

Four cases:
1. Live pipeline context — markers present; no DB fallback; unchanged.
2. Post-remediation context — transient markers empty, persisted evidence
   exists; markers hydrated; gate is non-vacuous.
3. Wrong-result negative test — post-remediation paper deliberately
   misattributes a result; experiment-alignment must fail.
4. Non-empirical proposal — no registered experiment; "No experiment
   results" path remains valid.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import pytest

from backend.db.database import Base
from backend.db.models import Proposal, Idea, ExperimentResult
from backend.pipeline.stages import PaperSynthesisStage, StageContext
from backend.pipeline.result import PipelineResult


VALID_EVAL_TEXT = (
    "NOVELTY_SCORE: 0.7\nNOVELTY_JUSTIFICATION: Novel.\n"
    "FEASIBILITY_SCORE: 0.7\nFEASIBILITY_JUSTIFICATION: Feasible.\n"
    "COMPLETENESS_SCORE: 0.7\nCOMPLETENESS_JUSTIFICATION: Complete.\n"
    "RIGOR_SCORE: 0.7\nRIGOR_JUSTIFICATION: Rigorous.\n"
    "CLARITY_SCORE: 0.7\nCLARITY_JUSTIFICATION: Clear.\n"
    "BASELINE_ADEQUACY_SCORE: 0.7\nBASELINE_ADEQUACY_JUSTIFICATION: Adequate.\n"
    "COMPUTE_REALISM_SCORE: 0.7\nCOMPUTE_REALISM_JUSTIFICATION: Realistic.\n"
    "OVERALL_SCORE: 0.7\n"
)


class StubProvider:
    """Returns a fixed valid evaluation."""
    default_model = "test-evaluator"

    async def complete(self, messages, **kwargs):
        return VALID_EVAL_TEXT


CORRECT_PAPER = (
    "# Logistic Regression on Iris\n\n"
    "## Abstract\n"
    "Logistic regression achieves balanced_accuracy of 0.966667 [RESULT-3], "
    "compared to the majority-class baseline at 0.333333 [RESULT-1], "
    "for an absolute improvement of 0.633333 [RESULT-2].\n\n"
    "## Conclusion\n"
    "The logistic regression model outperformed the majority-class baseline "
    "on the Iris dataset.\n"
)

WRONG_PAPER = (
    "# Quantum Solver on Iris\n\n"
    "## Abstract\n"
    "The variational quantum linear solver achieves balanced_accuracy of "
    "0.966667 [RESULT-3].\n\n"
    "## Conclusion\n"
    "Our quantum method is superior.\n"
)


def _make_manifest():
    """Persisted experiment manifest matching phase5-pilot-v1."""
    return json.dumps({
        "status": "succeeded",
        "experiment_spec_id": "phase5-pilot-v1",
        "results": {
            "baseline_accuracy": 0.333333,
            "model_accuracy": 0.966667,
            "improvement": 0.633333,
        },
        "result_artifacts": [
            {"artifact_type": "metrics", "filename": "metrics.json", "sha256": "abc123"},
        ],
    })


@pytest.fixture
def isolated_db():
    """In-memory SQLite with monkey-patched get_session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    import backend.db.database as dbmod
    old_engine = dbmod._engine
    old_factory = dbmod._session_factory
    dbmod._engine = engine
    dbmod._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine
    dbmod._engine = old_engine
    dbmod._session_factory = old_factory


def _create_proposal_with_experiment(isolated_db, paper_md):
    """Create a proposal with persisted experiment evidence."""
    from backend.db.database import get_session
    with get_session() as session:
        idea = Idea(
            title="R1 Test", problem_statement="test",
            proposed_method="logistic regression", domain="ML",
            overall_score=0.0,
        )
        session.add(idea)
        session.flush()

        meta = {
            "full_paper": {"paper_markdown": paper_md, "source_map": []},
            "paper_evaluation": {"status": "pending", "scope": "paper"},
        }

        proposal = Proposal(
            idea_id=idea.id,
            paper_md=paper_md,
            paper_meta_json=json.dumps(meta),
            content_md="", content_latex="",
            references_json="[]", sections_json="{}",
            proposal_evaluation_json="",
        )
        session.add(proposal)
        session.flush()

        exp = ExperimentResult(
            idea_id=idea.id,
            proposal_id=proposal.id,
            code_md="",
            manifest_json=_make_manifest(),
            success=True,
        )
        session.add(exp)
        session.commit()
        return proposal.id


def _ctx(*, experiment_spec_id=None, result_markers=None, proposals=None):
    result = PipelineResult()
    if result_markers:
        for idx, markers in result_markers.items():
            result.result_markers[idx] = markers
    if proposals:
        result.proposals = proposals
    params = {}
    if experiment_spec_id:
        params["experiment_spec_id"] = experiment_spec_id
    return StageContext(
        result=result, domain="machine learning",
        research_question="Can logistic regression classify Iris?",
        params=params,
    )


# ─── Case 1: Live pipeline context ─────────────────────────────


@pytest.mark.asyncio
async def test_live_context_markers_used_no_fallback(isolated_db):
    """When ctx.result.result_markers has live markers, the gate uses them
    and does not fall back to DB hydration."""
    from backend.pipeline.experiment.manifest import ResultMarker

    markers = [
        ResultMarker(
            marker_index=1, marker="RESULT-1",
            metric_name="baseline_accuracy", observed_value=0.333333,
            artifact_path="", artifact_sha256="", experiment_result_id=1,
        )
    ]

    proposal_id = _create_proposal_with_experiment(isolated_db, CORRECT_PAPER)

    stage = PaperSynthesisStage(provider=StubProvider())
    from backend.db.database import get_session
    with get_session() as session:
        from sqlalchemy import text as sa_text
        row = session.execute(sa_text(
            f"SELECT paper_meta_json FROM proposals WHERE id = {proposal_id}"
        )).fetchone()
        meta = json.loads(row[0])

    ctx = _ctx(
        experiment_spec_id="phase5-pilot-v1",
        result_markers={proposal_id: markers},
        proposals={proposal_id: SimpleNamespace()},
    )
    proposal_obj = SimpleNamespace(paper_md=CORRECT_PAPER, metadata=meta)

    with patch.object(
        PaperSynthesisStage, '_hydrate_persisted_result_markers',
        return_value=[],
    ) as mock_hydrate:
        await stage._evaluate_paper(ctx, proposal_obj, meta, proposal_id)
        mock_hydrate.assert_not_called()

    eval_data = meta.get("paper_evaluation", {})
    exp_gate = next(
        (g for g in eval_data.get("gates", []) if isinstance(g, dict) and g.get("gate") == "experiment_alignment"),
        {},
    )
    assert "No experiment results" not in exp_gate.get("reason", "")


# ─── Case 2: Post-remediation context ──────────────────────────


@pytest.mark.asyncio
async def test_post_remediation_hydrates_markers_from_db(isolated_db):
    """When ctx markers are empty but persisted evidence exists, markers
    are hydrated and the gate performs a real check."""
    proposal_id = _create_proposal_with_experiment(isolated_db, CORRECT_PAPER)

    stage = PaperSynthesisStage(provider=StubProvider())
    from backend.db.database import get_session
    with get_session() as session:
        from sqlalchemy import text as sa_text
        row = session.execute(sa_text(
            f"SELECT paper_meta_json FROM proposals WHERE id = {proposal_id}"
        )).fetchone()
        meta = json.loads(row[0])

    # Post-remediation: empty ctx, no proposals dict, no result_markers
    ctx = _ctx(experiment_spec_id="phase5-pilot-v1")
    proposal_obj = SimpleNamespace(paper_md=CORRECT_PAPER, metadata=meta)

    await stage._evaluate_paper(ctx, proposal_obj, meta, proposal_id)

    eval_data = meta.get("paper_evaluation", {})
    exp_gate = next(
        (g for g in eval_data.get("gates", []) if isinstance(g, dict) and g.get("gate") == "experiment_alignment"),
        {},
    )
    reason = exp_gate.get("reason", "")
    assert "No experiment results" not in reason, (
        f"Gate passed vacuously! reason={reason}"
    )
    assert eval_data.get("paper_hash") == hashlib.sha256(CORRECT_PAPER.encode()).hexdigest()


# ─── Case 3: Wrong-result negative test ────────────────────────


@pytest.mark.asyncio
async def test_wrong_attribution_fails_after_hydration(isolated_db):
    """A post-remediation paper that claims quantum (unexecuted method)
    must fail experiment-alignment after hydration, not pass vacuously."""
    proposal_id = _create_proposal_with_experiment(isolated_db, WRONG_PAPER)

    stage = PaperSynthesisStage(provider=StubProvider())
    from backend.db.database import get_session
    with get_session() as session:
        from sqlalchemy import text as sa_text
        row = session.execute(sa_text(
            f"SELECT paper_meta_json FROM proposals WHERE id = {proposal_id}"
        )).fetchone()
        meta = json.loads(row[0])

    ctx = _ctx(experiment_spec_id="phase5-pilot-v1")
    proposal_obj = SimpleNamespace(paper_md=WRONG_PAPER, metadata=meta)

    await stage._evaluate_paper(ctx, proposal_obj, meta, proposal_id)

    eval_data = meta.get("paper_evaluation", {})
    exp_gate = next(
        (g for g in eval_data.get("gates", []) if isinstance(g, dict) and g.get("gate") == "experiment_alignment"),
        {},
    )
    assert not exp_gate.get("passed", True), (
        f"Wrong-method paper passed experiment_alignment! gate={exp_gate}"
    )


# ─── Case 4: Non-empirical proposal ────────────────────────────


@pytest.mark.asyncio
async def test_non_empirical_paper_keeps_valid_no_results_path(isolated_db):
    """When no experiment_spec_id is registered, the 'No experiment results'
    path is legitimate and must remain unchanged."""
    from backend.db.database import get_session
    with get_session() as session:
        idea = Idea(
            title="Non-empirical", problem_statement="test",
            proposed_method="survey", domain="NLP",
            overall_score=0.0,
        )
        session.add(idea)
        session.flush()
        meta = {
            "full_paper": {"paper_markdown": "# Survey of NLP\n\n## Abstract\nA survey.\n"},
            "paper_evaluation": {"status": "pending"},
        }
        proposal = Proposal(
            idea_id=idea.id, paper_md="# Survey of NLP\n\n## Abstract\nA survey.\n",
            paper_meta_json=json.dumps(meta),
            content_md="", content_latex="",
            references_json="[]", sections_json="{}",
            proposal_evaluation_json="",
        )
        session.add(proposal)
        session.commit()
        pid = proposal.id

    stage = PaperSynthesisStage(provider=StubProvider())
    from backend.db.database import get_session
    with get_session() as session:
        from sqlalchemy import text as sa_text
        row = session.execute(sa_text(
            f"SELECT paper_meta_json FROM proposals WHERE id = {pid}"
        )).fetchone()
        meta2 = json.loads(row[0])

    # No experiment_spec_id
    ctx = _ctx(experiment_spec_id=None)
    proposal_obj = SimpleNamespace(paper_md="# Survey of NLP\n\n## Abstract\nA survey.\n", metadata=meta2)

    await stage._evaluate_paper(ctx, proposal_obj, meta2, pid)

    eval_data = meta2.get("paper_evaluation", {})
    exp_gate = next(
        (g for g in eval_data.get("gates", []) if isinstance(g, dict) and g.get("gate") == "experiment_alignment"),
        {},
    )
    reason = exp_gate.get("reason", "")
    assert reason == "Not an empirical run", (
        f"Non-empirical gate should say 'Not an empirical run', got: {reason}"
    )

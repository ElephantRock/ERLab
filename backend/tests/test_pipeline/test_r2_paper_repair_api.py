"""R2 — Autonomous paper repair API regression tests.

Tests the eligibility checks, blocking-findings derivation, and repair
operation through the product API contract.

Cases:
1. Blocked + exact evaluation → repair allowed
2. Ready paper → repair rejected
3. Stale evaluation hash → repair rejected
4. No paper → repair rejected
5. No evaluation → repair rejected
6. Blocking findings derived from evaluation dimensions
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.routes.ideas import _derive_blocking_findings
from backend.db.database import Base
from backend.db.models import ExperimentResult, Idea, Proposal


@pytest.fixture
def isolated_db():
    """In-memory SQLite with StaticPool so all sessions share one connection."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    import backend.db.database as dbmod
    old_engine = dbmod._engine
    old_factory = dbmod._session_factory
    dbmod._engine = engine
    dbmod._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine
    dbmod._engine = old_engine
    dbmod._session_factory = old_factory


def _create_proposal(isolated_db, *, paper_md="", eval_status="blocked",
                      eval_hash=None, has_experiment=False):
    """Create a proposal with specified evaluation and experiment state."""
    from backend.db.database import get_session

    if eval_hash is None and paper_md:
        eval_hash = hashlib.sha256(paper_md.encode()).hexdigest()

    meta = {
        "full_paper": {"paper_markdown": paper_md, "source_map": []},
        "paper_evaluation": {
            "status": eval_status,
            "scope": "paper",
            "paper_hash": eval_hash or "",
        },
    }
    if has_experiment:
        meta["experiment_spec_id"] = "phase5-pilot-v1"

    with get_session() as session:
        idea = Idea(
            title="R2 Test", problem_statement="test",
            proposed_method="logistic regression", domain="ML",
            overall_score=0.0,
        )
        session.add(idea)
        session.flush()

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

        if has_experiment:
            manifest = json.dumps({
                "status": "succeeded",
                "experiment_spec_id": "phase5-pilot-v1",
                "results": {"baseline_accuracy": 0.333, "model_accuracy": 0.967, "improvement": 0.633},
                "result_artifacts": [{"artifact_type": "metrics", "filename": "metrics.json", "sha256": "abc"}],
            })
            exp = ExperimentResult(
                idea_id=idea.id, proposal_id=proposal.id,
                code_md="", manifest_json=manifest, success=True,
            )
            session.add(exp)

        session.commit()
        return idea.id, proposal.id


# ─── Blocking-findings derivation ───────────────────────────────


class TestDeriveBlockingFindings:
    def test_extracts_low_scoring_dimensions(self):
        eval_data = {
            "dimensions": {
                "clarity": {"score": 0.3, "justification": "Formatting artifacts"},
                "novelty": {"score": 0.1, "justification": "Textbook exercise"},
                "feasibility": {"score": 1.0, "justification": "Trivially implementable"},
            },
            "blocking_reasons": [],
        }
        findings = _derive_blocking_findings(eval_data)
        # Only dimensions with score < 0.5 should produce findings
        finding_text = " ".join(findings)
        assert "clarity" in finding_text
        assert "novelty" in finding_text
        assert "feasibility" not in finding_text

    def test_includes_blocking_reasons(self):
        eval_data = {
            "dimensions": {},
            "blocking_reasons": ["provenance: no source map"],
        }
        findings = _derive_blocking_findings(eval_data)
        assert any("provenance" in f for f in findings)

    def test_empty_evaluation_produces_generic_finding(self):
        findings = _derive_blocking_findings({"dimensions": {}, "blocking_reasons": []})
        assert len(findings) >= 1
        assert "blocked" in findings[0].lower()


# ─── Eligibility checks ─────────────────────────────────────────


class TestRepairEligibility:
    @pytest.mark.asyncio
    async def test_ready_paper_rejected(self, isolated_db):
        from backend.api.errors import ConflictError
        from backend.api.routes.ideas import repair_paper

        paper = "# Ready Paper\n\n## Abstract\nGood paper."
        idea_id, prop_id = _create_proposal(
            isolated_db, paper_md=paper, eval_status="ready",
        )

        with pytest.raises(ConflictError) as exc_info:
            await repair_paper(idea_id)
        assert "not 'blocked'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_paper_rejected(self, isolated_db):
        from backend.api.errors import ConflictError
        from backend.api.routes.ideas import repair_paper

        idea_id, prop_id = _create_proposal(
            isolated_db, paper_md="", eval_status="blocked",
        )

        with pytest.raises(ConflictError):
            await repair_paper(idea_id)

    @pytest.mark.asyncio
    async def test_stale_hash_rejected(self, isolated_db):
        from backend.api.errors import ConflictError
        from backend.api.routes.ideas import repair_paper

        paper = "# Paper\n\nContent."
        idea_id, prop_id = _create_proposal(
            isolated_db,
            paper_md=paper,
            eval_status="blocked",
            eval_hash="0" * 64,  # wrong hash
        )

        with pytest.raises(ConflictError) as exc_info:
            await repair_paper(idea_id)
        assert "Stale" in str(exc_info.value) or "stale" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_experiment_rejected(self, isolated_db):
        from backend.api.errors import ConflictError
        from backend.api.routes.ideas import repair_paper

        paper = "# Blocked Paper\n\n## Abstract\nBlocked."
        idea_id, prop_id = _create_proposal(
            isolated_db,
            paper_md=paper,
            eval_status="blocked",
            has_experiment=False,
        )

        with pytest.raises(ConflictError) as exc_info:
            await repair_paper(idea_id)
        assert "experiment" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_blocked_with_exact_hash_and_experiment_passes_eligibility(self, isolated_db):
        """A blocked paper with matching hash and persisted experiment should
        pass the eligibility checks and reach the remediator.

        We verify by checking that the remediator is called (via spy) rather
        than running a full live LLM repair."""
        from backend.api.routes.ideas import repair_paper

        paper = "# Blocked Paper\n\n## Abstract\nLogistic regression on Iris."
        idea_id, prop_id = _create_proposal(
            isolated_db,
            paper_md=paper,
            eval_status="blocked",
            has_experiment=True,
        )

        mock_result = SimpleNamespace(
            # PAC contract: the remediator is a candidate producer —
            # a screening-ready candidate returns promoted=False with
            # eval_status="ready"; the route is the promotion authority.
            success=True, promoted=False, revision_number=1,
            eval_status="ready", gates=[], blocking_reasons=[],
            original_paper_hash=hashlib.sha256(paper.encode()).hexdigest(),
            revised_paper_hash="abc123",
            invariant_violations=[],
        )

        # Verify the experiment exists from a fresh session
        from sqlalchemy import text as _verify_text

        from backend.db.database import get_session as _verify_session
        with _verify_session() as s:
            rows = s.execute(_verify_text(
                "SELECT id, idea_id, proposal_id FROM experiment_results"
            )).fetchall()
            print(f"Experiments in DB: {rows}")
            print(f"Looking for idea_id={idea_id}")

        with patch(
            "backend.pipeline.evaluation.paper_remediator.auto_revise_paper",
            new=AsyncMock(return_value=mock_result),
        ) as mock_remediator:
            # The endpoint imports auto_revise_paper inside the function body
            # via `from ... import auto_revise_paper`, which binds the name
            # locally. Patching the source module attribute ensures the
            # from-import picks up the mock at call time.
            with patch(
                "backend.pipeline.stages.PaperSynthesisStage._evaluate_paper",
                new=AsyncMock(),
            ):
                with patch(
                    "backend.providers.provider_factory.create_provider",
                    return_value=SimpleNamespace(default_model="mock"),
                ):
                    try:
                        result = await repair_paper(idea_id)
                        mock_remediator.assert_called_once()
                        assert result["repair"]["success"] is True
                    except Exception as exc:
                        import traceback
                        traceback.print_exc()
                        pytest.fail(f"repair_paper raised: {type(exc).__name__}: {exc}")


def get_session_mock(paper_md, prop_id):
    """Context manager that mocks get_session to return the paper for evaluation."""
    from contextlib import contextmanager

    from backend.db.database import get_session

    @contextmanager
    def mock_get_session():
        # Just use the real session — the test DB is already set up
        with get_session() as session:
            yield session

    return patch("backend.api.routes.ideas.get_session", side_effect=mock_get_session)

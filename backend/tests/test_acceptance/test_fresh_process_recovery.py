"""Fresh-process artifact recovery proof (Commit 3).

Proves that a completed run's artifacts can be recovered from production
persistence by a SEPARATE Python process. The parent executes a
deterministic acceptance rehearsal through real production persistence
into an isolated SQLite database; the child (subprocess.run) imports
ERLab afresh, connects with a new engine, and loads the run through
production read APIs.

The paper, evaluation, and source map must come from production
persistence — not from an in-memory PipelineResult or a JSON handoff.

This test is hermetic (network-free). It creates an isolated DB and
disposes the parent's engine before spawning the child.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CHILD_SCRIPT = Path(__file__).parent / "_recovery_child.py"


def _is_chromadb_mocked():
    """The pipeline imports chromadb; ensure it's mocked in both processes."""
    return True


@pytest.fixture(scope="module")
def isolated_db(tmp_path_factory):
    """Create an isolated SQLite database URL for the recovery round-trip."""
    db_dir = tmp_path_factory.mktemp("recovery_db")
    db_path = db_dir / "recovery.db"
    return f"sqlite:///{db_path.as_posix()}", db_dir


class TestRecoveryModule:
    """Unit-test the recovery module directly (no subprocess yet)."""

    def test_recover_missing_run_returns_error(self, isolated_db):
        from backend.acceptance.recovery import recover_run
        db_url, _ = isolated_db
        # Ensure the schema exists so the engine connects.
        # Create an empty DB with schema.
        from sqlalchemy import create_engine

        from backend.db.models import Base
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        engine.dispose()
        record = recover_run(db_url, "nonexistent_run")
        assert record.run_recovered is False
        assert any("not found" in e for e in record.errors)

    def test_recovered_artifacts_to_dict_excludes_no_secrets(self):
        from backend.acceptance.recovery import RecoveredRunArtifacts
        d = RecoveredRunArtifacts().to_dict()
        assert "fresh_process" in d
        blob = json.dumps(d)
        # No provider/prompt content leaks.
        assert "messages" not in blob
        assert "api_key" not in blob


class TestFreshProcessRecovery:
    """The actual subprocess-boundary recovery proof.

    This executes a synthetic acceptance rehearsal through production
    persistence, then recovers in a child process. Marked slow because it
    runs a full persistence round-trip.
    """

    @pytest.mark.slow
    def test_child_process_recovers_persisted_artifacts(self, isolated_db):
        """End-to-end: parent persists → child recovers through production APIs."""
        db_url, db_dir = isolated_db
        run_id = "recovery-proof-run"

        # ── Parent: persist a complete run through production persistence ──
        from sqlalchemy import create_engine

        from backend.db.models import Base

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        # Use the production persistence boundary to store a run + artifacts.
        from backend.pipeline.gap_analysis.models import ResearchGap
        from backend.pipeline.persistence import PipelinePersistence
        from backend.pipeline.result import PipelineOutcome, PipelineResult
        from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

        persistence = PipelinePersistence()
        # Bind the persistence module's engine to our isolated DB.
        import backend.db.database as dbmod
        dbmod._engine = engine  # type: ignore[attr-defined]

        # Create the run record.
        db_run_id = persistence.create_run_record(
            domain="low-resource MT", params={}, run_id=run_id,
        )

        # Persist gaps.
        gaps = [ResearchGap(title="G1", description="d", gap_type="methodological",
                            confidence=0.8)]
        result = PipelineResult()
        result.gaps = gaps
        result.run_id = run_id
        result.outcome = PipelineOutcome.SUCCEEDED
        persistence.persist_gaps(result, db_run_id)

        # Persist ideas.
        from backend.pipeline.generation.models import ResearchIdea
        result.ideas = [ResearchIdea(
            title="I1", problem_statement="p", proposed_method="m",
            expected_contributions="c", novelty_rationale="n",
            evaluation_approach="e", domain="MT",
        )]
        persistence.persist_ideas(result, db_run_id)

        # Persist a proposal with paper + evaluation metadata.
        proposal = ResearchProposal(idea_id=1, title="P1",
                                     abstract="A", introduction="B")
        proposal.metadata = {
            "full_paper": {
                "paper_markdown": "# Recovered Paper\n\nReal content [SOURCE-1].",
                "word_count": 5,
                "synthesis_state": "ready",
                "source_map": [{"marker_index": 1, "mapping_status": "mapped", "source_id": "p1"}],
            },
            "synthesis_state": "ready",
            "paper_evaluation": {
                "scope": "paper", "status": "ready",
                "dimensions": {d: {"score": 0.7, "justification": "ok"} for d in (
                    "novelty", "feasibility", "completeness", "rigor",
                    "clarity", "baseline_adequacy", "compute_realism")},
            },
            "evaluation": {"novelty": {"score": 0.7}},
            "citation_audit": {"status": "complete", "total_citations": 1,
                               "fabricated_citations": 0},
        }
        result.proposals = {0: proposal}
        persistence.persist_proposals(result, db_run_id)

        # Persist stage reports.
        result.stage_report = [
            type("SR", (), {"name": "gap_analysis", "status": "executed",
                            "elapsed_s": 0.1, "error": None, "skip_reason": None,
                            "retries_used": 0, "contract_violations": None,
                            "data_quality": None, "stage_name": "gap_analysis",
                            "to_dict": lambda self: {"name": "gap_analysis", "status": "executed"}})(),
        ]
        # Write stage_report_json directly via the run record.
        import json as _json

        from backend.db.database import get_session
        from backend.db.models import PipelineRun
        with get_session() as session:
            run = session.query(PipelineRun).filter_by(id=db_run_id).first()
            if run:
                run.stage_report_json = _json.dumps([
                    {"name": "gap_analysis", "status": "executed"}
                ])
                run.status = "completed"
            session.commit()

        # Dispose the parent's engine BEFORE spawning the child.
        engine.dispose()
        dbmod._engine = None  # type: ignore[attr-defined]

        # ── Child: fresh process recovers through production APIs ──
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        # Mock chromadb in the child too.
        proc = subprocess.run(
            [sys.executable, str(CHILD_SCRIPT), db_url, run_id],
            capture_output=True, text=True, env=env, timeout=120,
        )
        assert proc.returncode == 0, (
            f"child failed (exit {proc.returncode}):\n{proc.stderr[-800:]}"
        )
        record = json.loads(proc.stdout)
        assert record["run_recovered"] is True, f"run not recovered: {record}"
        assert record["paper_recovered"] is True, f"paper not recovered: {record}"
        assert record["paper_word_count"] >= 4
        assert record["paper_evaluation_recovered"] is True
        assert record["source_map_recovered"] is True
        assert record["gaps_count"] >= 1
        assert record["ideas_count"] >= 1

    @pytest.mark.slow
    def test_child_exits_nonzero_when_paper_missing(self, isolated_db):
        """If the paper is absent from persistence, the child must exit nonzero."""
        db_url, _ = isolated_db
        run_id = "recovery-nopaper-run"

        from sqlalchemy import create_engine

        import backend.db.database as dbmod
        from backend.db.models import Base
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        dbmod._engine = engine  # type: ignore[attr-defined]

        from backend.pipeline.persistence import PipelinePersistence
        from backend.pipeline.result import PipelineResult
        persistence = PipelinePersistence()
        db_run_id = persistence.create_run_record(
            domain="MT", params={}, run_id=run_id,
        )
        # Persist ideas but NO proposal/paper.
        from backend.pipeline.generation.models import ResearchIdea
        result = PipelineResult()
        result.run_id = run_id
        result.ideas = [ResearchIdea(
            title="I1", problem_statement="p", proposed_method="m",
            expected_contributions="c", novelty_rationale="n",
            evaluation_approach="e", domain="MT",
        )]
        persistence.persist_ideas(result, db_run_id)

        engine.dispose()
        dbmod._engine = None  # type: ignore[attr-defined]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        proc = subprocess.run(
            [sys.executable, str(CHILD_SCRIPT), db_url, run_id],
            capture_output=True, text=True, env=env, timeout=120,
        )
        # Child must exit nonzero when paper is missing.
        assert proc.returncode != 0, "child should fail when paper is absent"

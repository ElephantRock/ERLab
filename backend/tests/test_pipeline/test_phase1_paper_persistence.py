"""Phase 1 1C/1D focused tests: paper persistence + state + evaluation scope.

Covers spec 1G backend cases 4–8:
  4. Paper synthesis produces or exposes a non-empty final artifact.
  5. Empty paper output is not marked ready.
  6. The API returns the correct paper for the run (via _serialize_paper_state).
  7. Paper evaluation consumes the final paper artifact (scope=paper).
  8. Proposal and paper evaluation scopes remain distinct.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from backend.api.routes.ideas import _serialize_paper_state
from backend.pipeline.persistence import _extract_paper_artifact


def _proposal_with_paper(paper_md=None, meta=None, full_paper_key_present=True):
    """Build a lightweight stand-in for a ResearchProposal carrying metadata
    in the shape PaperSynthesisStage writes."""
    metadata: dict = {}
    if full_paper_key_present:
        if paper_md is None and meta is None:
            metadata["full_paper"] = None  # explicit failure path
        elif paper_md is None:
            metadata["full_paper"] = {}  # empty dict
        else:
            metadata["full_paper"] = {
                "paper_markdown": paper_md,
                "word_count": (meta or {}).get("word_count"),
                "venue": (meta or {}).get("venue"),
                "synthesis_strategy": (meta or {}).get("synthesis_strategy"),
            }
    return SimpleNamespace(metadata=metadata)


# ── Case 4: non-empty paper is extracted and ready ──


def test_1g_04_nonempty_paper_extracted_and_ready():
    proposal = _proposal_with_paper(paper_md="# Title\n\nReal body content here.", meta={"word_count": 5})
    paper_md, meta = _extract_paper_artifact(proposal)
    assert paper_md is not None and "Real body content" in paper_md
    assert meta["status"] == "ready"
    assert meta["word_count"] == 5


# ── Case 5: empty paper is NOT marked ready ──


def test_1g_05_empty_paper_marked_failed_not_ready():
    """Whitespace-only paper markdown -> failed, not ready, no paper_md."""
    proposal = _proposal_with_paper(paper_md="   \n\n  \t  ")
    paper_md, meta = _extract_paper_artifact(proposal)
    assert paper_md is None
    assert meta is not None
    assert meta["status"] == "failed"


def test_1g_05b_explicit_failure_path_marked_failed():
    """PaperSynthesisStage sets metadata['full_paper'] = None on failure."""
    proposal = _proposal_with_paper(paper_md=None, meta=None)  # full_paper = None
    paper_md, meta = _extract_paper_artifact(proposal)
    assert paper_md is None
    assert meta["status"] == "failed"


def test_1g_05c_absent_full_paper_key_leaves_column_null():
    """When the paper stage didn't run (fast_scan), full_paper key is absent
    and the artifact is (None, None) so the column stays NULL rather than
    being written as a failed paper."""
    proposal = _proposal_with_paper(full_paper_key_present=False)
    paper_md, meta = _extract_paper_artifact(proposal)
    assert paper_md is None
    assert meta is None


# ── Case 6: API serialization returns the correct paper state ──


def _idea(run_id=1):
    return SimpleNamespace(id=10, title="An idea", pipeline_run_id=run_id)


def test_1g_06_ready_paper_serialized():
    proposal = SimpleNamespace(
        paper_md="# Paper\n\nBody.",
        paper_meta_json=json.dumps({"status": "ready", "word_count": 2}),
    )
    state = _serialize_paper_state(proposal, _idea())
    assert state["status"] == "ready"
    assert state["paper_md"] == "# Paper\n\nBody."
    assert state["word_count"] == 2
    assert state["source_run_id"] == 1


def test_1g_06b_no_proposal_paper_capable_strategy_is_pending():
    """Proposal not yet persisted but strategy includes paper synthesis -> pending."""
    state = _serialize_paper_state(None, _idea(run_id=None))
    # run_id None -> conservative True -> pending
    assert state["status"] == "pending"
    assert state["paper_md"] is None


def test_1g_06c_failed_paper_serialized_as_failed():
    proposal = SimpleNamespace(
        paper_md=None,
        paper_meta_json=json.dumps({"status": "failed"}),
    )
    state = _serialize_paper_state(proposal, _idea())
    assert state["status"] == "failed"
    assert state["paper_md"] is None


# ── Case 7: paper evaluation consumes the final paper (scope=paper) ──


def test_1g_07_paper_evaluation_carried_in_meta():
    """_extract_paper_artifact folds paper_evaluation into paper_meta_json."""
    proposal = SimpleNamespace(
        metadata={
            "full_paper": {"paper_markdown": "# Paper body"},
            "paper_evaluation": {
                "status": "ready",
                "scope": "paper",
                "evaluated_object": "final_paper",
                "dimensions": {"novelty": {"score": 0.7}},
            },
        }
    )
    _, meta = _extract_paper_artifact(proposal)
    assert meta["paper_evaluation"]["scope"] == "paper"
    assert meta["paper_evaluation"]["evaluated_object"] == "final_paper"
    assert meta["paper_evaluation"]["dimensions"]["novelty"]["score"] == 0.7


# ── Case 8: proposal and paper evaluation scopes remain distinct ──


def test_1g_08_paper_evaluation_scope_is_distinct_from_proposal():
    """The paper evaluation is explicitly labeled scope=paper; the proposal
    evaluation (which runs earlier in EvaluationStage) is a separate object.
    These must never be collapsed."""
    proposal = SimpleNamespace(
        paper_md="# Paper",
        paper_meta_json=json.dumps(
            {
                "status": "ready",
                "paper_evaluation": {"status": "ready", "scope": "paper"},
            }
        ),
    )
    state = _serialize_paper_state(proposal, _idea())
    paper_eval = state["paper_evaluation"]
    assert paper_eval is not None
    assert paper_eval["scope"] == "paper"
    # The proposal evaluation lives elsewhere in the idea-detail response
    # (mechanical_metrics / quality_checks), never under paper_evaluation.
    assert "proposal" not in (paper_eval or {})

"""Release-final lifecycle for the canonical research paper.

The live ``Proposal.paper_md`` remains the canonical *current* paper.  A
release-final paper is an immutable ``PaperRevision`` snapshot referenced from
``Proposal.paper_meta_json['release']``.  Later corrections may advance the
current paper, but they never rewrite the frozen revision; a later explicit
freeze moves the release pointer to a newly assured revision.

No schema change is required: PaperRevision already provides append-only
content/version history and paper_meta_json already owns paper lifecycle
metadata.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from backend.db.models import PaperRevision, Proposal

RELEASE_META_KEY = "release"
RELEASE_STATE_FROZEN = "frozen"


class PaperReleaseError(ValueError):
    """The current paper is not eligible for a release-final transition."""


def compute_paper_hash(paper_md: str) -> str:
    return hashlib.sha256((paper_md or "").encode("utf-8")).hexdigest()


def load_paper_meta(proposal: Proposal) -> dict:
    raw = getattr(proposal, "paper_meta_json", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def write_paper_meta(proposal: Proposal, meta: dict) -> None:
    proposal.paper_meta_json = json.dumps(meta)


def release_metadata(proposal: Proposal) -> dict | None:
    release = load_paper_meta(proposal).get(RELEASE_META_KEY)
    return release if isinstance(release, dict) else None


def merge_release_metadata(existing_proposal: Proposal, new_meta: dict | None) -> dict | None:
    """Carry an existing release pointer through whole-metadata replacements."""
    existing_release = release_metadata(existing_proposal)
    if not existing_release:
        return new_meta
    merged = dict(new_meta or {})
    merged[RELEASE_META_KEY] = dict(existing_release)
    return merged


def _next_revision_number(session, proposal_id: int) -> int:
    current = session.execute(
        select(func.max(PaperRevision.revision_number)).where(
            PaperRevision.proposal_id == proposal_id
        )
    ).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


def _latest_revision(session, proposal_id: int) -> PaperRevision | None:
    return session.execute(
        select(PaperRevision)
        .where(PaperRevision.proposal_id == proposal_id)
        .order_by(PaperRevision.revision_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def _matching_ready_revision(
    session, proposal_id: int, paper_hash: str
) -> PaperRevision | None:
    return session.execute(
        select(PaperRevision)
        .where(
            PaperRevision.proposal_id == proposal_id,
            PaperRevision.paper_hash == paper_hash,
            PaperRevision.eval_status == "ready",
        )
        .order_by(PaperRevision.revision_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def _fresh_ready_evaluation(meta: dict, paper_hash: str) -> tuple[bool, list[dict]]:
    evaluation = meta.get("paper_evaluation")
    if not isinstance(evaluation, dict):
        return False, []
    if evaluation.get("status") != "ready":
        return False, []
    if evaluation.get("blocking_reasons"):
        return False, []
    # Release-final is deliberately fail-closed: the evaluation must identify
    # the exact current content. Legacy evaluations without a paper_hash remain
    # viewable/exportable but are not release-eligible until re-evaluated.
    if evaluation.get("paper_hash") != paper_hash:
        return False, []
    gates = evaluation.get("gates")
    return True, gates if isinstance(gates, list) else []


def release_status(session, proposal: Proposal) -> dict:
    paper_md = (getattr(proposal, "paper_md", None) or "").strip()
    current_hash = compute_paper_hash(paper_md) if paper_md else None
    meta = load_paper_meta(proposal)
    release = meta.get(RELEASE_META_KEY)

    fresh_ready = False
    if current_hash:
        fresh_ready, _ = _fresh_ready_evaluation(meta, current_hash)
        if not fresh_ready:
            fresh_ready = _matching_ready_revision(
                session, proposal.id, current_hash
            ) is not None

    if isinstance(release, dict) and release.get("state") == RELEASE_STATE_FROZEN:
        frozen_hash = release.get("frozen_paper_hash")
        return {
            **release,
            "release_eligible": bool(fresh_ready),
            "current_paper_hash": current_hash,
            "current_matches_frozen": bool(current_hash and current_hash == frozen_hash),
        }

    return {
        "state": "release_eligible" if fresh_ready else "mutable",
        "release_eligible": bool(fresh_ready),
        "current_paper_hash": current_hash,
        "current_matches_frozen": False,
    }


def freeze_current_paper(session, proposal: Proposal) -> dict:
    """Freeze the exact current assured paper as the release-final revision.

    Idempotent for an already-frozen identical hash. A later assured current
    version can be frozen again; the previous frozen PaperRevision remains
    immutable in history and the release pointer advances to a new snapshot.
    """
    paper_md = getattr(proposal, "paper_md", None) or ""
    if not paper_md.strip():
        raise PaperReleaseError("Cannot freeze: no non-empty paper exists")

    current_hash = compute_paper_hash(paper_md)
    meta = load_paper_meta(proposal)
    existing_release = meta.get(RELEASE_META_KEY)
    if (
        isinstance(existing_release, dict)
        and existing_release.get("state") == RELEASE_STATE_FROZEN
        and existing_release.get("frozen_paper_hash") == current_hash
    ):
        return release_status(session, proposal)

    eval_ready, gates = _fresh_ready_evaluation(meta, current_hash)
    matching_revision = None
    if not eval_ready:
        matching_revision = _matching_ready_revision(session, proposal.id, current_hash)
        if matching_revision is None:
            raise PaperReleaseError(
                "Cannot freeze: current paper has no assurance result bound to its exact content"
            )
        if matching_revision.gates_json:
            try:
                parsed = json.loads(matching_revision.gates_json)
                gates = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                gates = []

    latest = _latest_revision(session, proposal.id)
    revision_number = _next_revision_number(session, proposal.id)
    frozen_at = datetime.now(UTC)
    revision = PaperRevision(
        proposal_id=proposal.id,
        experiment_result_id=(
            matching_revision.experiment_result_id
            if matching_revision is not None
            else meta.get("experiment_result_id")
        ),
        revision_number=revision_number,
        parent_revision_id=latest.id if latest else None,
        paper_md=paper_md,
        paper_hash=current_hash,
        source="release",
        trigger="release_freeze",
        trigger_detail_json=json.dumps({"frozen_at": frozen_at.isoformat()}),
        eval_status="ready",
        gates_json=json.dumps(gates),
    )
    session.add(revision)
    session.flush()

    release = {
        "state": RELEASE_STATE_FROZEN,
        "frozen_revision_id": revision.id,
        "frozen_revision_number": revision.revision_number,
        "frozen_paper_hash": current_hash,
        "frozen_at": frozen_at.isoformat(),
    }
    meta[RELEASE_META_KEY] = release
    write_paper_meta(proposal, meta)
    session.flush()
    return release_status(session, proposal)


def load_frozen_revision(session, proposal: Proposal) -> PaperRevision:
    release = release_metadata(proposal)
    if not release or release.get("state") != RELEASE_STATE_FROZEN:
        raise PaperReleaseError("No release-final paper has been frozen")
    revision_id = release.get("frozen_revision_id")
    if revision_id is None:
        raise PaperReleaseError("Frozen release metadata has no revision identity")
    revision = session.get(PaperRevision, int(revision_id))
    if revision is None or revision.proposal_id != proposal.id:
        raise PaperReleaseError("Frozen release revision is unavailable")
    expected_hash = release.get("frozen_paper_hash")
    if expected_hash != revision.paper_hash or compute_paper_hash(revision.paper_md) != revision.paper_hash:
        raise PaperReleaseError("Frozen release revision failed content-hash verification")
    return revision


def record_successor_revision_if_released(
    session,
    proposal: Proposal,
    new_paper_md: str | None,
    *,
    eval_status: str,
    gates: list[dict] | None = None,
    source: str,
    trigger: str,
    experiment_result_id: int | None = None,
) -> PaperRevision | None:
    """Record a post-release current-paper successor without moving the release pointer.

    This is a no-op until a release has been frozen. It is also idempotent for
    an already-recorded identical successor hash.
    """
    release = release_metadata(proposal)
    if not release or release.get("state") != RELEASE_STATE_FROZEN:
        return None
    paper_md = new_paper_md or ""
    if not paper_md.strip():
        return None
    new_hash = compute_paper_hash(paper_md)
    if new_hash == release.get("frozen_paper_hash"):
        return None

    existing = session.execute(
        select(PaperRevision)
        .where(
            PaperRevision.proposal_id == proposal.id,
            PaperRevision.paper_hash == new_hash,
        )
        .order_by(PaperRevision.revision_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    latest = _latest_revision(session, proposal.id)
    revision = PaperRevision(
        proposal_id=proposal.id,
        experiment_result_id=experiment_result_id,
        revision_number=_next_revision_number(session, proposal.id),
        parent_revision_id=latest.id if latest else release.get("frozen_revision_id"),
        paper_md=paper_md,
        paper_hash=new_hash,
        source=source,
        trigger=trigger,
        eval_status=eval_status,
        gates_json=json.dumps(gates or []),
    )
    session.add(revision)
    session.flush()
    return revision

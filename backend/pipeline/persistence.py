"""Pipeline DB persistence operations."""

import json
import hashlib
import logging
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path("./data/checkpoints")


# ═════════════════════════════════════════════════════════════════
# P0.1: Corpus Provenance Types
# ═════════════════════════════════════════════════════════════════


@dataclass
class SearchQueryData:
    """Logical query data for persistence. query_key is pre-computed."""

    query_text: str
    query_type: str  # template | llm_generated
    generation_origin: str  # base | llm
    sequence_number: int
    query_key: str


@dataclass
class DiscoveryMetadata:
    """One route through which a paper was found.

    P0.2.5: Governed remote discoveries carry execution_id, source_result_key,
    and linkage_schema_version. Legacy/non-query discoveries leave them NULL.
    """

    query_key: str
    source: str  # openalex | arxiv | crossref | pubmed | etc.
    execution_id: int | None = None
    source_result_key: str | None = None
    source_record_id: str | None = None
    source_rank: int | None = None
    discovery_origin: str = "remote_search"
    canonicalization_method: str | None = None
    linkage_schema_version: str | None = None


@dataclass
class CandidateWithDiscoveries:
    """A deduplicated paper candidate with ALL its discovery routes preserved."""

    paper: Any  # backend.pipeline.literature.models.Paper
    discoveries: list[DiscoveryMetadata] = field(default_factory=list)


def compute_query_key(
    query_text: str, query_type: str, generation_origin: str, sequence_number: int
) -> str:
    """Deterministic query key from normalized logical content.

    Stable across retries: the same logical query rebuilt as a new Python
    object produces the same key. Uses NFKC normalization + casefold.
    """
    normalized = unicodedata.normalize("NFKC", query_text)
    normalized = " ".join(normalized.strip().casefold().split())
    raw = f"{normalized}|{query_type}|{generation_origin}|{sequence_number}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _normalize_source_record_id(source: str, source_record_id: str | None) -> str:
    """Source-aware normalization for discovery_key computation.

    DOI: case-insensitive. PubMed/arXiv/OpenAlex IDs: trim only.
    Unknown: trim only, preserve case.
    """
    if not source_record_id:
        return ""
    sid = source_record_id.strip()
    if source.lower() in ("doi", "crossref") or sid.startswith("10."):
        return sid.lower()
    return sid


def compute_discovery_key(
    run_id: int,
    paper_id: int,
    query_key: str,
    source: str,
    source_record_id: str | None,
    discovery_origin: str,
) -> str:
    """Deterministic discovery key for idempotent replay."""
    raw = "|".join([
        str(run_id),
        str(paper_id),
        query_key,
        source.strip().lower(),
        _normalize_source_record_id(source, source_record_id),
        discovery_origin.strip().lower(),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# Current checkpoint schema version. Bump when the checkpoint
# format changes in a backwards-incompatible way.
# - v1: original format (run_id, state, stages, domain, params)
# - v2: adds schema_version, model_receipts, resource_epoch,
#       collector_record_ids, typed failure_class
CHECKPOINT_SCHEMA_VERSION = 2


class CheckpointPersistenceError(Exception):
    """Typed error for checkpoint save/load failures.

    Checkpoint persistence errors must fail the stage, not produce
    a warning-only success.
    """


class IncompatibleCheckpointError(CheckpointPersistenceError):
    """Raised when a checkpoint has an incompatible schema version."""

    def __init__(self, run_id: str, found_version: int, expected_version: int) -> None:
        self.run_id = run_id
        self.found_version = found_version
        self.expected_version = expected_version
        super().__init__(
            f"Checkpoint for run '{run_id}' has schema version {found_version}, "
            f"but this code expects version {expected_version}. "
            f"The checkpoint is incompatible and cannot be loaded."
        )


class contextlib_suppress:
    """Minimal context manager to suppress exceptions without importing contextlib."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return True


def normalize_title(title: str) -> str:
    """Normalize a gap title for dedup hashing (BATCH-42, HB-02)."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def content_hash(title: str) -> str:
    """SHA-256 hash of normalized title (BATCH-42, HB-01)."""
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()


def _extract_paper_artifact(proposal, result_markers=None) -> tuple[str | None, dict | None]:
    """Phase 1 1C: extract the synthesized full paper + metadata from a
    ResearchProposal as written by PaperSynthesisStage.

    PaperSynthesisStage stores the result under proposal.metadata["full_paper"]
    as a dict (monolithic path) or sets it to None on failure (failure paths).
    This helper normalizes both shapes into (paper_md, paper_meta).

    Phase 7H: also captures experiment linkage (experiment_result_id,
    result_markers map, selection metadata) from the proposal metadata so the
    RESULT-marker linkage is durable across restart, not in-memory only.

    Truth rule (WP-1C): an empty/placeholder paper is recorded with
    status="failed", never "ready", so the API can never surface an empty
    artifact as a successful paper.

    Returns (None, None) when no paper stage ran (e.g. fast_scan strategy) so
    the column stays NULL rather than being written as a failed paper.
    """
    raw_meta = getattr(proposal, "metadata", None)
    if raw_meta is None:
        return None, None
    if isinstance(raw_meta, str):
        try:
            meta_dict = json.loads(raw_meta)
        except Exception:
            return None, None
    elif isinstance(raw_meta, dict):
        meta_dict = raw_meta
    else:
        return None, None

    full_paper = meta_dict.get("full_paper")
    # A missing/absent full_paper key means the paper stage did not run for
    # this proposal (e.g. fast_scan). Leave the column NULL.
    if full_paper is None and "full_paper" not in meta_dict:
        # Phase 7H: even without a paper, a non-selected proposal carries
        # durable selection state (experiment_status, paper_status, selection
        # metadata). Persist this minimal metadata so the selection contract
        # survives restart.
        if meta_dict.get("experiment_status") == "not_selected_for_experiment":
            return None, {
                "status": "not_requested",
                "experiment_status": meta_dict.get("experiment_status"),
                "paper_status": meta_dict.get("paper_status", "not_requested"),
            }
        return None, None
    # Paper stage ran but explicitly failed -> record as failed (no markdown).
    if not full_paper or not isinstance(full_paper, dict):
        return None, {"status": "failed", "generated_at": None}

    paper_md = full_paper.get("paper_markdown") or ""
    # Truth rule: empty/whitespace paper is failed, not ready.
    if not paper_md.strip():
        return None, {"status": "failed", "generated_at": None}

    meta = {
        "status": "ready",
        "word_count": full_paper.get("word_count"),
        "venue": full_paper.get("venue"),
        "model_used": full_paper.get("model_used"),
        "source_count": full_paper.get("source_count"),
        "synthesis_strategy": full_paper.get("synthesis_strategy"),
        "sections_generated": full_paper.get("sections_generated"),
        "sections_total": full_paper.get("sections_total"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # Phase 1 1D: paper-level evaluation (scope=paper), written by
        # PaperSynthesisStage._evaluate_paper. Stored under paper_meta_json
        # so the API can expose it alongside the paper state.
        "paper_evaluation": meta_dict.get("paper_evaluation"),
        # Phase 4 / WP-4C: the frozen marker→source map. Each entry is
        # {marker_index, marker, source_id, mapping_status}. source_id is the
        # literature Paper.id; persist_proposals resolves it to papers.id and
        # writes one paper_source_markers row per entry.
        "source_map": full_paper.get("source_map") or [],
    }

    # Phase 7H: durable RESULT-marker linkage. Each entry resolves a paper
    # [RESULT-N] marker to its experiment_result_id, metric_id, observed_value,
    # and artifact hash. This must survive restart — the paper text alone is
    # insufficient to resolve markers after a reload.
    if result_markers:
        meta["result_markers"] = [
            {
                "marker": m.marker,
                "marker_index": m.marker_index,
                "metric_id": m.metric_name,
                "observed_value": m.observed_value,
                "experiment_result_id": m.experiment_result_id,
                "artifact_path": m.artifact_path,
                "artifact_sha256": m.artifact_sha256,
                # Phase 8 / D3: structural direction metadata
                "direction": getattr(m, "direction", ""),
                "role": getattr(m, "role", ""),
                "derived_from": getattr(m, "derived_from", ""),
            }
            for m in result_markers
        ]
        # Link the paper to the experiment row
        if result_markers[0].experiment_result_id:
            meta["experiment_result_id"] = result_markers[0].experiment_result_id

    return paper_md, meta


def _extract_proposal_evaluation(proposal) -> str | None:
    """Phase 2 2B: extract the proposal-scope evaluation from a ResearchProposal.

    EvaluationStage writes metadata["evaluation"] = evaluation.to_dict() (the
    7-dim ProposalEvaluation). Previously persist_proposals dropped it, so the
    proposal evaluation was lost on every run. Returns a JSON string (or None
    when no evaluation ran) for storage in Proposal.proposal_evaluation_json.

    Scope is explicitly proposal (distinct from paper_evaluation, which is
    stored under paper_meta_json).
    """
    raw_meta = getattr(proposal, "metadata", None)
    if raw_meta is None:
        return None
    if isinstance(raw_meta, str):
        try:
            meta_dict = json.loads(raw_meta)
        except Exception:
            return None
    elif isinstance(raw_meta, dict):
        meta_dict = raw_meta
    else:
        return None
    evaluation = meta_dict.get("evaluation")
    if not evaluation or not isinstance(evaluation, dict):
        return None
    return json.dumps(evaluation)


class PipelinePersistence:
    """Handles all database writes for pipeline runs."""

    def __init__(self):
        self.warnings: list[str] = []

    def get_warnings(self) -> list[str]:
        return self.warnings.copy()

    def create_run_record(self, domain: str, params: dict, session_id: str | None = None, run_id: str | None = None) -> int | None:
        try:
            from backend.db import crud
            from backend.db.database import get_session
            from sqlalchemy import select as sa_select, update as sa_update
            from backend.db.models import PipelineRun as _PR

            with get_session() as session:
                # Check if record already exists (created by run_svc.create_run)
                if run_id:
                    existing = session.execute(
                        sa_select(_PR).where(_PR.run_id_str == run_id)
                    ).scalar_one_or_none()
                    if existing:
                        # Update existing record to 'running'
                        existing.status = "running"
                        existing.current_stage = "initializing"
                        existing.config_json = json.dumps(params)
                        session.commit()
                        return existing.id

                # No existing record — create new
                db_run = crud.create_pipeline_run(
                    session,
                    domain=domain,
                    status="running",
                    current_stage="initializing",
                    config_json=json.dumps(params),
                    session_id=session_id,
                    run_id_str=run_id,
                )
                return db_run.id
        except Exception as e:
            logger.warning("Failed to create DB run record: %s", e)
            self.warnings.append(f"create_run_record: {e}")
            return None

    def persist_gaps(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.gaps:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                for gap in result.gaps:
                    gap_kwargs = {
                        "title": gap.title,
                        "description": gap.description,
                        "gap_type": gap.gap_type,
                        "confidence": gap.confidence,
                        "potential_impact": gap.potential_impact,
                        "pipeline_run_id": db_run_id,
                    }
                    # Write truth value columns when present (BATCH-38)
                    if hasattr(gap, "truth") and gap.truth is not None:
                        gap_kwargs["truth_frequency"] = gap.truth.frequency
                        gap_kwargs["truth_confidence"] = gap.truth.confidence
                        gap_kwargs["truth_evidence_count"] = gap.truth.evidence_count
                    # Write related_clusters as JSON array (BATCH-38)
                    if hasattr(gap, "related_clusters") and gap.related_clusters:
                        gap_kwargs["related_clusters"] = json.dumps(gap.related_clusters)
                    # Deduplication: check content_hash (BATCH-42)
                    c_hash = content_hash(gap.title)
                    existing = crud.find_gap_by_hash(session, c_hash)
                    if existing:
                        # Revise truth values using OpenNARS rule (HB-03)
                        from backend.pipeline.knowledge.truth import TruthValue
                        new_truth = TruthValue.from_observation(frequency=gap.confidence)
                        if hasattr(gap, "truth") and gap.truth is not None:
                            new_truth = gap.truth
                        revised = TruthValue(
                            frequency=existing.truth_frequency,
                            confidence=existing.truth_confidence,
                            evidence_count=existing.truth_evidence_count,
                        ).revise(new_truth)
                        existing.truth_frequency = revised.frequency
                        existing.truth_confidence = revised.confidence
                        existing.truth_evidence_count = revised.evidence_count
                        session.commit()
                        logger.info("Revised truth for duplicate gap: %s (hash=%s)", gap.title[:50], c_hash[:12])
                        continue
                    gap_kwargs["content_hash"] = c_hash
                    gap_kwargs["canonical_id"] = c_hash  # First occurrence is canonical
                    crud.create_gap(session, **gap_kwargs)
        except Exception as e:
            logger.warning("Failed to persist gaps: %s", e)
            self.warnings.append(f"persist_gaps: {e}")

    def persist_papers(self, papers: list, db_run_id: int | None) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                for paper in papers:
                    if not crud.get_paper_by_source_id(session, paper.id):
                        crud.create_paper(
                            session,
                            source_id=paper.id,
                            source=paper.source,
                            title=paper.title,
                            abstract=paper.abstract,
                            authors=json.dumps([a.name for a in paper.authors])
                            if paper.authors
                            else "[]",
                            year=paper.year,
                            venue=paper.venue,
                            citation_count=paper.citation_count,
                            url=paper.url,
                            doi=paper.doi,
                            arxiv_id=paper.arxiv_id,
                            keywords=json.dumps(paper.keywords) if paper.keywords else "[]",
                        )
        except Exception as e:
            logger.warning("Failed to persist papers: %s", e)
            self.warnings.append(f"persist_papers: {e}")

    def ensure_search_queries(
        self,
        search_queries: list[SearchQueryData],
        db_run_id: int,
    ) -> dict[str, int]:
        """Idempotently persist logical queries in one short transaction.

        P0.2.2: Resolves search_query_id BEFORE the search fan-out so the
        execution recorder can link execution rows to the correct query.
        Uses a dedicated short transaction (NOT the governed corpus boundary).

        Returns ``query_key -> search_query_id`` mapping. The later
        ``persist_search_results`` call will find these rows already present
        (its select-then-insert-if-absent loop handles this).

        When ``db_run_id`` is falsy, returns an empty dict (no-op).
        """
        if not db_run_id:
            return {}

        from sqlalchemy import select as sa_select

        from backend.db.database import get_session
        from backend.db.models import SearchQuery as SearchQueryModel

        query_ids_by_key: dict[str, int] = {}
        try:
            with get_session() as session:
                for sq_data in search_queries:
                    existing_sq = session.execute(
                        sa_select(SearchQueryModel).where(
                            SearchQueryModel.run_id == db_run_id,
                            SearchQueryModel.query_key == sq_data.query_key,
                        )
                    ).scalar_one_or_none()

                    if existing_sq:
                        query_ids_by_key[sq_data.query_key] = existing_sq.id
                    else:
                        new_sq = SearchQueryModel(
                            run_id=db_run_id,
                            query_key=sq_data.query_key,
                            query_text=sq_data.query_text,
                            query_type=sq_data.query_type,
                            generation_origin=sq_data.generation_origin,
                            sequence_number=sq_data.sequence_number,
                        )
                        session.add(new_sq)
                        session.flush()
                        query_ids_by_key[sq_data.query_key] = new_sq.id
                session.commit()
        except Exception as e:
            logger.warning("Failed to ensure search queries: %s", e)
            self.warnings.append(f"ensure_search_queries: {e}")
            return {}
        return query_ids_by_key

    def persist_search_results(
        self,
        candidates: list[CandidateWithDiscoveries],
        search_queries: list[SearchQueryData],
        db_run_id: int,
        execution_linkage_expectations: list | None = None,
    ) -> None:
        """Single governed persistence boundary for literature search results.

        P0.1: Persists search queries, run-paper membership, and discovery
        provenance in one transaction. Idempotent via deterministic keys.
        All-or-nothing on failure (transactional integrity).

        Args:
            candidates: deduplicated papers with preserved discovery routes
            search_queries: logical queries to persist
            db_run_id: integer PK of the pipeline run
        """
        if not db_run_id:
            return
        try:
            from sqlalchemy import select as sa_select

            from backend.db import crud
            from backend.db.database import get_session
            from backend.db.models import (
                Paper as DBPaper,
                SearchQuery as SearchQueryModel,
                RunPaper,
                PaperDiscovery,
            )

            with get_session() as session:
                # ── 1. Persist search queries (idempotent, flush-only) ──
                query_ids_by_key: dict[str, int] = {}

                for sq_data in search_queries:
                    existing_sq = session.execute(
                        sa_select(SearchQueryModel).where(
                            SearchQueryModel.run_id == db_run_id,
                            SearchQueryModel.query_key == sq_data.query_key,
                        )
                    ).scalar_one_or_none()

                    if existing_sq:
                        query_ids_by_key[sq_data.query_key] = existing_sq.id
                    else:
                        new_sq = SearchQueryModel(
                            run_id=db_run_id,
                            query_key=sq_data.query_key,
                            query_text=sq_data.query_text,
                            query_type=sq_data.query_type,
                            generation_origin=sq_data.generation_origin,
                            sequence_number=sq_data.sequence_number,
                        )
                        session.add(new_sq)
                        session.flush()
                        query_ids_by_key[sq_data.query_key] = new_sq.id

                # ── 2. For each candidate: paper + membership + discoveries
                # All operations use flush (NOT commit) so the governed
                # boundary stays in one uncommitted transaction.
                for candidate in candidates:
                    paper = candidate.paper

                    # 2a. Resolve or create canonical Paper (flush-only)
                    db_paper = crud.get_paper_by_source_id(session, paper.id)
                    if not db_paper:
                        # P0.1.1: Use add_paper (non-committing) not create_paper.
                        # create_paper calls session.commit() which would
                        # commit ALL pending state mid-transaction, breaking
                        # the governed boundary.
                        db_paper = crud.add_paper(
                            session,
                            source_id=paper.id,
                            source=paper.source,
                            title=paper.title,
                            abstract=paper.abstract,
                            authors=json.dumps([a.name for a in paper.authors])
                            if paper.authors
                            else "[]",
                            year=paper.year,
                            venue=paper.venue,
                            citation_count=paper.citation_count,
                            url=paper.url,
                            doi=paper.doi,
                            arxiv_id=paper.arxiv_id,
                            keywords=json.dumps(paper.keywords) if paper.keywords else "[]",
                        )

                    paper_db_id = db_paper.id

                    # 2b. Upsert RunPaper membership (flush-only)
                    existing_rp = session.execute(
                        sa_select(RunPaper).where(
                            RunPaper.run_id == db_run_id,
                            RunPaper.paper_id == paper_db_id,
                        )
                    ).scalar_one_or_none()

                    if not existing_rp:
                        new_rp = RunPaper(
                            run_id=db_run_id,
                            paper_id=paper_db_id,
                            inclusion_origin=candidate.discoveries[0].discovery_origin
                            if candidate.discoveries
                            else "remote_search",
                        )
                        session.add(new_rp)
                        session.flush()

                    # 2c. Insert PaperDiscovery rows (idempotent via discovery_key)
                    for disc in candidate.discoveries:
                        discovery_key = compute_discovery_key(
                            db_run_id,
                            paper_db_id,
                            disc.query_key,
                            disc.source,
                            disc.source_record_id,
                            disc.discovery_origin,
                        )

                        # Check if this discovery already exists
                        existing_disc = session.execute(
                            sa_select(PaperDiscovery).where(
                                PaperDiscovery.run_id == db_run_id,
                                PaperDiscovery.discovery_key == discovery_key,
                            )
                        ).scalar_one_or_none()

                        if not existing_disc:
                            new_disc = PaperDiscovery(
                                run_id=db_run_id,
                                paper_id=paper_db_id,
                                search_query_id=query_ids_by_key.get(disc.query_key),
                                execution_id=disc.execution_id,
                                source_result_key=disc.source_result_key,
                                linkage_schema_version=disc.linkage_schema_version,
                                source=disc.source,
                                source_record_id=disc.source_record_id,
                                source_rank=disc.source_rank,
                                discovery_origin=disc.discovery_origin,
                                canonicalization_method=disc.canonicalization_method,
                                discovery_key=discovery_key,
                            )
                            session.add(new_disc)

                # ── P0.2.5: Linkage-ledger reconciliation ──
                if execution_linkage_expectations:
                    from backend.db.models import ExecutionDiscoveryLinkage
                    from datetime import datetime, timezone as dt_tz

                    for exp in execution_linkage_expectations:
                        if exp.accounting_status != "reconciled":
                            # Incomplete execution: mark not_applicable if not already
                            existing_ledger = session.execute(
                                sa_select(ExecutionDiscoveryLinkage).where(
                                    ExecutionDiscoveryLinkage.execution_id == exp.execution_id
                                )
                            ).scalar_one_or_none()
                            if existing_ledger and existing_ledger.status == "pending":
                                # Shouldn't happen for incomplete, but handle defensively
                                pass
                            continue

                        # Count actual linked discoveries for this execution
                        linked_count = session.execute(
                            sa_select(PaperDiscovery).where(
                                PaperDiscovery.execution_id == exp.execution_id,
                                PaperDiscovery.linkage_schema_version == "linkage_v1",
                            )
                        ).all()
                        actual_count = len(linked_count)

                        # Conservation check
                        if actual_count != (exp.expected_discovery_count or 0):
                            raise RuntimeError(
                                f"conservation violation for execution {exp.execution_id}: "
                                f"expected {exp.expected_discovery_count} discoveries, "
                                f"found {actual_count}"
                            )

                        # Mark linkage ledger as linked
                        ledger = session.execute(
                            sa_select(ExecutionDiscoveryLinkage).where(
                                ExecutionDiscoveryLinkage.execution_id == exp.execution_id
                            )
                        ).scalar_one_or_none()
                        if ledger and ledger.status == "pending":
                            ledger.status = "linked"
                            ledger.linked_discovery_count = actual_count
                            ledger.completed_at = datetime.now(dt_tz.utc)

                session.commit()
                logger.info(
                    "persist_search_results: %d queries, %d candidates, %d total discoveries for run %d",
                    len(search_queries),
                    len(candidates),
                    sum(len(c.discoveries) for c in candidates),
                    db_run_id,
                )

        except Exception as e:
            logger.warning("Failed to persist search results: %s", e)
            self.warnings.append(f"persist_search_results: {e}")
            raise

    def persist_ideas(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.ideas:
            return
        try:
            from sqlalchemy import select

            from backend.db import crud
            from backend.db.database import get_session
            from backend.db.models import Idea as IdeaModel

            with get_session() as session:
                for i, idea in enumerate(result.ideas):
                    # Idempotency key: stable identity material, not just title.
                    # Uses run_id + content hash of (title + problem + method)
                    # so replaying a stage does not duplicate ideas.
                    idea_idempotency_key = content_hash(
                        f"{db_run_id}|{idea.title}|{getattr(idea, 'problem_statement', '')}"
                    )

                    # Dedup check: use idempotency key (run_id + content hash)
                    existing = session.execute(
                        select(IdeaModel).where(
                            IdeaModel.pipeline_run_id == db_run_id,
                            IdeaModel.source_gap_ids == idea_idempotency_key,
                        ).limit(1)
                    ).scalar_one_or_none()
                    # Fallback: check title match for backwards compat with ideas
                    # persisted before the idempotency key migration.
                    if not existing:
                        existing = session.execute(
                            select(IdeaModel).where(
                                IdeaModel.title == idea.title,
                                IdeaModel.pipeline_run_id == db_run_id,
                            ).limit(1)
                        ).scalar_one_or_none()
                    nov = result.novelty_reports.get(i)
                    feas = result.feasibility_reports.get(i)

                    if existing:
                        # Idea already persisted (e.g., after idea_generation).
                        # If novelty/feasibility data is now available, update scores.
                        if nov or feas:
                            nov_dict = None
                            if nov:
                                nov_dict = {
                                    "method_novelty": nov.method_novelty,
                                    "problem_novelty": nov.problem_novelty,
                                    "domain_transfer": nov.domain_transfer,
                                    "combination_novelty": nov.combination_novelty,
                                    "novelty_arguments": nov.novelty_arguments,
                                }
                            mech = result.mechanical_metrics.get(i)
                            if mech and nov_dict is not None:
                                nov_dict["mechanical_metrics"] = mech
                            elif mech and nov_dict is None:
                                nov_dict = {"mechanical_metrics": mech, "overall_score": None}

                            feas_dict = None
                            if feas:
                                feas_dict = {
                                    "data_availability": feas.data_availability,
                                    "computational_requirements": feas.computational_requirements,
                                    "methodological_complexity": feas.methodological_complexity,
                                    "evaluation_plan": feas.evaluation_plan,
                                    "reasoning": feas.reasoning,
                                    "estimated_timeline": feas.estimated_timeline,
                                }

                            crud.update_idea_scores(
                                session,
                                existing.id,
                                novelty_score=nov.overall_score if nov else None,
                                feasibility_score=feas.overall_score if feas else None,
                                novelty_report=json.dumps(nov_dict) if nov_dict else None,
                                feasibility_report=json.dumps(feas_dict) if feas_dict else None,
                            )
                            logger.info(
                                "Updated scores for idea '%s' (run_id=%s)",
                                idea.title[:50], db_run_id,
                            )
                        else:
                            logger.debug(
                                "Skipping duplicate idea (no new scores): '%s'",
                                idea.title[:50],
                            )
                        continue

                    # getattr guards for IdeaCandidate compatibility (BATCH-75, HB-02)
                    source_gap_ids_raw = getattr(idea, 'source_gap_ids', None)
                    # Store idempotency key if no source gap IDs exist,
                    # or append it to existing gap IDs for replay dedup.
                    if source_gap_ids_raw:
                        gap_ids_json = json.dumps(source_gap_ids_raw)
                    else:
                        gap_ids_json = idea_idempotency_key
                    # novelty_rationale is guarded via getattr even though not persisted yet
                    getattr(idea, 'novelty_rationale', '')

                    db_idea = crud.create_idea(
                        session,
                        title=idea.title,
                        problem_statement=idea.problem_statement,
                        proposed_method=idea.proposed_method,
                        expected_contributions=getattr(idea, 'expected_contributions', ''),
                        domain=getattr(idea, 'domain', 'AI/NLP'),
                        source_gap_ids=gap_ids_json,
                        pipeline_run_id=db_run_id,
                    )
                    if nov or feas:
                        # Build novelty report dict
                        nov_dict = None
                        if nov:
                            nov_dict = {
                                "method_novelty": nov.method_novelty,
                                "problem_novelty": nov.problem_novelty,
                                "domain_transfer": nov.domain_transfer,
                                "combination_novelty": nov.combination_novelty,
                                "novelty_arguments": nov.novelty_arguments,
                            }
                        # Merge mechanical metrics into novelty report (BATCH-64)
                        mech = result.mechanical_metrics.get(i)
                        if mech and nov_dict is not None:
                            nov_dict["mechanical_metrics"] = mech
                        elif mech and nov_dict is None:
                            nov_dict = {"mechanical_metrics": mech, "overall_score": None}

                        feas_dict = None
                        if feas:
                            feas_dict = {
                                "data_availability": feas.data_availability,
                                "computational_requirements": feas.computational_requirements,
                                "methodological_complexity": feas.methodological_complexity,
                                "evaluation_plan": feas.evaluation_plan,
                                "reasoning": feas.reasoning,
                                "estimated_timeline": feas.estimated_timeline,
                            }

                        crud.update_idea_scores(
                            session,
                            db_idea.id,
                            novelty_score=nov.overall_score if nov else None,
                            feasibility_score=feas.overall_score if feas else None,
                            novelty_report=json.dumps(nov_dict) if nov_dict else None,
                            feasibility_report=json.dumps(feas_dict) if feas_dict else None,
                        )

                    # Persist idea ↔ paper links (schema-backed provenance)
                    self._persist_idea_paper_links(session, idea, db_idea.id, db_run_id)

                    # Also update paper links for existing ideas that were skipped above
                    if not existing or existing.source_gap_ids == idea_idempotency_key:
                        pass  # Already handled above for new ideas

        except Exception as e:
            logger.warning("Failed to persist ideas: %s", e)
            self.warnings.append(f"persist_ideas: {e}")

    def _persist_idea_paper_links(
        self, session, idea, db_idea_id: int, db_run_id: int
    ) -> None:
        """Link an idea to its supporting papers via IdeaPaperLink.

        Resolves ``idea.supporting_papers`` (source_id strings) to Paper DB
        rows by ``source_id``.  Paper.source_id is globally unique (enforced
        by a unique constraint), so there is at most one match per source_id —
        no cross-run ambiguity is possible.

        Papers whose source_id does not appear in the DB (e.g. from a
        different source or not yet persisted) are logged as unresolved.

        Idempotent via the ``(idea_id, paper_id, role)`` unique constraint.
        """
        supporting_ids = getattr(idea, "supporting_papers", None) or []
        if not supporting_ids:
            return

        from sqlalchemy import select as sa_select

        from backend.db.models import IdeaPaperLink, Paper

        # Resolve source_ids to Paper rows.
        # Paper.source_id is globally unique, so this lookup is unambiguous
        # — the same source_id can never resolve to papers from different runs.
        resolved_ids: list[int] = []
        unresolved: list[str] = []

        for source_id in supporting_ids:
            if not isinstance(source_id, str):
                continue
            paper = session.execute(
                sa_select(Paper).where(Paper.source_id == source_id)
            ).scalars().first()
            if paper:
                resolved_ids.append(paper.id)
            else:
                unresolved.append(source_id)

        if unresolved:
            logger.warning(
                "Idea '%s' (run %d): %d/%d supporting papers resolved, "
                "%d unresolved (source_ids not in Paper table): %s",
                getattr(idea, "title", "?")[:50],
                db_run_id,
                len(resolved_ids),
                len(supporting_ids),
                len(unresolved),
                ", ".join(unresolved[:5]),  # log first 5 for brevity
            )

        for paper_id in resolved_ids:
            # Idempotent insert — skip if link already exists
            existing_link = session.execute(
                sa_select(IdeaPaperLink).where(
                    IdeaPaperLink.idea_id == db_idea_id,
                    IdeaPaperLink.paper_id == paper_id,
                    IdeaPaperLink.role == "supporting",
                )
            ).scalar_one_or_none()
            if not existing_link:
                session.add(IdeaPaperLink(
                    idea_id=db_idea_id,
                    paper_id=paper_id,
                    role="supporting",
                ))

        if resolved_ids:
            session.commit()

    # Phase 1 1C: persist the full-paper artifact written by PaperSynthesisStage
    # into proposal.metadata["full_paper"]. Previously this metadata was dropped
    # by persist_proposals, so the paper was generated but never persisted.
    def persist_proposals(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.proposals:
            return
        try:
            from sqlalchemy import select

            from backend.db import crud
            from backend.db.database import get_session
            from backend.db.models import Idea, Proposal

            with get_session() as session:
                for i, proposal in result.proposals.items():
                    idea = result.ideas[i] if i < len(result.ideas) else None
                    if idea:
                        db_idea_row = session.execute(
                            select(Idea).where(
                                Idea.title == idea.title,
                                Idea.pipeline_run_id == db_run_id,
                            ).limit(1)
                        ).scalar_one_or_none()
                        if db_idea_row:
                            # Filter out non-serializable values (e.g., EnsembleReviewResult)
                            sections_to_store = {}
                            for k, v in proposal.sections.items():
                                if k == "validated_text":
                                    continue
                                if isinstance(v, (str, list, dict, int, float, bool, type(None))):
                                    sections_to_store[k] = v
                                elif hasattr(v, "model_dump"):
                                    sections_to_store[k] = v.model_dump()
                                elif hasattr(v, "__dict__"):
                                    sections_to_store[k] = str(v)

                            refs = proposal.sections.get("references", [])
                            if not isinstance(refs, (list, dict, str)):
                                refs = str(refs)

                            # Upsert: update existing proposal or create new
                            existing = session.execute(
                                select(Proposal).where(
                                    Proposal.idea_id == db_idea_row.id
                                ).limit(1)
                            ).scalar_one_or_none()
                            # Phase 1 1C: persist the full-paper artifact.
                            # PaperSynthesisStage writes proposal.metadata
                            # ["full_paper"]; previously dropped here. Extract
                            # markdown + synthesis metadata and store on the
                            # Proposal row. An empty/placeholder paper is
                            # recorded with status "failed" so it can never
                            # appear as ready (truth rule, WP-1C).
                            #
                            # Phase 7H: pass result_markers so the RESULT
                            # marker→experiment linkage is durable.
                            markers_for_proposal = result.result_markers.get(i) if hasattr(result, "result_markers") else None
                            paper_md, paper_meta = _extract_paper_artifact(
                                proposal, result_markers=markers_for_proposal
                            )
                            # Phase 2 2B: persist the proposal-scope evaluation
                            # that EvaluationStage writes to metadata["evaluation"]
                            # and that was previously dropped (2A bug).
                            proposal_eval = _extract_proposal_evaluation(proposal)
                            if existing:
                                existing.content_md = proposal.to_markdown()
                                existing.references_json = json.dumps(refs)
                                existing.sections_json = json.dumps(sections_to_store)
                                if hasattr(proposal, 'content_latex') and proposal.content_latex:
                                    existing.content_latex = proposal.content_latex
                                existing.paper_md = paper_md
                                existing.paper_meta_json = (
                                    json.dumps(paper_meta) if paper_meta else None
                                )
                                existing.proposal_evaluation_json = proposal_eval
                                session.flush()
                                proposal_row_id = existing.id
                            else:
                                new_proposal = crud.create_proposal(
                                    session,
                                    idea_id=db_idea_row.id,
                                    content_md=proposal.to_markdown(),
                                    references_json=json.dumps(refs),
                                    sections_json=json.dumps(sections_to_store),
                                    paper_md=paper_md,
                                    paper_meta_json=(
                                        json.dumps(paper_meta) if paper_meta else None
                                    ),
                                    proposal_evaluation_json=proposal_eval,
                                )
                                proposal_row_id = new_proposal.id
                            # Phase 4 / WP-4C: persist the frozen marker→source
                            # map. Resolve each source_id (literature Paper.id)
                            # to its papers.id row, or leave unmapped. Only write
                            # when a real paper was synthesized (paper_meta with
                            # source_map) so failed papers get no markers.
                            if paper_meta and paper_meta.get("source_map"):
                                self._persist_source_markers(
                                    session, proposal_row_id, paper_meta["source_map"]
                                )
                            session.commit()
        except Exception as e:
            logger.warning("Failed to persist proposals: %s", e)
            self.warnings.append(f"persist_proposals: {e}")

    @staticmethod
    def _persist_source_markers(
        session, proposal_id: int, source_map: list[dict]
    ) -> None:
        """Phase 4 / WP-4C — write the marker→source map for one paper.

        Resolves each entry's ``source_id`` (the literature ``Paper.id``) to its
        ``papers.id`` row. A mapped entry whose source_id cannot be resolved is
        downgraded to ``unmapped`` rather than dropped or guessed. Unmapped
        entries are written with ``source_paper_id=None``.
        """
        from backend.db import crud

        resolved: list[dict] = []
        for entry in source_map:
            marker_index = entry.get("marker_index")
            marker = entry.get("marker") or f"SOURCE-{marker_index}"
            source_id = entry.get("source_id")
            mapping_status = entry.get("mapping_status", "mapped")
            db_paper_id = None
            if source_id is not None and mapping_status == "mapped":
                db_paper = crud.get_paper_by_source_id(session, source_id)
                if db_paper is None:
                    # The source was in ctx.all_papers but never persisted
                    # (e.g. persist_search_results was skipped on a legacy run).
                    # Downgrade to unmapped rather than guessing or dropping.
                    mapping_status = "unmapped"
                else:
                    db_paper_id = db_paper.id
            resolved.append({
                "marker_index": marker_index,
                "marker": marker,
                "source_paper_id": db_paper_id,
                "mapping_status": mapping_status,
            })
        crud.replace_source_markers(session, proposal_id, resolved)

    def persist_cluster_report(self, cluster_report, db_run_id: int | None) -> None:
        """Write cluster_report_json to PipelineRun (BATCH-38)."""
        if not db_run_id:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun as PipelineRunModel
            from sqlalchemy import select

            report_data = cluster_report
            if hasattr(cluster_report, "model_dump"):
                report_data = cluster_report.model_dump()
            report_json = json.dumps(report_data)

            with get_session() as session:
                run = session.get(PipelineRunModel, db_run_id)
                if run:
                    run.cluster_report_json = report_json
                    session.commit()
        except Exception as e:
            logger.warning("Failed to persist cluster report: %s", e)
            self.warnings.append(f"persist_cluster_report: {e}")

    def persist_tree_data(self, tree_data: dict | None, db_run_id: int | None) -> None:
        """Write tree_data_json to PipelineRun (BATCH-63)."""
        if not db_run_id or not tree_data:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun as PipelineRunModel

            report_json = json.dumps(tree_data, default=str)

            with get_session() as session:
                run = session.get(PipelineRunModel, db_run_id)
                if run:
                    run.tree_data_json = report_json
                    session.commit()
        except Exception as e:
            logger.warning("Failed to persist tree data: %s", e)
            self.warnings.append(f"persist_tree_data: {e}")

    def advance_stage(self, run_id: int, stage_name: str) -> None:
        """Update the current stage, append to stages_completed, and update updated_at."""
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun

            with get_session() as session:
                run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                if run:
                    run.current_stage = stage_name
                    stages = json.loads(run.stages_completed) if run.stages_completed else []
                    if stage_name not in stages:
                        stages.append(stage_name)
                    run.stages_completed = json.dumps(stages)
                    run.updated_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception as e:
            logger.warning("Failed to advance stage: %s", e)
            self.warnings.append(f"advance_stage: {e}")

    def mark_run_failed(self, db_run_id: int | None, message: str) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="failed",
                    current_stage="failed",
                    error_message=message,
                )
        except Exception as e:
            logger.warning("Failed to mark DB run as failed: %s", e)
            self.warnings.append(f"mark_run_failed: {e}")

    def mark_run_completed(self, db_run_id: int | None) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="completed",
                    current_stage="completed",
                )
        except Exception as e:
            logger.warning("Failed to mark DB run as completed: %s", e)
            self.warnings.append(f"mark_run_completed: {e}")

    def find_stale_runs(self, max_age: timedelta, exclude_run_id: str | None = None) -> list:
        """Find runs stuck in 'running' longer than max_age.

        Args:
            max_age: Maximum time a run should be in 'running' state.
            exclude_run_id: If set, skip this run_id_str (e.g. the just-started run).

        Returns:
            List of PipelineRun objects that are stale.
        """
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun

            cutoff = datetime.now(timezone.utc) - max_age
            with get_session() as session:
                # Check updated_at first (heartbeat-updated), fall back to created_at
                stale = session.query(PipelineRun).filter(
                    PipelineRun.status == "running",
                ).all()
                result = []
                for run in stale:
                    # Skip the just-started run
                    if exclude_run_id and run.run_id_str == exclude_run_id:
                        continue
                    # Also skip if DB id matches
                    if exclude_run_id:
                        try:
                            if run.id == int(exclude_run_id):
                                continue
                        except (ValueError, TypeError):
                            pass
                    last_active = run.updated_at or run.created_at
                    if last_active:
                        # Handle both tz-aware and tz-naive datetimes
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(tzinfo=timezone.utc)
                        if last_active < cutoff:
                            result.append(run)
                return result
        except Exception as e:
            logger.warning("Failed to find stale runs: %s", e)
            return []

    def mark_stale_run_failed(self, db_run_id: int, message: str) -> None:
        """Mark a single stale run as failed with a watchdog message."""
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="failed",
                    current_stage="failed",
                    error_message=message,
                )
        except Exception as e:
            logger.warning("Failed to mark stale run as failed: %s", e)

    # ── Checkpoint persistence (durable execution) ─────────────────

    def save_checkpoint(self, checkpoint: "RunCheckpoint") -> None:
        """Save a run checkpoint to disk atomically.

        Writes to a temp file, flushes, fsyncs, then atomically replaces
        the destination with ``os.replace()``. This is the correct Python
        primitive for atomic same-filesystem replacement.

        If the write or replace fails, the old checkpoint is left intact.
        """
        try:
            _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
            path = _CHECKPOINT_DIR / f"{checkpoint.run_id}.json"
            tmp = path.with_suffix(".json.tmp")

            with tmp.open("w", encoding="utf-8") as f:
                f.write(checkpoint.to_json())
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp, path)
            logger.info("Checkpoint saved: %s", checkpoint.run_id)
        except Exception as e:
            # Clean up temp file if it exists
            tmp = _CHECKPOINT_DIR / f"{checkpoint.run_id}.json.tmp"
            if tmp.exists():
                with contextlib_suppress():
                    tmp.unlink()
            logger.error("Failed to save checkpoint: %s", e)
            raise CheckpointPersistenceError(
                f"Failed to save checkpoint for run '{checkpoint.run_id}': {e}"
            ) from e

    def load_checkpoint(self, run_id: str) -> "RunCheckpoint | None":
        """Load a run checkpoint from disk.

        Raises:
            IncompatibleCheckpointError: If the checkpoint schema version
                does not match ``CHECKPOINT_SCHEMA_VERSION``.
            CheckpointPersistenceError: If the checkpoint file is corrupted
                or cannot be read.
        """
        path = _CHECKPOINT_DIR / f"{run_id}.json"
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as e:
            raise CheckpointPersistenceError(
                f"Corrupted checkpoint for run '{run_id}': {e}"
            ) from e

        # Schema version check
        file_version = data.get("schema_version", 1)
        if file_version != CHECKPOINT_SCHEMA_VERSION:
            raise IncompatibleCheckpointError(
                run_id=run_id,
                found_version=file_version,
                expected_version=CHECKPOINT_SCHEMA_VERSION,
            )

        from backend.pipeline.execution.run_state import RunCheckpoint
        return RunCheckpoint.from_dict(data)

    def list_checkpoints(self) -> list[dict]:
        """List all resumable checkpoints.

        Incompatible or corrupted checkpoints are skipped with a warning,
        not raised. Only ``load_checkpoint`` raises typed errors.
        """
        results = []
        if not _CHECKPOINT_DIR.exists():
            return results
        for path in _CHECKPOINT_DIR.glob("*.json"):
            try:
                from backend.pipeline.execution.run_state import RunCheckpoint
                cp = RunCheckpoint.from_json(path.read_text(encoding="utf-8"))
                results.append({
                    "run_id": cp.run_id,
                    "state": cp.state.value,
                    "completed_stages": sum(1 for s in cp.stages if s.status.value == "completed"),
                    "total_stages": len(cp.stages),
                })
            except Exception as e:
                logger.warning("Skipping unreadable checkpoint %s: %s", path.name, e)
        return results

    # ---- State Reconstruction for Resume ----

    def get_run_by_uuid(self, run_id: str) -> Any | None:
        """Look up a PipelineRun by its string run ID."""
        from backend.db.database import get_session
        from backend.db.models import PipelineRun

        with get_session() as session:
            # Direct lookup by run_id_str column
            run = session.query(PipelineRun).filter(
                PipelineRun.run_id_str == run_id
            ).first()
            if run:
                return run
            # Fallback: try numeric ID for backwards compat
            try:
                return session.query(PipelineRun).filter(
                    PipelineRun.id == int(run_id)
                ).first()
            except (ValueError, TypeError):
                return None

    def load_gaps(self, run_db_id: int) -> list:
        """Load ResearchGap objects from database for a pipeline run."""
        from backend.db.crud import get_pipeline_run
        from backend.db.database import get_session
        from backend.pipeline.gap_analysis.models import ResearchGap
        from backend.pipeline.knowledge.truth import TruthValue

        with get_session() as session:
            run = get_pipeline_run(session, run_db_id)
            if not run:
                return []
            gaps = []
            for gap_db in getattr(run, "gaps", []):
                # Reconstruct TruthValue from persisted columns (BATCH-38)
                truth = TruthValue(
                    frequency=getattr(gap_db, "truth_frequency", 0.5),
                    confidence=getattr(gap_db, "truth_confidence", 0.5),
                    evidence_count=getattr(gap_db, "truth_evidence_count", 0),
                )
                # Parse related_clusters from JSON string (BATCH-38)
                related_clusters_raw = getattr(gap_db, "related_clusters", None)
                related_clusters = json.loads(related_clusters_raw) if related_clusters_raw else []

                gaps.append(ResearchGap(
                    title=gap_db.title,
                    description=gap_db.description,
                    gap_type=gap_db.gap_type,
                    confidence=gap_db.confidence,
                    potential_impact=getattr(gap_db, "potential_impact", ""),
                    truth=truth,
                    related_clusters=related_clusters,
                ))
            return gaps

    def load_ideas(self, run_db_id: int) -> list:
        """Load ResearchIdea objects from database for a pipeline run."""
        from backend.db.crud import get_pipeline_run
        from backend.db.database import get_session
        from backend.pipeline.generation.models import ResearchIdea

        with get_session() as session:
            run = get_pipeline_run(session, run_db_id)
            if not run:
                return []
            ideas = []
            for idea_db in getattr(run, "ideas", []):
                ideas.append(ResearchIdea(
                    title=idea_db.title,
                    problem_statement=getattr(idea_db, "problem_statement", ""),
                    proposed_method=getattr(idea_db, "proposed_method", ""),
                    domain=getattr(idea_db, "domain", "AI/NLP"),
                    score=getattr(idea_db, "overall_score", 0.0) or 0.0,
                ))
            return ideas

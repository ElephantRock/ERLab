"""ClaimStore — persistence and query layer for structured claims.

AIV v5.3 — BATCH-122 TASK-02
Authority: A-01 (sole authority for claim persistence)
Hard Boundaries: HB-01 (idempotent store), HB-02 (empty DB search)
"""

from __future__ import annotations

import json
import logging
from typing import Sequence

from sqlalchemy import select, delete, func

from sqlalchemy.orm import Session
from backend.db.models import ResearchClaim
from backend.pipeline.claims.models import Claim, ClaimType

logger = logging.getLogger(__name__)


class ClaimStore:
    """Persistent storage and query layer for structured claims.

    Usage:
        store = ClaimStore(session=db_session)
        count = store.store_claims(claims)
        claims = store.get_claims_by_paper("2401.12345")
    """

    def __init__(self, session: Session, embedding_service=None) -> None:
        self._session = session
        self._embedding_service = embedding_service

    async def store_claims(self, claims: list[Claim]) -> int:
        """Persist claims to database. Idempotent (HB-01).

        If a claim with the same claim_id already exists, it is skipped.
        Returns the number of new claims stored.
        """
        stored = 0
        for claim in claims:
            # Check if claim already exists (idempotency)
            existing = self._session.execute(
                select(ResearchClaim).where(ResearchClaim.claim_id == claim.claim_id)
            ).scalar_one_or_none()
            if existing:
                continue  # HB-01: skip, don't duplicate

            row = self._claim_to_row(claim)
            self._session.add(row)
            stored += 1

        self._session.commit()
        return stored

    def get_claims_by_paper(self, paper_id: str) -> list[Claim]:
        """Retrieve all claims for a given paper."""
        rows = self._session.execute(
            select(ResearchClaim).where(ResearchClaim.source_paper_id == paper_id)
        ).scalars().all()
        return [self._row_to_claim(r) for r in rows]

    def get_claims_by_type(self, claim_type: ClaimType) -> list[Claim]:
        """Retrieve all claims of a given type."""
        rows = self._session.execute(
            select(ResearchClaim).where(ResearchClaim.claim_type == claim_type.value)
        ).scalars().all()
        return [self._row_to_claim(r) for r in rows]

    async def find_similar_claims(
        self, query: str, top_k: int = 10
    ) -> list[tuple[Claim, float]]:
        """Find claims similar to a query string.

        Uses embedding service if available, otherwise falls back to
        keyword matching on the description field.
        Returns [] on empty database (HB-02).
        """
        all_rows = self._session.execute(
            select(ResearchClaim)
        ).scalars().all()

        if not all_rows:
            return []  # HB-02

        if self._embedding_service is not None:
            return await self._find_via_embedding(query, all_rows, top_k)
        else:
            return self._find_via_keyword(query, all_rows, top_k)

    def delete_claims_by_paper(self, paper_id: str) -> int:
        """Delete all claims for a paper. Returns count deleted."""
        result = self._session.execute(
            delete(ResearchClaim).where(ResearchClaim.source_paper_id == paper_id)
        )
        self._session.commit()
        return result.rowcount

    def count_claims(self) -> int:
        """Return total claim count."""
        return self._session.execute(
            select(func.count(ResearchClaim.id))
        ).scalar() or 0

    # ── Private helpers ──

    async def _find_via_embedding(
        self, query: str, rows: Sequence[ResearchClaim], top_k: int
    ) -> list[tuple[Claim, float]]:
        """Use embedding similarity to find matching claims."""
        try:
            query_vec = await self._embedding_service.embed_single(query)
        except Exception:
            logger.warning("Embedding failed, falling back to keyword search")
            return self._find_via_keyword(query, rows, top_k)

        scored: list[tuple[Claim, float]] = []
        for row in rows:
            # Compute cosine similarity with query
            # For now, use description text overlap as proxy
            # (full embedding search would pre-compute claim embeddings)
            sim = self._text_similarity(query, row.description)
            claim = self._row_to_claim(row)
            scored.append((claim, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _find_via_keyword(
        self, query: str, rows: Sequence[ResearchClaim], top_k: int
    ) -> list[tuple[Claim, float]]:
        """Fallback keyword matching on description."""
        query_words = set(query.lower().split())
        scored: list[tuple[Claim, float]] = []
        for row in rows:
            desc_words = set(row.description.lower().split())
            overlap = len(query_words & desc_words)
            sim = overlap / max(len(query_words), 1)
            claim = self._row_to_claim(row)
            scored.append((claim, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _text_similarity(query: str, text: str) -> float:
        """Simple text similarity metric."""
        q_words = set(query.lower().split())
        t_words = set(text.lower().split())
        if not q_words:
            return 0.0
        return len(q_words & t_words) / len(q_words)

    @staticmethod
    def _claim_to_row(claim: Claim) -> ResearchClaim:
        """Convert Claim dataclass to ResearchClaim ORM object."""
        extra = {}
        if claim.constraints is not None:
            extra["constraints"] = claim.constraints

        return ResearchClaim(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type.value,
            title=claim.title,
            description=claim.description,
            source_paper_id=claim.source_paper_id,
            source_section=claim.source_section,
            confidence=claim.confidence,
            method_name=claim.method_name,
            method_category=claim.method_category,
            dataset=claim.dataset,
            metric=claim.metric,
            value=claim.value,
            baseline_method=claim.baseline_method,
            baseline_value=claim.baseline_value,
            limitation_category=claim.limitation_category,
            acknowledged=claim.acknowledged,
            feasibility=claim.feasibility,
            potential_impact=claim.potential_impact,
            compared_to=claim.compared_to,
            relationship=claim.relationship,
            extra_json=json.dumps(extra) if extra else None,
        )

    @staticmethod
    def _row_to_claim(row: ResearchClaim) -> Claim:
        """Convert ResearchClaim ORM to Claim dataclass.

        Raises ValueError if claim_type is invalid (A-02).
        """
        try:
            claim_type = ClaimType(row.claim_type)
        except ValueError:
            raise ValueError(
                f"Invalid claim_type '{row.claim_type}' in database row id={row.id}. "
                f"Expected one of: {[e.value for e in ClaimType]}"
            )

        extra = {}
        if row.extra_json:
            try:
                extra = json.loads(row.extra_json)
            except json.JSONDecodeError:
                pass

        return Claim(
            claim_id=row.claim_id,
            claim_type=claim_type,
            title=row.title,
            description=row.description,
            source_paper_id=row.source_paper_id,
            source_section=row.source_section or "abstract",
            confidence=row.confidence if row.confidence is not None else 0.5,
            method_name=row.method_name,
            method_category=row.method_category,
            constraints=extra.get("constraints"),
            dataset=row.dataset,
            metric=row.metric,
            value=row.value,
            baseline_method=row.baseline_method,
            baseline_value=row.baseline_value,
            limitation_category=row.limitation_category,
            acknowledged=row.acknowledged,
            feasibility=row.feasibility,
            potential_impact=row.potential_impact,
            compared_to=row.compared_to,
            relationship=row.relationship,
        )

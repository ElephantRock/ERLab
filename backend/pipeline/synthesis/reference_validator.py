"""Reference validation — check proposal references against known papers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    reference_index: int
    title: str
    status: str  # "verified_doi", "verified_similarity", "unverified"
    details: str = ""


class ReferenceValidator:
    """Validates proposal references against the papers DB and vector store."""

    def __init__(self, session=None, store=None):
        self._session = session
        self._store = store

    async def validate(self, references: list[dict]) -> list[ValidationResult]:
        results = []
        for i, ref in enumerate(references):
            if not isinstance(ref, dict):
                results.append(
                    ValidationResult(
                        reference_index=i,
                        title=str(ref),
                        status="unverified",
                        details="Reference is not a structured dict",
                    )
                )
                continue

            title = ref.get("title", "")
            doi = ref.get("doi", "")
            verified = False

            # Check DOI against papers table
            if doi and self._session:
                verified = self._check_doi(doi)

            # Check title similarity against vector store
            if not verified and title and self._store:
                verified = await self._check_similarity(title)

            if verified:
                results.append(
                    ValidationResult(
                        reference_index=i,
                        title=title,
                        status="verified_doi" if doi and self._session else "verified_similarity",
                        details="Found in knowledge base",
                    )
                )
            else:
                results.append(
                    ValidationResult(
                        reference_index=i,
                        title=title,
                        status="unverified",
                        details="Not found in knowledge base",
                    )
                )

        return results

    def _check_doi(self, doi: str) -> bool:
        if not self._session:
            return False
        try:
            from sqlalchemy import select

            from backend.db.models import Paper

            row = self._session.execute(
                select(Paper).where(Paper.doi == doi).limit(1)
            ).scalar_one_or_none()
            return row is not None
        except Exception as e:
            logger.warning("DOI check failed: %s", e)
            return False

    async def _check_similarity(self, title: str) -> bool:
        if not self._store:
            return False
        try:
            results = await self._store.query(title, n_results=1)
            if results:
                distance = results[0].get("distance", 1.0)
                return distance < 0.2  # High similarity threshold
        except Exception as e:
            logger.warning("Similarity check failed: %s", e)
        return False

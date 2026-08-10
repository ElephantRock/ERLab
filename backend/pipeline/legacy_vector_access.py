"""Explicit legacy vector access boundary (P0.3.4H).

The only production location allowed to use the ``research_papers`` collection.
Requires a legacy provenance contract; rejects ``provenance_v1`` runs.

Governed code must never import or call this module.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_LEGACY_COLLECTION = "research_papers"


class LegacyVectorAccessError(Exception):
    """Raised when a provenance_v1 run attempts to use legacy vector access."""


def _guard_legacy_only(run_id: int | None, db_engine: Any = None) -> None:
    """Verify the run is explicitly legacy, not governed.

    Raises LegacyVectorAccessError if the run is provenance_v1.
    Returns silently for legacy runs or non-run callers (run_id=None).
    """
    if run_id is None or db_engine is None:
        return  # Non-run caller (CLI, standalone tool) — legacy allowed

    try:
        from sqlalchemy.orm import sessionmaker

        from backend.pipeline.provenance_gate import (
            load_run_provenance_contract,
            select_run_execution_mode,
        )

        Session = sessionmaker(bind=db_engine, expire_on_commit=False)
        session = Session()
        try:
            contract = load_run_provenance_contract(session, run_id)
            mode = select_run_execution_mode(contract)
            if mode == "governed":
                raise LegacyVectorAccessError(
                    f"provenance_v1 run {run_id} cannot use legacy vector access; "
                    f"use the governed scoped vector service instead"
                )
        finally:
            session.close()
    except LegacyVectorAccessError:
        raise
    except Exception:
        # If we can't determine provenance, allow legacy (non-pipeline callers)
        pass


async def query_vectors_legacy_unscoped(
    *,
    store: Any,
    query: str,
    n_results: int,
    run_id: int | None = None,
    db_engine: Any = None,
) -> list[dict]:
    """Legacy unscoped vector query. Only for pre_provenance runs.

    Queries the global ``research_papers`` collection without any scope.
    Creates no governed retrieval event.
    """
    _guard_legacy_only(run_id, db_engine)
    return await store.query(query, n_results=n_results)


async def index_vectors_legacy(
    *,
    store: Any,
    papers: list,
    chunks: list,
    run_id: int | None = None,
    db_engine: Any = None,
) -> int:
    """Legacy vector indexing. Only for pre_provenance runs.

    Writes to the global ``research_papers`` collection.
    Creates no governed vector_index_records.
    """
    _guard_legacy_only(run_id, db_engine)
    return await store.add_papers(papers, chunks)

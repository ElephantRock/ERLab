"""Legacy collection freeze and quarantine (P0.3.6).

Controls the runtime accessibility of the ``research_papers`` collection.

After P0.3.6:
  - Legacy VectorStore construction is disabled for all paths
  - Legacy API endpoints (/search, /ingest) refuse with a clear error
  - Only explicit maintenance inventory (P0.3.5 CLI) may inspect the collection
  - The collection may be quarantined (renamed) or deleted under operator action

The freeze is controlled by a durable database flag so it survives restarts.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class LegacyCollectionFrozenError(Exception):
    """Raised when production code attempts to use the frozen legacy collection."""


_LEGACY_COLLECTION = "research_papers"


# ── Freeze state ─────────────────────────────────────────────────────


def is_legacy_collection_frozen(session: Session) -> bool:
    """Check if the legacy collection is frozen (production access disabled).

    Fail-closed semantics: if the freeze-state row is missing, the read
    fails, or the database is unavailable, the collection is treated as
    FROZEN. This prevents a migration error, database restoration, or
    partial deployment from silently reopening the legacy collection.

    Only an explicitly ``active`` row permits production access.
    """
    try:
        result = session.execute(
            select(_LegacyFreezeState).where(
                _LegacyFreezeState.collection_name == _LEGACY_COLLECTION
            )
        ).scalar_one_or_none()

        # Missing row → fail closed (treat as frozen)
        if result is None:
            return True

        # Only 'active' permits access; everything else is frozen
        return result.status != "active"
    except Exception:
        # Read failure → fail closed
        return True


def freeze_legacy_collection(session: Session, *, reason: str = "P0.3.6 isolation") -> None:
    """Freeze the legacy collection — disable all production access.

    Monotonic: once frozen, the state can only advance (frozen → quarantined
    → deleted). The transition active → frozen is the only way to enter the
    frozen lifecycle. A frozen collection can never return to active.
    """
    existing = session.execute(
        select(_LegacyFreezeState).where(
            _LegacyFreezeState.collection_name == _LEGACY_COLLECTION
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Monotonic guard: cannot go backward
        if existing.status in ("frozen", "quarantined", "deleted"):
            return  # Already frozen or stronger — no backward transition
        # Only active → frozen is permitted
        if existing.status != "active":
            raise ValueError(
                f"cannot freeze from status {existing.status!r}; "
                f"only 'active' can transition to 'frozen'"
            )
        existing.status = "frozen"
        existing.reason = reason
        existing.frozen_at = datetime.now(UTC)
    else:
        state = _LegacyFreezeState(
            collection_name=_LEGACY_COLLECTION,
            status="frozen",
            reason=reason,
            frozen_at=datetime.now(UTC),
        )
        session.add(state)
    session.commit()
    logger.info("Legacy collection %s frozen: %s", _LEGACY_COLLECTION, reason)


def quarantine_legacy_collection(session: Session, *, reason: str = "P0.3.6 quarantine") -> None:
    """Quarantine the legacy collection — rename/access-revoke posture.

    Monotonic: only frozen → quarantined is permitted.
    """
    existing = session.execute(
        select(_LegacyFreezeState).where(
            _LegacyFreezeState.collection_name == _LEGACY_COLLECTION
        )
    ).scalar_one_or_none()
    if existing is None:
        raise ValueError("cannot quarantine: no freeze state exists")
    if existing.status != "frozen":
        raise ValueError(
            f"cannot quarantine from status {existing.status!r}; "
            f"only 'frozen' can transition to 'quarantined'"
        )
    existing.status = "quarantined"
    existing.reason = reason
    existing.quarantined_at = datetime.now(UTC)
    session.commit()
    logger.info("Legacy collection %s quarantined", _LEGACY_COLLECTION)


def delete_legacy_collection_record(session: Session, *, reason: str = "P0.3.6 deletion") -> None:
    """Mark the legacy collection as deleted (physical deletion is a separate Chroma operation).

    Monotonic: only quarantined → deleted is permitted. Deleted is terminal.
    """
    existing = session.execute(
        select(_LegacyFreezeState).where(
            _LegacyFreezeState.collection_name == _LEGACY_COLLECTION
        )
    ).scalar_one_or_none()
    if existing is None:
        raise ValueError("cannot delete: no freeze state exists")
    if existing.status != "quarantined":
        raise ValueError(
            f"cannot delete from status {existing.status!r}; "
            f"only 'quarantined' can transition to 'deleted'"
        )
    existing.status = "deleted"
    existing.reason = reason
    existing.deleted_at = datetime.now(UTC)
    session.commit()
    logger.info("Legacy collection %s marked deleted", _LEGACY_COLLECTION)


# ── Production guard ─────────────────────────────────────────────────


def assert_legacy_not_frozen(session: Session) -> None:
    """Guard for production code that constructs legacy VectorStore.

    Call this before any production access to the legacy collection.
    Raises LegacyCollectionFrozenError if the collection is frozen.
    """
    if is_legacy_collection_frozen(session):
        raise LegacyCollectionFrozenError(
            f"The legacy collection '{_LEGACY_COLLECTION}' is frozen. "
            f"Production access is disabled. Use the governed scoped vector "
            f"service (/search/governed) for governed runs."
        )


# ── ORM model for the freeze state ───────────────────────────────────
# This is a simple singleton-style table that doesn't need a full migration
# for P0.3.6 — it uses an existing pattern of a settings/state table.
# We define it here and let create_all handle it for tests.
# In production, migration 027 would add it formally.


from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.db.database import Base


class _LegacyFreezeState(Base):
    """Durable freeze state for the legacy collection."""

    __tablename__ = "legacy_collection_freeze_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_name = Column(String(120), unique=True, nullable=False)
    status = Column(String(30), nullable=False, default="active")  # active|frozen|quarantined|deleted
    reason = Column(Text, nullable=True)
    frozen_at = Column(DateTime, nullable=True)
    quarantined_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

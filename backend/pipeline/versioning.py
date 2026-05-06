"""Proposal versioning: track revisions with diff support.

Stores proposal versions in SQLite. Each version includes the full text,
a change summary, and a timestamp. Diff between versions shows what changed.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProposalVersion:
    """A single proposal version."""
    proposal_id: str
    version: int
    content: str
    content_hash: str = ""
    change_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict = field(default_factory=dict)


class ProposalVersionStore:
    """SQLite-backed proposal version store.

    Tracks revisions with full content, hashes, and change summaries.
    Supports diff between any two versions.
    """

    def __init__(self, db_path: str | Path = "./data/proposal_versions.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS proposal_versions (
                proposal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                change_summary TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                PRIMARY KEY (proposal_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_proposal_id ON proposal_versions(proposal_id);
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def save(self, version: ProposalVersion) -> int:
        """Save a proposal version. Returns version number."""
        conn = self._get_conn()

        # Auto-increment version
        if version.version == 0:
            cursor = conn.execute(
                "SELECT MAX(version) FROM proposal_versions WHERE proposal_id = ?",
                (version.proposal_id,),
            )
            row = cursor.fetchone()
            version.version = (row[0] or 0) + 1

        version.content_hash = hashlib.sha256(version.content.encode()).hexdigest()[:16]

        conn.execute(
            "INSERT OR REPLACE INTO proposal_versions "
            "(proposal_id, version, content, content_hash, change_summary, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (version.proposal_id, version.version, version.content,
             version.content_hash, version.change_summary, version.created_at,
             json.dumps(version.metadata)),
        )
        conn.commit()
        return version.version

    def get(self, proposal_id: str, version: int | None = None) -> ProposalVersion | None:
        """Get a specific version (or latest if version=None)."""
        conn = self._get_conn()
        try:
            if version is not None:
                cursor = conn.execute(
                    "SELECT * FROM proposal_versions WHERE proposal_id = ? AND version = ?",
                    (proposal_id, version),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM proposal_versions WHERE proposal_id = ? ORDER BY version DESC LIMIT 1",
                    (proposal_id,),
                )
            row = cursor.fetchone()
            if not row:
                return None

            return ProposalVersion(
                proposal_id=row["proposal_id"],
                version=row["version"],
                content=row["content"],
                content_hash=row["content_hash"],
                change_summary=row["change_summary"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"]),
            )
        except Exception as e:
            logger.warning("Version get failed: %s", e)
            return None

    def list_versions(self, proposal_id: str) -> list[int]:
        """List all version numbers for a proposal."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT version FROM proposal_versions WHERE proposal_id = ? ORDER BY version",
                (proposal_id,),
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.warning("List versions failed: %s", e)
            return []

    def diff(self, proposal_id: str, v1: int, v2: int) -> str:
        """Generate a unified diff between two versions."""
        ver1 = self.get(proposal_id, v1)
        ver2 = self.get(proposal_id, v2)
        if not ver1 or not ver2:
            return "Error: one or both versions not found"

        lines1 = ver1.content.splitlines(keepends=True)
        lines2 = ver2.content.splitlines(keepends=True)
        diff = difflib.unified_diff(lines1, lines2, fromfile=f"v{v1}", tofile=f"v{v2}")
        return "".join(diff)

    def count(self, proposal_id: str | None = None) -> int:
        """Count versions."""
        conn = self._get_conn()
        if proposal_id:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM proposal_versions WHERE proposal_id = ?",
                (proposal_id,),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM proposal_versions")
        return cursor.fetchone()[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

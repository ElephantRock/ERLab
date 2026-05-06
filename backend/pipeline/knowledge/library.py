"""Persistent knowledge library for cross-run research memory.

Indexes papers, gaps, and ideas from completed pipeline runs into
persistent storage. Future runs query this library first before
hitting external sources. Research compounds over time.
"""
from __future__ import annotations

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
class LibraryEntry:
    """A single entry in the knowledge library."""
    entry_type: str  # "paper", "gap", "idea"
    domain: str
    title: str
    content: str  # JSON-serialized metadata
    source_run_id: str = ""
    dedup_key: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def compute_dedup_key(self) -> str:
        """Compute dedup key from title."""
        normalized = self.title.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class KnowledgeLibrary:
    """Persistent knowledge library backed by SQLite.

    Stores papers, gaps, and ideas indexed by domain.
    Deduplicates by title hash. Queryable by domain and keywords.
    """

    def __init__(self, db_path: str | Path = "./data/knowledge_library.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS library_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_run_id TEXT DEFAULT '',
                dedup_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_domain ON library_entries(domain);
            CREATE INDEX IF NOT EXISTS idx_type ON library_entries(entry_type);
            CREATE INDEX IF NOT EXISTS idx_dedup ON library_entries(dedup_key);
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def add(self, entry: LibraryEntry) -> bool:
        """Add an entry to the library. Returns True if added, False if duplicate.

        Deduplication is by title hash (HB-02).
        """
        if not entry.dedup_key:
            entry.dedup_key = entry.compute_dedup_key()

        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO library_entries (entry_type, domain, title, content, source_run_id, dedup_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry.entry_type, entry.domain, entry.title, entry.content,
                 entry.source_run_id, entry.dedup_key, entry.created_at),
            )
            conn.commit()
            logger.debug("Added %s '%s' to knowledge library", entry.entry_type, entry.title[:50])
            return True
        except sqlite3.IntegrityError:
            logger.debug("Duplicate entry skipped: %s", entry.title[:50])
            return False

    def query(
        self,
        domain: str,
        entry_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query the library by domain and optional type.

        Returns list of dicts with entry fields.
        """
        conn = self._get_conn()
        try:
            if entry_type:
                cursor = conn.execute(
                    "SELECT * FROM library_entries WHERE domain = ? AND entry_type = ? ORDER BY created_at DESC LIMIT ?",
                    (domain, entry_type, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM library_entries WHERE domain = ? ORDER BY created_at DESC LIMIT ?",
                    (domain, limit),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning("Knowledge library query failed: %s", e)
            return []

    def count(self, domain: str | None = None, entry_type: str | None = None) -> int:
        """Count entries, optionally filtered by domain and type."""
        conn = self._get_conn()
        conditions = []
        params: list = []
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if entry_type:
            conditions.append("entry_type = ?")
            params.append(entry_type)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        cursor = conn.execute(f"SELECT COUNT(*) FROM library_entries{where}", params)
        return cursor.fetchone()[0]

    def add_papers(self, papers: list[Any], domain: str, run_id: str = "") -> int:
        """Bulk-add papers. Returns count of new papers added."""
        added = 0
        for paper in papers:
            title = getattr(paper, "title", "")
            doi = getattr(paper, "doi", "")
            if not title:
                continue
            entry = LibraryEntry(
                entry_type="paper",
                domain=domain,
                title=title,
                content=json.dumps({
                    "doi": doi,
                    "year": getattr(paper, "year", None),
                    "abstract": getattr(paper, "abstract", "")[:500],
                    "authors": getattr(paper, "authors", []),
                }),
                source_run_id=run_id,
            )
            if self.add(entry):
                added += 1
        return added

    def add_gaps(self, gaps: list[Any], domain: str, run_id: str = "") -> int:
        """Bulk-add gaps. Returns count of new gaps added."""
        added = 0
        for gap in gaps:
            title = getattr(gap, "title", getattr(gap, "name", ""))
            if not title:
                continue
            entry = LibraryEntry(
                entry_type="gap",
                domain=domain,
                title=title,
                content=json.dumps({
                    "description": getattr(gap, "description", "")[:500],
                }),
                source_run_id=run_id,
            )
            if self.add(entry):
                added += 1
        return added

    def add_ideas(self, ideas: list[Any], domain: str, run_id: str = "") -> int:
        """Bulk-add ideas. Returns count of new ideas added."""
        added = 0
        for idea in ideas:
            title = getattr(idea, "title", "")
            if not title:
                continue
            entry = LibraryEntry(
                entry_type="idea",
                domain=domain,
                title=title,
                content=json.dumps({
                    "description": getattr(idea, "description", "")[:500],
                    "novelty_score": getattr(idea, "novelty_score", None),
                }),
                source_run_id=run_id,
            )
            if self.add(entry):
                added += 1
        return added

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

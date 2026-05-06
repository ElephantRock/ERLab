"""Error knowledge store: learns from pipeline failures across runs.

Logs rejection reasons, low scores, and quality check failures
so future runs can avoid repeating the same mistakes.
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
class FailureEntry:
    """A single failure record."""
    stage: str
    input_hash: str
    reason: str
    suggestion: str = ""
    score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorKnowledgeStore:
    """Append-only store for pipeline failure knowledge.

    Future runs query this store to learn from past mistakes.
    No deletions allowed (HB-02).
    """

    def __init__(self, db_path: str | Path = "./data/error_knowledge.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS failure_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                reason TEXT NOT NULL,
                suggestion TEXT DEFAULT '',
                score REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_stage ON failure_log(stage);
            CREATE INDEX IF NOT EXISTS idx_hash ON failure_log(input_hash);
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def record(self, entry: FailureEntry) -> int:
        """Record a failure. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO failure_log (stage, input_hash, reason, suggestion, score, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entry.stage, entry.input_hash, entry.reason, entry.suggestion,
             entry.score, entry.created_at),
        )
        conn.commit()
        logger.debug("Recorded failure in stage '%s': %s", entry.stage, entry.reason[:80])
        return cursor.lastrowid

    def query(
        self,
        stage: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query failure records, optionally by stage."""
        conn = self._get_conn()
        try:
            if stage:
                cursor = conn.execute(
                    "SELECT * FROM failure_log WHERE stage = ? ORDER BY created_at DESC LIMIT ?",
                    (stage, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM failure_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning("Error knowledge query failed: %s", e)
            return []

    def count(self, stage: str | None = None) -> int:
        """Count failure records."""
        conn = self._get_conn()
        if stage:
            cursor = conn.execute("SELECT COUNT(*) FROM failure_log WHERE stage = ?", (stage,))
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM failure_log")
        return cursor.fetchone()[0]

    @staticmethod
    def hash_input(content: str) -> str:
        """Create a hash for deduplication of failure inputs."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

"""Gap queue: persistent queue for revisiting research gaps.

Stores gaps from previous runs with priority levels so they can be
investigated more deeply in future pipeline runs.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GapPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class QueuedGap:
    """A gap queued for future investigation."""
    gap_id: str
    title: str
    description: str
    domain: str
    priority: GapPriority = GapPriority.MEDIUM
    source_run_id: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    investigated: bool = False
    investigated_at: str = ""


class GapQueue:
    """Persistent SQLite-backed queue for research gaps.

    Gaps from previous runs are queued with priority levels.
    Future runs can dequeue high-priority gaps for deeper investigation.
    """

    def __init__(self, db_path: str | Path = "./data/gap_queue.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gap_queue (
                gap_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                domain TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                source_run_id TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                investigated INTEGER DEFAULT 0,
                investigated_at TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_priority ON gap_queue(priority);
            CREATE INDEX IF NOT EXISTS idx_investigated ON gap_queue(investigated);
            CREATE INDEX IF NOT EXISTS idx_domain ON gap_queue(domain);
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def enqueue(self, gap: QueuedGap) -> bool:
        """Add a gap to the queue. Returns False if already queued."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO gap_queue "
                "(gap_id, title, description, domain, priority, source_run_id, metadata, created_at, investigated, investigated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (gap.gap_id, gap.title, gap.description, gap.domain, gap.priority.value,
                 gap.source_run_id, json.dumps(gap.metadata), gap.created_at,
                 1 if gap.investigated else 0, gap.investigated_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("Failed to enqueue gap '%s': %s", gap.gap_id, e)
            return False

    def dequeue(self, limit: int = 10, domain: str | None = None) -> list[QueuedGap]:
        """Get next gaps to investigate, ordered by priority then age."""
        conn = self._get_conn()
        try:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            if domain:
                cursor = conn.execute(
                    "SELECT * FROM gap_queue WHERE investigated = 0 AND domain = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (domain, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM gap_queue WHERE investigated = 0 "
                    "ORDER BY created_at ASC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            gaps = []
            for row in rows:
                gaps.append(QueuedGap(
                    gap_id=row["gap_id"],
                    title=row["title"],
                    description=row["description"],
                    domain=row["domain"],
                    priority=GapPriority(row["priority"]),
                    source_run_id=row["source_run_id"],
                    metadata=json.loads(row["metadata"]),
                    created_at=row["created_at"],
                    investigated=bool(row["investigated"]),
                    investigated_at=row["investigated_at"],
                ))
            # Sort by priority
            gaps.sort(key=lambda g: priority_order.get(g.priority.value, 1))
            return gaps
        except Exception as e:
            logger.warning("Gap queue dequeue failed: %s", e)
            return []

    def mark_investigated(self, gap_id: str) -> bool:
        """Mark a gap as investigated."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE gap_queue SET investigated = 1, investigated_at = ? WHERE gap_id = ?",
                (datetime.utcnow().isoformat(), gap_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("Failed to mark gap '%s' investigated: %s", gap_id, e)
            return False

    def count(self, investigated: bool | None = None) -> int:
        """Count gaps in queue, optionally filtered by status."""
        conn = self._get_conn()
        if investigated is None:
            cursor = conn.execute("SELECT COUNT(*) FROM gap_queue")
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM gap_queue WHERE investigated = ?",
                (1 if investigated else 0,),
            )
        return cursor.fetchone()[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

"""In-app notification service for pipeline events.

Stores notifications in SQLite. Supports:
- Pipeline completion notifications
- Error notifications
- Custom notifications with metadata
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """A single notification."""
    id: int = 0
    type: str = "info"  # info, success, warning, error
    title: str = ""
    message: str = ""
    run_id: str = ""
    read: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict = field(default_factory=dict)


class NotificationService:
    """SQLite-backed notification service."""

    def __init__(self, db_path: str | Path = "./data/notifications.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'info',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_read ON notifications(read);
            CREATE INDEX IF NOT EXISTS idx_type ON notifications(type);
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def notify(self, notification: Notification) -> int:
        """Create a notification. Returns ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO notifications (type, title, message, run_id, read, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (notification.type, notification.title, notification.message,
             notification.run_id, 1 if notification.read else 0,
             notification.created_at, json.dumps(notification.metadata)),
        )
        conn.commit()
        return cursor.lastrowid

    def notify_pipeline_complete(self, run_id: str, ideas: int, gaps: int, duration_s: float) -> int:
        """Send pipeline completion notification."""
        return self.notify(Notification(
            type="success",
            title="Pipeline Complete",
            message=f"Found {ideas} ideas and {gaps} gaps in {duration_s:.0f}s",
            run_id=run_id,
            metadata={"ideas": ideas, "gaps": gaps, "duration_s": duration_s},
        ))

    def notify_pipeline_error(self, run_id: str, error: str) -> int:
        """Send pipeline error notification."""
        return self.notify(Notification(
            type="error",
            title="Pipeline Error",
            message=error[:500],
            run_id=run_id,
        ))

    def list_notifications(self, unread_only: bool = False, limit: int = 50) -> list[Notification]:
        """List notifications."""
        conn = self._get_conn()
        try:
            if unread_only:
                cursor = conn.execute(
                    "SELECT * FROM notifications WHERE read = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            results = []
            for row in cursor.fetchall():
                results.append(Notification(
                    id=row["id"],
                    type=row["type"],
                    title=row["title"],
                    message=row["message"],
                    run_id=row["run_id"],
                    read=bool(row["read"]),
                    created_at=row["created_at"],
                    metadata=json.loads(row["metadata"]),
                ))
            return results
        except Exception as e:
            logger.warning("List notifications failed: %s", e)
            return []

    def mark_read(self, notification_id: int) -> bool:
        """Mark a notification as read."""
        conn = self._get_conn()
        conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        return True

    def count_unread(self) -> int:
        """Count unread notifications."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM notifications WHERE read = 0")
        return cursor.fetchone()[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

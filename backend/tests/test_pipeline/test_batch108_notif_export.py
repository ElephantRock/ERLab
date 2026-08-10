"""Tests for BATCH-108 — Notifications + Export.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.pipeline.notifications.service import Notification, NotificationService


@pytest.fixture
def notif_svc():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = NotificationService(db_path=os.path.join(tmpdir, "notif.db"))
        yield svc
        svc.close()


def test_108_01_create_notification(notif_svc):
    """Creating a notification returns an ID."""
    nid = notif_svc.notify(Notification(title="Test", message="Test message"))
    assert nid > 0


def test_108_01_pipeline_complete_notification(notif_svc):
    """Pipeline complete notification is created."""
    nid = notif_svc.notify_pipeline_complete("run-1", ideas=3, gaps=5, duration_s=120)
    assert nid > 0
    notifs = notif_svc.list_notifications()
    assert len(notifs) == 1
    assert notifs[0].type == "success"
    assert "3 ideas" in notifs[0].message


def test_108_01_count_unread(notif_svc):
    """Unread count is correct."""
    assert notif_svc.count_unread() == 0
    notif_svc.notify(Notification(title="A", message="B"))
    notif_svc.notify(Notification(title="C", message="D"))
    assert notif_svc.count_unread() == 2


def test_108_01_mark_read(notif_svc):
    """Marking as read updates unread count."""
    nid = notif_svc.notify(Notification(title="A", message="B"))
    assert notif_svc.count_unread() == 1
    notif_svc.mark_read(nid)
    assert notif_svc.count_unread() == 0
    unread = notif_svc.list_notifications(unread_only=True)
    assert len(unread) == 0


def test_108_02_export_routes_exist():
    """Export API routes file exists."""
    from pathlib import Path
    export_path = Path(str(Path(__file__).resolve().parents[3] / "backend/api/routes/export.py"))
    assert export_path.exists()


def test_108_02_export_has_markdown_route():
    """Export has markdown endpoint."""
    from pathlib import Path
    content = Path(str(Path(__file__).resolve().parents[3] / "backend/api/routes/export.py")).read_text(encoding="utf-8")
    assert "export_markdown" in content
    assert "text/markdown" in content


def test_108_02_export_has_bibtex_route():
    """Export has BibTeX endpoint."""
    from pathlib import Path
    content = Path(str(Path(__file__).resolve().parents[3] / "backend/api/routes/export.py")).read_text(encoding="utf-8")
    assert "export_bibtex" in content
    assert "bibtex" in content.lower()


def test_108_02_bibtex_exporter_exists():
    """BibTeX exporter module exists and works."""
    from backend.pipeline.export.bibtex_exporter import paper_to_bibtex
    from backend.pipeline.literature.models import Paper
    paper = Paper(id="test:1", title="Test Paper", source="test")
    bibtex = paper_to_bibtex(paper)
    assert "@article{" in bibtex

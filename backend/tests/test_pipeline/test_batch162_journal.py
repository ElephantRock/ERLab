"""BATCH-162: Research Journal & AI Honesty Labeling.

TASK-01: Journal API endpoint (4 tests)
TASK-02: AI Honesty labeling in journal (3 tests)
TASK-03: Per-stage journal hooks (3 tests)
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ─── TASK-01: Journal API ───────────────────────────────────

class TestJournalAPI:

    def test_01_journal_endpoint_exists(self):
        from backend.api.routes.pipeline import router
        routes = [r.path for r in router.routes]
        assert any("journal" in r for r in routes)

    def test_02_journal_returns_404_when_missing(self):
        from fastapi.testclient import TestClient
        from backend.api.app import app
        client = TestClient(app)
        response = client.get("/api/v1/pipeline/runs/nonexistent_run/journal")
        assert response.status_code == 404

    def test_03_journal_writer_creates_files(self):
        from backend.pipeline.journal.writer import JournalWriter
        tmpdir = tempfile.mkdtemp()
        writer = JournalWriter(run_id="test_run", domain="AI", output_dir=tmpdir)
        writer.add_note("test_stage", "Test message", {"key": "value"})
        notes_path, readme_path = writer.write()
        assert notes_path.exists()
        assert readme_path.exists()
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_04_journal_writer_produces_valid_output(self):
        from backend.pipeline.journal.writer import JournalWriter
        import shutil

        tmpdir = tempfile.mkdtemp()
        writer = JournalWriter(run_id="test_api_run", domain="AI", output_dir=tmpdir)
        writer.add_note("stage1", "Hello journal")
        notes_path, readme_path = writer.write()

        notes_content = notes_path.read_text(encoding="utf-8")
        readme_content = readme_path.read_text(encoding="utf-8")
        assert "Hello journal" in notes_content
        assert "Research Report" in readme_content

        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── TASK-02: AI Honesty Labeling ────────────────────────────

class TestAIHonestyLabeling:

    def test_05_notes_has_ai_disclaimer(self):
        from backend.pipeline.journal.writer import JournalWriter
        import shutil
        tmpdir = tempfile.mkdtemp()
        writer = JournalWriter(run_id="test", domain="AI", output_dir=tmpdir)
        writer.add_note("stage", "msg")
        notes_path, _ = writer.write()
        content = notes_path.read_text(encoding="utf-8")
        assert "AI-Generated Content" in content
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_06_readme_has_honesty_badge(self):
        from backend.pipeline.journal.writer import JournalWriter
        import shutil
        tmpdir = tempfile.mkdtemp()
        writer = JournalWriter(run_id="test", domain="AI", output_dir=tmpdir)
        writer.add_note("stage", "msg")
        _, readme_path = writer.write()
        content = readme_path.read_text(encoding="utf-8")
        # Should contain AI honesty text
        assert "AI pipeline" in content or "independently verified" in content
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_07_scrub_removes_sensitive_data(self):
        from backend.pipeline.journal.writer import JournalWriter
        scrubbed = JournalWriter._scrub("Key is sk-abc123secret")
        assert "sk-" not in scrubbed
        assert "[REDACTED]" in scrubbed


# ─── TASK-03: Per-stage Journal Hooks ───────────────────────

class TestStageJournalHooks:

    def test_08_stage_context_has_journal_field(self):
        from backend.pipeline.stages import StageContext
        from backend.pipeline.result import PipelineResult
        ctx = StageContext(result=PipelineResult())
        assert hasattr(ctx, "journal")
        assert ctx.journal is None

    def test_09_journal_hook_works_with_mock(self):
        from backend.pipeline.stages import StageContext
        from backend.pipeline.result import PipelineResult
        mock_journal = MagicMock()
        ctx = StageContext(result=PipelineResult(), journal=mock_journal)
        if ctx.journal:
            ctx.journal.add_note("test", "hello", {"a": 1})
        mock_journal.add_note.assert_called_once_with("test", "hello", {"a": 1})

    def test_10_journal_hook_graceful_on_none(self):
        from backend.pipeline.stages import StageContext
        from backend.pipeline.result import PipelineResult
        ctx = StageContext(result=PipelineResult(), journal=None)
        # Should not crash when journal is None
        if ctx.journal:
            ctx.journal.add_note("test", "hello")
        # Passes if no exception

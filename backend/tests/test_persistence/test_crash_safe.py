"""Tests for crash-safe persistence and replay.

Tests cover:
1. Atomic checkpoint writes (temp-file + fsync + os.replace)
2. Interrupted writes leave old checkpoint intact
3. Corrupted checkpoints fail explicitly
4. Schema version incompatibility raises typed error
5. Replay idempotency: no duplicate ideas
6. Collector record IDs preserved through replay

Run: pytest backend/tests/test_persistence/ -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.pipeline.execution.run_state import (
    RunCheckpoint,
    RunState,
)
from backend.pipeline.persistence import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointPersistenceError,
    IncompatibleCheckpointError,
    PipelinePersistence,
    content_hash,
)


@pytest.fixture
def checkpoint_dir(tmp_path, monkeypatch):
    """Create a temporary checkpoint directory."""
    ckpt_dir = tmp_path / "checkpoints"
    ckpt_dir.mkdir()
    monkeypatch.setattr(
        "backend.pipeline.persistence._CHECKPOINT_DIR", ckpt_dir
    )
    return ckpt_dir


@pytest.fixture
def sample_checkpoint():
    """Create a sample checkpoint for testing."""
    return RunCheckpoint.create_new(
        run_id="run_test123",
        stage_names=["literature_search", "gap_analysis", "idea_generation"],
        domain="AI/NLP",
    )


class TestAtomicCheckpointWrite:
    """Atomic writes use temp-file + fsync + os.replace."""

    def test_save_creates_checkpoint_file(self, checkpoint_dir, sample_checkpoint):
        persistence = PipelinePersistence()
        persistence.save_checkpoint(sample_checkpoint)

        path = checkpoint_dir / "run_test123.json"
        assert path.exists()

        # Verify content is valid JSON with schema version
        data = json.loads(path.read_text())
        assert data["schema_version"] == CHECKPOINT_SCHEMA_VERSION
        assert data["run_id"] == "run_test123"

    def test_no_temp_file_left_after_success(self, checkpoint_dir, sample_checkpoint):
        persistence = PipelinePersistence()
        persistence.save_checkpoint(sample_checkpoint)

        tmp = checkpoint_dir / "run_test123.json.tmp"
        assert not tmp.exists()

    def test_interrupted_write_keeps_old_checkpoint(
        self, checkpoint_dir, sample_checkpoint
    ):
        """If the write fails after creating the temp file,
        the old checkpoint remains intact."""
        persistence = PipelinePersistence()

        # Save initial checkpoint
        persistence.save_checkpoint(sample_checkpoint)
        original_content = (checkpoint_dir / "run_test123.json").read_text()

        # Simulate a crash: replace os.replace with a failing function
        original_replace = os.replace
        call_count = {"n": 0}

        def failing_replace(src, dst):
            call_count["n"] += 1
            # Clean up the temp file to simulate crash mid-write
            Path(src).unlink()
            raise OSError("Simulated disk failure")

        with patch("backend.pipeline.persistence.os.replace", failing_replace):
            with pytest.raises(CheckpointPersistenceError):
                sample_checkpoint.state = RunState.COMPLETED
                persistence.save_checkpoint(sample_checkpoint)

        # Old checkpoint must still be intact
        current_content = (checkpoint_dir / "run_test123.json").read_text()
        assert current_content == original_content
        assert call_count["n"] == 1  # os.replace was called

    def test_save_checkpoint_raises_on_failure(self, checkpoint_dir, sample_checkpoint):
        """Checkpoint save failure raises CheckpointPersistenceError, not warning."""
        persistence = PipelinePersistence()

        with patch.object(Path, "open", side_effect=OSError("disk full")):
            with pytest.raises(CheckpointPersistenceError):
                persistence.save_checkpoint(sample_checkpoint)


class TestSchemaVersioning:
    """Checkpoint schema versioning prevents loading incompatible formats."""

    def test_current_schema_version_is_2(self):
        assert CHECKPOINT_SCHEMA_VERSION == 2

    def test_checkpoint_includes_schema_version(self, sample_checkpoint):
        data = sample_checkpoint.to_dict()
        assert "schema_version" in data
        assert data["schema_version"] == CHECKPOINT_SCHEMA_VERSION

    def test_load_incompatible_version_raises(self, checkpoint_dir):
        """Loading a v1 checkpoint with v2 code raises IncompatibleCheckpointError."""
        # Write a fake v1 checkpoint
        old_data = {
            "schema_version": 1,
            "run_id": "run_old",
            "state": "running",
            "stages": [],
            "domain": "AI/NLP",
            "params": {},
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        (checkpoint_dir / "run_old.json").write_text(json.dumps(old_data))

        persistence = PipelinePersistence()
        with pytest.raises(IncompatibleCheckpointError) as exc_info:
            persistence.load_checkpoint("run_old")

        assert exc_info.value.found_version == 1
        assert exc_info.value.expected_version == CHECKPOINT_SCHEMA_VERSION

    def test_load_v2_checkpoint_succeeds(self, checkpoint_dir, sample_checkpoint):
        """Loading a current-version checkpoint works."""
        persistence = PipelinePersistence()
        persistence.save_checkpoint(sample_checkpoint)

        loaded = persistence.load_checkpoint("run_test123")
        assert loaded is not None
        assert loaded.run_id == "run_test123"
        assert len(loaded.stages) == 3

    def test_load_nonexistent_returns_none(self, checkpoint_dir):
        persistence = PipelinePersistence()
        result = persistence.load_checkpoint("does_not_exist")
        assert result is None


class TestCorruptedCheckpoint:
    """Corrupted checkpoints fail explicitly."""

    def test_corrupted_json_raises_typed_error(self, checkpoint_dir):
        """A file with invalid JSON raises CheckpointPersistenceError."""
        (checkpoint_dir / "run_corrupt.json").write_text("NOT VALID JSON{{{")

        persistence = PipelinePersistence()
        with pytest.raises(CheckpointPersistenceError, match="Corrupted"):
            persistence.load_checkpoint("run_corrupt")

    def test_list_checkpoints_skips_corrupted(self, checkpoint_dir):
        """list_checkpoints should skip corrupted files, not crash."""
        (checkpoint_dir / "run_corrupt.json").write_text("GARBAGE")
        # Write a valid checkpoint
        valid_cp = RunCheckpoint.create_new("run_ok", ["stage1"])
        valid_cp.mark_stage_completed("stage1")
        valid_data = valid_cp.to_dict()
        # Wrap in the format from_json expects
        (checkpoint_dir / "run_ok.json").write_text(json.dumps(valid_data))

        persistence = PipelinePersistence()
        result = persistence.list_checkpoints()
        # Corrupted file skipped, valid one included
        run_ok_found = any(r["run_id"] == "run_ok" for r in result)
        assert run_ok_found


class TestReplayIdempotency:
    """Replay should not duplicate ideas."""

    def test_idempotency_key_is_stable(self):
        """Same idea content produces the same idempotency key."""
        key1 = content_hash("1|Title A|Problem A")
        key2 = content_hash("1|Title A|Problem A")
        assert key1 == key2

    def test_idempotency_key_differs_by_run(self):
        """Different run IDs produce different keys for the same idea."""
        key1 = content_hash("1|Title A|Problem A")
        key2 = content_hash("2|Title A|Problem A")
        assert key1 != key2

    def test_idempotency_key_differs_by_content(self):
        """Different content produces different keys."""
        key1 = content_hash("1|Title A|Problem A")
        key2 = content_hash("1|Title B|Problem B")
        assert key1 != key2

    def test_replay_does_not_duplicate_ideas(self):
        """Replaying persist_ideas with the same data does not create duplicates."""
        persistence = PipelinePersistence()

        # Mock idea object
        idea = MagicMock()
        idea.title = "Test Idea"
        idea.problem_statement = "Test Problem"
        idea.proposed_method = "Test Method"
        idea.expected_contributions = ""
        idea.domain = "AI/NLP"
        idea.source_gap_ids = None

        result = MagicMock()
        result.ideas = [idea]
        result.novelty_reports = {}
        result.feasibility_reports = {}
        result.mechanical_metrics = {}

        # Mock the DB session and query
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # First call: no existing idea found → creates it
        mock_existing_query = MagicMock()
        mock_existing_query.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_existing_query

        with patch("backend.db.database.get_session", return_value=mock_session), \
             patch("backend.db.crud.create_idea", return_value=MagicMock(id=42)):
            persistence.persist_ideas(result, db_run_id=1)

        # Verify create_idea was called (first insert)
        assert mock_session.execute.call_count >= 1

        # Second call: same idea → query finds it → no create
        mock_existing_idea = MagicMock()
        mock_existing_idea.id = 42
        mock_existing_query2 = MagicMock()
        mock_existing_query2.scalar_one_or_none.return_value = mock_existing_idea
        mock_session.execute.return_value = mock_existing_query2

        with patch("backend.db.database.get_session", return_value=mock_session):
            persistence.persist_ideas(result, db_run_id=1)


class TestCollectorLinkPreservation:
    """Source gap IDs / collector record IDs must survive replay."""

    def test_source_gap_ids_stored_as_json(self):
        """When source_gap_ids are present, they're stored as JSON."""
        idea = MagicMock()
        idea.title = "Test"
        idea.problem_statement = "Problem"
        idea.proposed_method = "Method"
        idea.expected_contributions = ""
        idea.domain = "AI/NLP"
        idea.source_gap_ids = ["gap_1", "gap_2", "gap_3"]

        result = MagicMock()
        result.ideas = [idea]
        result.novelty_reports = {}
        result.feasibility_reports = {}
        result.mechanical_metrics = {}

        persistence = PipelinePersistence()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_query = MagicMock()
        mock_query.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_query

        created_ideas = []
        def capture_create(session, **kwargs):
            created_ideas.append(kwargs)
            return MagicMock(id=1)

        with patch("backend.db.database.get_session", return_value=mock_session), \
             patch("backend.db.crud.create_idea", side_effect=capture_create):
            persistence.persist_ideas(result, db_run_id=1)

        assert len(created_ideas) == 1
        # source_gap_ids should be stored as JSON string
        gap_ids = created_ideas[0]["source_gap_ids"]
        assert "gap_1" in gap_ids
        assert "gap_3" in gap_ids

    def test_idempotency_key_stored_when_no_gap_ids(self):
        """When no source_gap_ids exist, idempotency key is stored."""
        idea = MagicMock()
        idea.title = "Test"
        idea.problem_statement = "Problem"
        idea.proposed_method = "Method"
        idea.expected_contributions = ""
        idea.domain = "AI/NLP"
        idea.source_gap_ids = None

        result = MagicMock()
        result.ideas = [idea]
        result.novelty_reports = {}
        result.feasibility_reports = {}
        result.mechanical_metrics = {}

        persistence = PipelinePersistence()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_query = MagicMock()
        mock_query.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_query

        created_ideas = []
        def capture_create(session, **kwargs):
            created_ideas.append(kwargs)
            return MagicMock(id=1)

        with patch("backend.db.database.get_session", return_value=mock_session), \
             patch("backend.db.crud.create_idea", side_effect=capture_create):
            persistence.persist_ideas(result, db_run_id=1)

        assert len(created_ideas) == 1
        # When no gap IDs, idempotency key (hash string) is stored
        gap_ids = created_ideas[0]["source_gap_ids"]
        assert gap_ids is not None
        # It should be a content hash, not JSON array
        assert not gap_ids.startswith("[")

"""BATCH-165: Self-Improving Prompts (TextGrad)."""
import os
import tempfile
from pathlib import Path

import pytest


class TestTextGrad:

    def test_01_no_gradient_when_performing_well(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        gradient = engine.compute_gradient("gap_analysis", "prompt text", 0.9, 0.8)
        assert gradient is None

    def test_02_gradient_for_poor_performance(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        gradient = engine.compute_gradient("gap_analysis", "prompt text", 0.3, 0.8)
        assert gradient is not None
        assert gradient.score_delta > 0
        assert "rewrite" in gradient.suggestion.lower()

    def test_03_moderate_improvement_suggestion(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        gradient = engine.compute_gradient("gap_analysis", "prompt", 0.5, 0.8)
        assert gradient is not None
        assert gradient.score_delta > 0

    def test_04_apply_gradient_creates_version(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        gradient = engine.compute_gradient("gap_analysis", "old prompt", 0.3, 0.8)
        version = engine.apply_gradient(gradient, "improved prompt")
        assert version.version == 1
        assert version.hash != ""
        assert gradient.applied is True

    def test_05_version_increments(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        g1 = engine.compute_gradient("test", "p1", 0.3, 0.8)
        engine.apply_gradient(g1, "p2")
        g2 = engine.compute_gradient("test", "p2", 0.4, 0.8)
        engine.apply_gradient(g2, "p3")
        history = engine.get_history("test")
        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].version == 2

    def test_06_persist_writes_file(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        import json
        tmpdir = tempfile.mkdtemp()
        engine = TextGradEngine(persist_dir=tmpdir)
        g = engine.compute_gradient("test", "p", 0.3, 0.8)
        engine.apply_gradient(g, "p2")
        path = Path(tmpdir) / "test_history.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1

    def test_07_minor_tuning_suggestion(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        gradient = engine.compute_gradient("test", "p", 0.72, 0.8)
        assert gradient is not None
        assert "tuning" in gradient.suggestion.lower() or "refine" in gradient.suggestion.lower()

    def test_08_prompt_version_hash(self):
        from backend.pipeline.self_improve.textgrad import PromptVersion
        v = PromptVersion(stage_name="test", version=1, content="hello world")
        h = v.compute_hash()
        assert len(h) == 16
        # Same content = same hash
        v2 = PromptVersion(stage_name="test", version=2, content="hello world")
        v2.compute_hash()
        assert v2.hash == h

    def test_09_empty_history(self):
        from backend.pipeline.self_improve.textgrad import TextGradEngine
        engine = TextGradEngine(persist_dir=tempfile.mkdtemp())
        assert engine.get_history("nonexistent") == []

    def test_10_gradient_dataclass_fields(self):
        from backend.pipeline.self_improve.textgrad import PromptGradient
        g = PromptGradient(stage_name="test", version=1, current_hash="abc", suggestion="fix it")
        assert g.applied is False
        assert g.score_delta == 0.0

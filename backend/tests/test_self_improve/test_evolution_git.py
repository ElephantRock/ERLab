"""Tests for git-backed undo/redo on PipelineEvolver."""

import json
import subprocess
from pathlib import Path

from backend.pipeline.self_improve.evolution import PipelineEvolver
from backend.pipeline.self_improve.frontier import ParetoFrontier


def _init_git_repo(tmp: str) -> str:
    """Create a minimal git repo in tmp dir."""
    subprocess.run(["git", "init"], cwd=tmp, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, capture_output=True)
    Path(tmp, "README").write_text("test")
    subprocess.run(["git", "add", "README"], cwd=tmp, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, capture_output=True, check=True)
    return tmp


class TestGitUndo:
    def test_snapshot_commits(self, tmp_path):
        repo = _init_git_repo(str(tmp_path))
        frontier_path = tmp_path / "frontier.json"
        evolver = PipelineEvolver(ParetoFrontier(str(frontier_path)), git_dir=repo)
        h = evolver.snapshot({"key": "value"}, "run1")
        assert h is not None
        # File should exist with the params
        assert json.loads(Path(repo, "evolved_params.json").read_text()) == {"key": "value"}

    def test_undo_reverts(self, tmp_path):
        repo = _init_git_repo(str(tmp_path))
        frontier_path = tmp_path / "frontier.json"
        evolver = PipelineEvolver(ParetoFrontier(str(frontier_path)), git_dir=repo)
        evolver.snapshot({"v": 1}, "run1")
        evolver.snapshot({"v": 2}, "run2")
        prev = evolver.undo()
        assert prev == {"v": 1}

    def test_no_git_dir_returns_none(self, tmp_path):
        frontier_path = tmp_path / "frontier.json"
        evolver = PipelineEvolver(ParetoFrontier(str(frontier_path)))
        assert evolver.snapshot({"a": 1}, "run1") is None
        assert evolver.undo() is None

    def test_evaluate_snapshots_on_success(self, tmp_path):
        repo = _init_git_repo(str(tmp_path))
        frontier_path = tmp_path / "frontier.json"
        evolver = PipelineEvolver(ParetoFrontier(str(frontier_path)), git_dir=repo)
        params = {"generation_rounds": 2}
        evolver.evaluate(params, "test_run", avg_idea_score=0.8)
        assert Path(repo, "evolved_params.json").exists()

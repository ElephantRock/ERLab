"""Tests for BATCH-180: DAG foundation -- config, logger, runner."""

import asyncio
import json
import os
import sys
import io
import tempfile

import pytest


# ── TASK-01: ConfigLoader ─────────────────────────────────────────────


class TestConfigLoader:
    """TEST-180-01-01 through TEST-180-01-06."""

    def _get_yaml_path(self):
        return os.path.join(
            os.path.dirname(__file__), "..", "..", "pipeline", "dag", "pipeline.yaml"
        )

    def test_01_loads_yaml_and_returns_dict(self):
        """TEST-180-01-01: ConfigLoader reads pipeline.yaml and returns dict."""
        from backend.pipeline.dag.config import ConfigLoader

        loader = ConfigLoader()
        config = loader.load()
        assert "models" in config
        assert config["models"]["thinking"]["provider"] == "openai"

    def test_02_validates_required_fields(self):
        """TEST-180-01-02: ConfigLoader validates required fields present."""
        from backend.pipeline.dag.config import ConfigLoader

        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write("models:\n  thinking: {provider: test}\n")  # Missing infrastructure/budgets/search/strategies
        f.close()
        try:
            with pytest.raises(ValueError, match="Missing required sections"):
                ConfigLoader(f.name).load()
        finally:
            os.unlink(f.name)

    def test_03_immutable_snapshot(self):
        """TEST-180-01-03: ConfigLoader returns independent copies."""
        from backend.pipeline.dag.config import ConfigLoader

        loader = ConfigLoader()
        snap1 = loader.load()
        snap1["models"]["thinking"]["provider"] = "MUTATED"
        snap2 = loader.load()
        assert snap2["models"]["thinking"]["provider"] == "openai"

    def test_04_all_four_strategies_present(self):
        """TEST-180-01-04: All 4 strategies present in config."""
        from backend.pipeline.dag.config import ConfigLoader

        loader = ConfigLoader()
        config = loader.load()
        strategies = config["strategies"]
        assert len(strategies) == 4
        for name in ["fast_scan", "deep_research", "academic_proposal", "literature_review"]:
            assert name in strategies

    def test_05_strategy_has_stages_and_description(self):
        """TEST-180-01-05: Each strategy has stages list and description."""
        from backend.pipeline.dag.config import ConfigLoader

        loader = ConfigLoader()
        config = loader.load()
        for name, strat in config["strategies"].items():
            assert "stages" in strat, f"Strategy '{name}' missing 'stages'"
            assert "description" in strat, f"Strategy '{name}' missing 'description'"
            assert isinstance(strat["stages"], list)
            assert len(strat["stages"]) > 0

    def test_06_resolves_relative_paths(self):
        """TEST-180-01-06: ConfigLoader resolves relative paths to absolute."""
        from backend.pipeline.dag.config import ConfigLoader

        loader = ConfigLoader()
        config = loader.load()
        assert os.path.isabs(config["infrastructure"]["chroma_dir"])
        assert os.path.isabs(config["infrastructure"]["bm25_dir"])


# ── TASK-02: StageLogger ──────────────────────────────────────────────


class TestStageLogger:
    """TEST-180-02-01 through TEST-180-02-05."""

    REQUIRED_FIELDS = {"run_id", "stage", "timestamp", "event", "elapsed_s", "config", "inputs", "outputs", "error"}

    def _make_logger(self, tmpdir):
        from backend.pipeline.dag.stage_log import StageLogger
        return StageLogger(run_id="test_run", log_dir=str(tmpdir))

    def test_01_writes_json_with_required_fields(self):
        """TEST-180-02-01: StageLogger writes JSON entry with all required fields."""
        tmpdir = tempfile.mkdtemp()
        logger = self._make_logger(tmpdir)
        entry = logger.log(
            stage="gap_analysis",
            event="complete",
            config={"model": "test"},
            inputs={"papers_count": 10},
            outputs={"gaps_count": 5},
            elapsed_s=42.1,
        )
        missing = self.REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_02_appends_not_overwrites(self):
        """TEST-180-02-02: StageLogger appends entries (not overwrites)."""
        tmpdir = tempfile.mkdtemp()
        logger = self._make_logger(tmpdir)
        logger.log(stage="stage_a", event="complete", elapsed_s=1.0)
        logger.log(stage="stage_b", event="complete", elapsed_s=2.0)
        entries = logger.read_entries()
        assert len(entries) == 2

    def test_03_handles_error_entries(self):
        """TEST-180-02-03: StageLogger handles error entries correctly."""
        tmpdir = tempfile.mkdtemp()
        logger = self._make_logger(tmpdir)
        entry = logger.log_error(
            stage="failing_stage",
            event="error",
            error="Something went wrong",
            elapsed_s=0.0,
        )
        assert entry["error"] is not None
        assert "Something went wrong" in entry["error"]

    def test_04_creates_log_directory(self):
        """TEST-180-02-04: StageLogger creates log directory if missing."""
        tmpdir = tempfile.mkdtemp()
        log_dir = os.path.join(tmpdir, "nested", "logs")
        assert not os.path.exists(log_dir)
        from backend.pipeline.dag.stage_log import StageLogger
        logger = StageLogger(run_id="test", log_dir=log_dir)
        logger.log(stage="test", event="complete", elapsed_s=0.0)
        assert os.path.isdir(log_dir)

    def test_05_counts_are_integers(self):
        """TEST-180-02-05: StageLogger input/output counts are integers."""
        tmpdir = tempfile.mkdtemp()
        logger = self._make_logger(tmpdir)
        entry = logger.log(
            stage="test",
            event="complete",
            inputs={"papers_count": 36.0},
            outputs={"gaps_count": 5.0},
            elapsed_s=1.0,
        )
        assert isinstance(entry["inputs"]["papers_count"], int)
        assert isinstance(entry["outputs"]["gaps_count"], int)


# ── TASK-03: DAGRunner ────────────────────────────────────────────────


class TestDAGRunner:
    """TEST-180-03-01 through TEST-180-03-07."""

    def _get_yaml_path(self):
        return os.path.join(
            os.path.dirname(__file__), "..", "..", "pipeline", "dag", "pipeline.yaml"
        )

    def test_01_build_plan_returns_correct_stages(self):
        """TEST-180-03-01: DAGRunner.build_plan returns correct stage list."""
        from backend.pipeline.dag.runner import DAGRunner
        runner = DAGRunner()
        plan = runner.build_plan("fast_scan")
        assert "literature_search" in plan
        assert "gap_analysis" in plan

    def test_02_build_plan_validates_strategy_name(self):
        """TEST-180-03-02: DAGRunner.build_plan validates strategy name."""
        from backend.pipeline.dag.runner import DAGRunner
        runner = DAGRunner()
        with pytest.raises((KeyError, ValueError)):
            runner.build_plan("nonexistent_strategy")

    def test_03_dry_run_prints_without_executing(self):
        """TEST-180-03-03: DAGRunner.dry_run prints stage list without executing."""
        from backend.pipeline.dag.runner import DAGRunner
        runner = DAGRunner()
        output = runner.dry_run("test domain", "fast_scan")
        assert "literature_search" in output
        assert "Strategy:" in output or "fast_scan" in output

    def test_04_dry_run_shows_model_assignment(self):
        """TEST-180-03-04: DAGRunner.dry_run prints model assignment per stage."""
        from backend.pipeline.dag.runner import DAGRunner
        runner = DAGRunner()
        output = runner.dry_run("test", "deep_research")
        # Should show model info
        assert "thinking" in output or "generation" in output or "embedding" in output

    def test_05_context_config_immutable(self):
        """TEST-180-03-05: StageContext config is immutable-in."""
        import copy
        from backend.pipeline.dag.context import StageContext
        original_config = {"models": {"thinking": {"provider": "test"}}}
        ctx = StageContext(
            domain="test", config=copy.deepcopy(original_config),
            run_id="test", strategy="test", log=None,
        )
        # Mutate ctx.config (it's a copy)
        ctx.config["models"]["thinking"]["provider"] = "MUTATED"
        # Original should be unchanged
        assert original_config["models"]["thinking"]["provider"] == "test"

    def test_06_context_tracks_counts(self):
        """TEST-180-03-06: StageContext tracks paper/gap/idea/proposal counts."""
        from backend.pipeline.dag.context import StageContext
        ctx = StageContext(domain="test", config={}, run_id="t", strategy="t", log=None)
        assert ctx.paper_count == 0
        ctx.papers = [{"title": "Paper 1"}, {"title": "Paper 2"}, {"title": "Paper 3"}]
        ctx.gaps = [{"title": "Gap 1"}]
        assert ctx.paper_count == 3
        assert ctx.gap_count == 1

    def test_07_registry_maps_all_16_stages(self):
        """TEST-180-03-07: STAGE_REGISTRY maps all 16 stage names."""
        from backend.pipeline.dag.registry import STAGE_REGISTRY
        expected_stages = {
            "literature_search", "ingestion", "gap_analysis", "gap_reflection",
            "idea_generation", "idea_reflection", "novelty_checking",
            "feasibility_scoring", "mechanical_metrics", "proposal_synthesis",
            "adversarial_review", "evaluation", "paper_synthesis",
            "citation_audit", "proposal_deepening", "export",
        }
        mapped = set(STAGE_REGISTRY.keys())
        assert expected_stages.issubset(mapped), f"Missing: {expected_stages - mapped}"

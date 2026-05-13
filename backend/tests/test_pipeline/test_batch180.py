"""BATCH-180 tests: ConfigLoader, StageLogger, DAGRunner.

18 tests covering all 3 tasks:
  TEST-180-01-01 through TEST-180-01-06  (ConfigLoader)
  TEST-180-02-01 through TEST-180-02-05  (StageLogger)
  TEST-180-03-01 through TEST-180-03-07  (DAGRunner)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

# ── Module under test ─────────────────────────────────────────
from backend.pipeline.dag.config import ConfigLoader
from backend.pipeline.dag.stage_log import REQUIRED_FIELDS, StageLogger
from backend.pipeline.dag.context import StageContext
from backend.pipeline.dag.registry import STAGE_REGISTRY, ALL_STAGES
from backend.pipeline.dag.runner import DAGRunner


# ═══════════════════════════════════════════════════════════════
# TASK-01: ConfigLoader Tests
# ═══════════════════════════════════════════════════════════════


class TestConfigLoader:
    """TEST-180-01-xx: ConfigLoader reads pipeline.yaml."""

    @pytest.fixture()
    def default_yaml(self, tmp_path: Path) -> Path:
        """Write a valid pipeline.yaml to a temp directory."""
        config = {
            "models": {
                "thinking": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "generation": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "embedding": {"provider": "openai", "model": "text-embedding-3-small", "dimension": 1536, "base_url": "https://api.openai.com/v1"},
                "reranker": {"strategy": "llm", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
            },
            "infrastructure": {
                "chroma_dir": "data/chroma",
                "bm25_dir": "data/bm25",
                "database": "data/research.db",
                "server": {"host": "0.0.0.0", "port": 8000},
            },
            "budgets": {
                "max_papers": 50, "max_gaps": 30, "max_ideas": 20,
                "max_abstract_chars": 500, "trim_top_k": 10,
                "stage_timeout": 300, "total_timeout": 1800,
            },
            "search": {
                "sources": ["crossref", "openalex", "semantic_scholar"],
                "queries_per_source": 5,
                "citation_explore": True,
            },
            "strategies": {
                "deep_research": {
                    "stages": ["literature_search", "gap_analysis", "idea_generation", "export"],
                    "description": "Full pipeline.",
                },
                "fast_scan": {
                    "stages": ["literature_search", "gap_analysis", "export"],
                    "description": "Quick scan.",
                },
                "academic_proposal": {
                    "stages": ["literature_search", "gap_analysis", "idea_generation", "export"],
                    "description": "Academic.",
                },
                "literature_review": {
                    "stages": ["literature_search", "gap_analysis", "export"],
                    "description": "Lit review.",
                },
            },
        }
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
        return yaml_file

    # TEST-180-01-01 ────────────────────────────────────────────
    def test_reads_yaml_returns_dict(self, default_yaml: Path):
        """ConfigLoader reads pipeline.yaml and returns dict."""
        loader = ConfigLoader(yaml_path=default_yaml)
        config = loader.load()
        assert isinstance(config, dict)
        assert config["models"]["thinking"]["provider"] == "openai"

    # TEST-180-01-02 ────────────────────────────────────────────
    def test_validates_required_fields(self, tmp_path: Path):
        """ConfigLoader raises ValueError on missing required fields."""
        # Write YAML without budgets section
        bad_config = {"models": {"thinking": {"provider": "x"}}, "infrastructure": {}, "search": {}, "strategies": {}}
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml.dump(bad_config), encoding="utf-8")
        loader = ConfigLoader(yaml_path=yaml_file)
        with pytest.raises(ValueError, match="budget"):
            loader.load()

    # TEST-180-01-03 ────────────────────────────────────────────
    def test_snapshot_is_immutable_copy(self, default_yaml: Path):
        """ConfigLoader returns independent deep copies (AUTH-01)."""
        loader = ConfigLoader(yaml_path=default_yaml)
        snap1 = loader.load()
        snap1["models"]["thinking"]["provider"] = "MUTATED"
        snap2 = loader.load()
        assert snap2["models"]["thinking"]["provider"] == "openai"

    # TEST-180-01-04 ────────────────────────────────────────────
    def test_all_four_strategies_present(self, default_yaml: Path):
        """All 4 strategies present in config."""
        loader = ConfigLoader(yaml_path=default_yaml)
        config = loader.load()
        assert len(config["strategies"]) == 4
        for name in ("deep_research", "fast_scan", "academic_proposal", "literature_review"):
            assert name in config["strategies"]

    # TEST-180-01-05 ────────────────────────────────────────────
    def test_strategy_has_stages_and_description(self, default_yaml: Path):
        """Each strategy has stages list and description."""
        loader = ConfigLoader(yaml_path=default_yaml)
        config = loader.load()
        for name, strat in config["strategies"].items():
            assert "stages" in strat, f"Strategy '{name}' missing 'stages'"
            assert "description" in strat, f"Strategy '{name}' missing 'description'"
            assert isinstance(strat["stages"], list)
            assert len(strat["stages"]) > 0

    # TEST-180-01-06 ────────────────────────────────────────────
    def test_resolves_relative_paths_to_absolute(self, tmp_path: Path):
        """ConfigLoader resolves relative paths to absolute."""
        config = {
            "models": {
                "thinking": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "generation": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "embedding": {"provider": "openai", "model": "text-embedding-3-small", "base_url": "https://api.openai.com/v1"},
                "reranker": {"strategy": "llm", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
            },
            "infrastructure": {
                "chroma_dir": "data/chroma",
                "bm25_dir": "data/bm25",
                "database": "data/research.db",
                "server": {"host": "0.0.0.0", "port": 8000},
            },
            "budgets": {
                "max_papers": 50, "max_gaps": 30, "max_ideas": 20,
                "max_abstract_chars": 500, "trim_top_k": 10,
                "stage_timeout": 300, "total_timeout": 1800,
            },
            "search": {"sources": ["x"], "queries_per_source": 1, "citation_explore": True},
            "strategies": {
                "fast_scan": {"stages": ["export"], "description": "test"},
                "deep_research": {"stages": ["export"], "description": "test"},
                "academic_proposal": {"stages": ["export"], "description": "test"},
                "literature_review": {"stages": ["export"], "description": "test"},
            },
        }
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml.dump(config), encoding="utf-8")
        loader = ConfigLoader(yaml_path=yaml_file)
        loaded = loader.load()
        for key in ("chroma_dir", "bm25_dir", "database"):
            assert os.path.isabs(loaded["infrastructure"][key]), f"{key} not absolute"

    # TEST-180-01-01 variant ────────────────────────────────────
    def test_missing_yaml_raises_file_not_found(self, tmp_path: Path):
        """FileNotFoundError when YAML doesn't exist."""
        loader = ConfigLoader(yaml_path=tmp_path / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            loader.load()


# ═══════════════════════════════════════════════════════════════
# TASK-02: StageLogger Tests
# ═══════════════════════════════════════════════════════════════


class TestStageLogger:
    """TEST-180-02-xx: StageLogger writes one JSON entry per stage."""

    @pytest.fixture()
    def logger(self, tmp_path: Path) -> StageLogger:
        return StageLogger(run_id="test-run-001", log_dir=tmp_path / "logs")

    # TEST-180-02-01 ────────────────────────────────────────────
    def test_writes_entry_with_all_required_fields(self, logger: StageLogger):
        """StageLogger writes JSON entry with all required fields (HB-03)."""
        logger.log(
            stage="gap_analysis",
            event="complete",
            elapsed_s=1.234,
            config={"model": "gpt-4o"},
            inputs={"papers_count": 10},
            outputs={"gaps_count": 3},
        )
        entries = logger.read_entries()
        assert len(entries) == 1
        entry = entries[0]
        for field_name in REQUIRED_FIELDS:
            assert field_name in entry, f"Missing required field: {field_name}"

    # TEST-180-02-02 ────────────────────────────────────────────
    def test_appends_not_overwrites(self, logger: StageLogger):
        """StageLogger appends entries (not overwrites)."""
        logger.log(stage="stage_a", event="complete", elapsed_s=0.1)
        logger.log(stage="stage_b", event="complete", elapsed_s=0.2)
        entries = logger.read_entries()
        assert len(entries) == 2
        assert entries[0]["stage"] == "stage_a"
        assert entries[1]["stage"] == "stage_b"

    # TEST-180-02-03 ────────────────────────────────────────────
    def test_error_entry_captures_error(self, logger: StageLogger):
        """StageLogger handles error entries correctly."""
        logger.log_error(
            stage="idea_generation",
            event="error",
            elapsed_s=5.0,
            error="API rate limit exceeded",
        )
        entries = logger.read_entries()
        assert len(entries) == 1
        assert entries[0]["error"] is not None
        assert "rate limit" in entries[0]["error"]

    # TEST-180-02-04 ────────────────────────────────────────────
    def test_creates_log_directory_if_missing(self, tmp_path: Path):
        """StageLogger creates log directory if missing."""
        log_dir = tmp_path / "nested" / "deep" / "logs"
        assert not log_dir.exists()
        logger = StageLogger(run_id="dir-test", log_dir=log_dir)
        logger.log(stage="test", event="complete", elapsed_s=0.0)
        assert log_dir.exists()
        assert logger.log_file.exists()

    # TEST-180-02-05 ────────────────────────────────────────────
    def test_input_output_counts_are_integers(self, logger: StageLogger):
        """StageLogger input/output counts are integers."""
        logger.log(
            stage="gap_analysis",
            event="complete",
            elapsed_s=1.0,
            inputs={"papers_count": 10.0, "queries_count": 5.5},
            outputs={"gaps_count": 3.0},
        )
        entries = logger.read_entries()
        assert len(entries) == 1
        assert isinstance(entries[0]["inputs"]["papers_count"], int)
        assert isinstance(entries[0]["inputs"]["queries_count"], int)
        assert isinstance(entries[0]["outputs"]["gaps_count"], int)


# ═══════════════════════════════════════════════════════════════
# TASK-03: DAGRunner + StageContext + Registry Tests
# ═══════════════════════════════════════════════════════════════


class TestDAGRunner:
    """TEST-180-03-xx: DAGRunner builds plans and executes stages."""

    @pytest.fixture()
    def runner(self, tmp_path: Path) -> DAGRunner:
        """Create a DAGRunner with a temp YAML config."""
        config = {
            "models": {
                "thinking": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "generation": {"provider": "openai", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
                "embedding": {"provider": "openai", "model": "text-embedding-3-small", "base_url": "https://api.openai.com/v1"},
                "reranker": {"strategy": "llm", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
            },
            "infrastructure": {
                "chroma_dir": str(tmp_path / "chroma"),
                "bm25_dir": str(tmp_path / "bm25"),
                "database": str(tmp_path / "research.db"),
                "server": {"host": "0.0.0.0", "port": 8000},
            },
            "budgets": {
                "max_papers": 50, "max_gaps": 30, "max_ideas": 20,
                "max_abstract_chars": 500, "trim_top_k": 10,
                "stage_timeout": 300, "total_timeout": 1800,
            },
            "search": {"sources": ["x"], "queries_per_source": 1, "citation_explore": True},
            "strategies": {
                "deep_research": {
                    "stages": [
                        "literature_search", "ingestion", "gap_analysis",
                        "gap_reflection", "idea_generation", "idea_reflection",
                        "novelty_checking", "feasibility_scoring", "mechanical_metrics",
                        "proposal_synthesis", "adversarial_review", "evaluation",
                        "paper_synthesis", "citation_audit", "proposal_deepening", "export",
                    ],
                    "description": "Full pipeline.",
                },
                "fast_scan": {
                    "stages": ["literature_search", "ingestion", "gap_analysis", "feasibility_scoring", "proposal_synthesis", "export"],
                    "description": "Quick scan.",
                },
                "academic_proposal": {
                    "stages": [
                        "literature_search", "ingestion", "gap_analysis",
                        "gap_reflection", "idea_generation", "idea_reflection",
                        "novelty_checking", "feasibility_scoring", "mechanical_metrics",
                        "proposal_synthesis", "adversarial_review", "evaluation",
                        "paper_synthesis", "citation_audit", "proposal_deepening", "export",
                    ],
                    "description": "Academic.",
                },
                "literature_review": {
                    "stages": ["literature_search", "ingestion", "gap_analysis", "export"],
                    "description": "Lit review.",
                },
            },
        }
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
        loader = ConfigLoader(yaml_path=yaml_file)
        return DAGRunner(config_loader=loader, log_dir=str(tmp_path / "logs"))

    # TEST-180-03-01 ────────────────────────────────────────────
    def test_build_plan_returns_correct_stages(self, runner: DAGRunner):
        """DAGRunner.build_plan returns correct stage list."""
        plan = runner.build_plan("fast_scan")
        assert "idea_generation" not in plan
        assert "literature_search" in plan
        assert "gap_analysis" in plan
        assert "export" in plan

    # TEST-180-03-02 ────────────────────────────────────────────
    def test_build_plan_validates_strategy_name(self, runner: DAGRunner):
        """DAGRunner.build_plan raises ValueError for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            runner.build_plan("nonexistent_strategy")

    # TEST-180-03-03 ────────────────────────────────────────────
    def test_dry_run_prints_plan_without_executing(self, runner: DAGRunner):
        """dry_run prints stage list without executing (AUTH-03)."""
        output = runner.dry_run(domain="AI", strategy="fast_scan")
        assert "dry_run" in output
        assert "fast_scan" in output
        # Should NOT have created any log files
        log_dir = Path(runner._log_dir)
        if log_dir.exists():
            jsonl_files = list(log_dir.glob("*.jsonl"))
            assert len(jsonl_files) == 0, "dry_run should not write log entries"

    # TEST-180-03-04 ────────────────────────────────────────────
    def test_dry_run_shows_model_assignment(self, runner: DAGRunner):
        """dry_run prints model assignment per stage."""
        output = runner.dry_run(domain="AI", strategy="deep_research")
        assert "thinking" in output
        assert "generation" in output
        # Verify a specific stage shows its model category
        assert "gpt-4o" in output

    # TEST-180-03-05 ────────────────────────────────────────────
    def test_stage_context_config_is_immutable(self):
        """StageContext config is immutable (AUTH-01)."""
        original_config = {"models": {"thinking": {"provider": "openai"}}}
        ctx = StageContext(domain="AI", config=original_config)
        with pytest.raises(AttributeError, match="read-only"):
            ctx.config = {"MUTATED": True}
        # Original dict should be unchanged
        assert original_config["models"]["thinking"]["provider"] == "openai"

    # TEST-180-03-06 ────────────────────────────────────────────
    def test_stage_context_tracks_counts(self):
        """StageContext tracks paper/gap/idea/proposal counts."""
        ctx = StageContext(
            domain="AI",
            papers=["p1", "p2", "p3"],
            gaps=["g1"],
            ideas=["i1", "i2"],
            proposals={0: "prop1"},
        )
        assert ctx.paper_count == 3
        assert ctx.gap_count == 1
        assert ctx.idea_count == 2
        assert ctx.proposal_count == 1

    # TEST-180-03-07 ────────────────────────────────────────────
    def test_stage_registry_has_all_16_stages(self):
        """STAGE_REGISTRY maps all 16 stage names."""
        assert len(STAGE_REGISTRY) >= 16
        expected_stages = {
            "literature_search", "ingestion", "gap_analysis", "gap_reflection",
            "idea_generation", "idea_reflection", "novelty_checking",
            "feasibility_scoring", "mechanical_metrics", "proposal_synthesis",
            "adversarial_review", "evaluation", "paper_synthesis",
            "citation_audit", "proposal_deepening", "export",
        }
        assert expected_stages.issubset(set(STAGE_REGISTRY.keys()))
        # Also verify ALL_STAGES list
        assert len(ALL_STAGES) == 16

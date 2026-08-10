"""Tests for BATCH-182: Dataset Generator + Eval Sidecar."""

import json
import os
import sqlite3
import tempfile

# ── TASK-01: Dataset Generator ────────────────────────────────────────


class TestDatasetGenerator:
    """TEST-182-01-01 through TEST-182-01-05."""

    def _make_test_db(self, tmpdir: str) -> str:
        """Create a minimal test DB with completed runs."""
        db_path = os.path.join(tmpdir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE pipeline_runs (
                id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                domain TEXT DEFAULT 'AI/NLP',
                config_json TEXT DEFAULT '{}',
                current_stage TEXT,
                stages_completed TEXT DEFAULT '[]',
                stage_report_json TEXT,
                created_at TEXT,
                completed_at TEXT,
                session_id TEXT
            );
            CREATE TABLE research_gaps (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT DEFAULT '',
                gap_type TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                pipeline_run_id INTEGER
            );
            CREATE TABLE ideas (
                id INTEGER PRIMARY KEY,
                title TEXT,
                problem_statement TEXT DEFAULT '',
                proposed_method TEXT DEFAULT '',
                expected_contributions TEXT DEFAULT '',
                domain TEXT DEFAULT 'AI/NLP',
                novelty_score REAL,
                feasibility_score REAL,
                overall_score REAL,
                pipeline_run_id INTEGER
            );
            CREATE TABLE proposals (
                id INTEGER PRIMARY KEY,
                idea_id INTEGER,
                content_md TEXT DEFAULT '',
                references_json TEXT DEFAULT '[]'
            );
        """)
        # Insert a completed run
        conn.execute(
            "INSERT INTO pipeline_runs (id, status, domain, stages_completed, created_at, completed_at) "
            "VALUES (1, 'completed', 'Test Domain', '[\"gap_analysis\",\"export\"]', "
            "'2026-05-13T08:00:00', '2026-05-13T08:10:00')"
        )
        conn.execute(
            "INSERT INTO research_gaps (id, title, confidence, gap_type, pipeline_run_id) "
            "VALUES (1, 'Test Gap', 0.85, 'methodological', 1)"
        )
        conn.execute(
            "INSERT INTO ideas (id, title, novelty_score, feasibility_score, overall_score, pipeline_run_id) "
            "VALUES (1, 'Test Idea', 0.9, 0.8, 0.85, 1)"
        )
        conn.execute(
            "INSERT INTO proposals (id, idea_id, content_md) VALUES (1, 1, 'A test proposal with some words')"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_01_generates_json_from_db(self):
        """TEST-182-01-01: Dataset generator produces valid JSON."""
        from backend.pipeline.dag.dataset_generator import generate_benchmark

        tmpdir = tempfile.mkdtemp()
        db_path = self._make_test_db(tmpdir)
        output = os.path.join(tmpdir, "bench.json")

        result = generate_benchmark(db_path, output)
        assert result["run_count"] == 1
        assert os.path.exists(output)

        # Verify JSON is valid
        with open(output) as f:
            loaded = json.load(f)
        assert loaded["run_count"] == 1

    def test_02_includes_run_fields(self):
        """TEST-182-01-02: Each run entry has required fields."""
        from backend.pipeline.dag.dataset_generator import generate_benchmark

        tmpdir = tempfile.mkdtemp()
        db_path = self._make_test_db(tmpdir)
        result = generate_benchmark(db_path, os.path.join(tmpdir, "bench.json"))

        run = result["runs"][0]
        for field in ["db_id", "domain", "gaps_count", "ideas_count", "proposals_count"]:
            assert field in run, f"Missing field: {field}"

    def test_03_includes_gap_and_idea_data(self):
        """TEST-182-01-03: Run entry includes gap titles and idea scores."""
        from backend.pipeline.dag.dataset_generator import generate_benchmark

        tmpdir = tempfile.mkdtemp()
        db_path = self._make_test_db(tmpdir)
        result = generate_benchmark(db_path, os.path.join(tmpdir, "bench.json"))

        run = result["runs"][0]
        assert len(run["gaps"]) == 1
        assert run["gaps"][0]["title"] == "Test Gap"
        assert run["gaps"][0]["confidence"] == 0.85
        assert len(run["ideas"]) == 1
        assert run["ideas"][0]["overall"] == 0.85

    def test_04_computes_elapsed_time(self):
        """TEST-182-01-04: Run entry includes computed elapsed time."""
        from backend.pipeline.dag.dataset_generator import generate_benchmark

        tmpdir = tempfile.mkdtemp()
        db_path = self._make_test_db(tmpdir)
        result = generate_benchmark(db_path, os.path.join(tmpdir, "bench.json"))

        run = result["runs"][0]
        assert run["elapsed_s"] == 600.0  # 10 minutes

    def test_05_empty_db_produces_empty_benchmark(self):
        """TEST-182-01-05: Empty database produces zero-run benchmark."""
        from backend.pipeline.dag.dataset_generator import generate_benchmark

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "empty.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE pipeline_runs (id INTEGER PRIMARY KEY, status TEXT, domain TEXT, config_json TEXT, current_stage TEXT, stages_completed TEXT, stage_report_json TEXT, created_at TEXT, completed_at TEXT, session_id TEXT)")
        conn.execute("CREATE TABLE research_gaps (id INTEGER PRIMARY KEY, title TEXT, description TEXT, gap_type TEXT, confidence REAL, pipeline_run_id INTEGER)")
        conn.execute("CREATE TABLE ideas (id INTEGER PRIMARY KEY, title TEXT, problem_statement TEXT, proposed_method TEXT, expected_contributions TEXT, domain TEXT, novelty_score REAL, feasibility_score REAL, overall_score REAL, pipeline_run_id INTEGER)")
        conn.execute("CREATE TABLE proposals (id INTEGER PRIMARY KEY, idea_id INTEGER, content_md TEXT, references_json TEXT)")
        conn.commit()
        conn.close()

        result = generate_benchmark(db_path, os.path.join(tmpdir, "bench.json"))
        assert result["run_count"] == 0
        assert result["runs"] == []


# ── TASK-02: Eval Sidecar ─────────────────────────────────────────────


class TestEvalSidecar:
    """TEST-182-02-01 through TEST-182-02-06."""

    def _make_test_logs(self, tmpdir: str, run_id: str = "run_test") -> str:
        """Create test stage log JSONL file."""
        logs_dir = os.path.join(tmpdir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"{run_id}.jsonl")

        entries = [
            {
                "run_id": run_id,
                "stage": "literature_search",
                "event": "complete",
                "elapsed_s": 5.2,
                "config": {"model_category": "thinking"},
                "inputs": {"papers": 0},
                "outputs": {"gaps": 0, "ideas": 0, "proposals": 0},
                "error": None,
                "timestamp": "2026-05-13T08:00:00Z",
            },
            {
                "run_id": run_id,
                "stage": "gap_analysis",
                "event": "complete",
                "elapsed_s": 42.1,
                "config": {"model_category": "thinking"},
                "inputs": {"papers": 36},
                "outputs": {"gaps": 5, "ideas": 0, "proposals": 0},
                "error": None,
                "timestamp": "2026-05-13T08:00:47Z",
            },
            {
                "run_id": run_id,
                "stage": "idea_generation",
                "event": "complete",
                "elapsed_s": 95.0,
                "config": {"model_category": "thinking"},
                "inputs": {"papers": 36},
                "outputs": {"gaps": 0, "ideas": 2, "proposals": 0},
                "error": None,
                "timestamp": "2026-05-13T08:02:22Z",
            },
        ]

        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return logs_dir

    def test_01_loads_stage_logs(self):
        """TEST-182-02-01: Sidecar loads stage log entries."""
        from backend.pipeline.dag.eval_sidecar import _load_stage_logs

        tmpdir = tempfile.mkdtemp()
        logs_dir = self._make_test_logs(tmpdir)
        logs = _load_stage_logs(logs_dir, "run_test")
        assert len(logs) == 3

    def test_02_computes_total_elapsed(self):
        """TEST-182-02-02: Sidecar computes total elapsed time."""
        from backend.pipeline.dag.eval_sidecar import evaluate_run

        tmpdir = tempfile.mkdtemp()
        logs_dir = self._make_test_logs(tmpdir)
        db_path = os.path.join(tmpdir, "metrics.db")
        metrics = evaluate_run("run_test", logs_dir, db_path=db_path)
        assert metrics["total_elapsed_s"] == 142.3  # 5.2 + 42.1 + 95.0

    def test_03_detects_slowest_stage(self):
        """TEST-182-02-03: Sidecar identifies the slowest stage."""
        from backend.pipeline.dag.eval_sidecar import evaluate_run

        tmpdir = tempfile.mkdtemp()
        logs_dir = self._make_test_logs(tmpdir)
        db_path = os.path.join(tmpdir, "metrics.db")
        metrics = evaluate_run("run_test", logs_dir, db_path=db_path)
        assert metrics["slowest_stage"] == "idea_generation"
        assert metrics["slowest_stage_elapsed_s"] == 95.0

    def test_04_computes_pipeline_ratios(self):
        """TEST-182-02-04: Sidecar computes papers-to-ideas ratio."""
        from backend.pipeline.dag.eval_sidecar import evaluate_run

        tmpdir = tempfile.mkdtemp()
        logs_dir = self._make_test_logs(tmpdir)
        db_path = os.path.join(tmpdir, "metrics.db")
        metrics = evaluate_run("run_test", logs_dir, db_path=db_path)
        # Total papers_in across logs = 0 + 36 + 36 = 72
        # Total ideas_out = 0 + 0 + 2 = 2
        assert metrics["papers_to_ideas_ratio"] == round(2 / 72, 3)

    def test_05_persists_to_sqlite(self):
        """TEST-182-02-05: Sidecar writes metrics to SQLite."""
        from backend.pipeline.dag.eval_sidecar import evaluate_run

        tmpdir = tempfile.mkdtemp()
        logs_dir = self._make_test_logs(tmpdir)
        db_path = os.path.join(tmpdir, "metrics.db")
        metrics = evaluate_run("run_test", logs_dir, db_path=db_path)

        # Verify it was written to SQLite
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT run_id, total_elapsed_s, stage_count FROM dag_evaluation_metrics WHERE run_id = ?",
            ("run_test",),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "run_test"
        assert row[1] == 142.3
        assert row[2] == 3

    def test_06_handles_missing_logs(self):
        """TEST-182-02-06: Sidecar handles missing log files gracefully."""
        from backend.pipeline.dag.eval_sidecar import evaluate_run

        tmpdir = tempfile.mkdtemp()
        metrics = evaluate_run("nonexistent_run", tmpdir, db_path=os.path.join(tmpdir, "metrics.db"))
        assert "error" in metrics
        assert metrics["error"] == "no_logs_found"

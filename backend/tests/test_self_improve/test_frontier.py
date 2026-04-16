"""Tests for Pareto frontier and pipeline evolution."""

from backend.pipeline.self_improve.frontier import FrontierPoint, FrontierType, ParetoFrontier
from backend.pipeline.self_improve.evolution import PipelineEvolver


class TestParetoFrontier:
    def test_add_first_point(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        point = FrontierPoint(
            params={"generation_rounds": 2},
            scores={"quality": 0.8, "novelty": 0.7},
        )
        assert frontier.add(point) is True  # First point is always non-dominated

    def test_dominated_point_not_pareto(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 2},
            scores={"quality": 0.9, "novelty": 0.9},
        ))
        result = frontier.add(FrontierPoint(
            params={"generation_rounds": 3},
            scores={"quality": 0.5, "novelty": 0.5},
        ))
        assert result is False  # Dominated

    def test_non_comparable_points_both_pareto(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 2},
            scores={"quality": 0.9, "novelty": 0.5},
        ))
        result = frontier.add(FrontierPoint(
            params={"generation_rounds": 3},
            scores={"quality": 0.5, "novelty": 0.9},
        ))
        assert result is True  # Not dominated — different objective is better
        assert frontier.frontier_size == 2

    def test_new_dominant_removes_old(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 2},
            scores={"quality": 0.5, "novelty": 0.5},
        ))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 3},
            scores={"quality": 0.9, "novelty": 0.9},
        ))
        assert frontier.frontier_size == 1

    def test_get_best(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 2},
            scores={"quality": 0.9, "novelty": 0.5},
        ))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 3},
            scores={"quality": 0.5, "novelty": 0.9},
        ))
        best_quality = frontier.get_best(FrontierType.QUALITY)
        assert best_quality is not None
        assert best_quality.scores["quality"] == 0.9

    def test_suggest_params_crossover(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 2, "temperature": 0.8},
            scores={"quality": 0.9},
        ))
        frontier.add(FrontierPoint(
            params={"generation_rounds": 4, "temperature": 0.5},
            scores={"novelty": 0.9},
        ))
        params = frontier.suggest_params()
        assert "generation_rounds" in params
        assert "temperature" in params
        # Should be between the two parents
        assert 2 <= params["generation_rounds"] <= 4

    def test_suggest_params_empty(self, tmp_path):
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        params = frontier.suggest_params()
        assert params == {}

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "f.json")
        f1 = ParetoFrontier(persist_path=path)
        f1.add(FrontierPoint(
            params={"generation_rounds": 3},
            scores={"quality": 0.85},
        ))
        f2 = ParetoFrontier(persist_path=path)
        assert f2.frontier_size == 1


class TestPipelineEvolver:
    def test_propose_defaults_when_empty(self, tmp_path):
        from backend.pipeline.self_improve.frontier import ParetoFrontier
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        evolver = PipelineEvolver(frontier)
        params = evolver.propose()
        assert params["generation_rounds"] == 2
        assert params["ideas_per_round"] == 3

    def test_evaluate_records_point(self, tmp_path):
        from backend.pipeline.self_improve.frontier import ParetoFrontier
        frontier = ParetoFrontier(persist_path=str(tmp_path / "f.json"))
        evolver = PipelineEvolver(frontier)

        point = evolver.evaluate(
            params={"generation_rounds": 3},
            run_id="test_run",
            avg_idea_score=0.75,
            avg_novelty_score=0.6,
        )
        assert point.scores["quality"] == 0.75
        assert frontier.frontier_size == 1

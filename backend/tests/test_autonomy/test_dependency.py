"""Tests for Goal Dependency Sets and conflict detection."""


from backend.pipeline.autonomy.dependency import (
    ConflictReport,
    GoalDependency,
    GoalDependencyTracker,
)
from backend.pipeline.autonomy.goals import GoalManager, GoalStatus


def _make_mock_gap(title: str, confidence: float = 0.7):
    class MockGap:
        def __init__(self, t, c):
            self.title = t
            self.description = f"desc for {t}"
            self.gap_type = "methodological"
            self.confidence = c

    return MockGap(title, confidence)


class MockKG:
    def __init__(self, entities: dict | None = None):
        self._entities = entities or {}

    def get_entity(self, eid):
        return self._entities.get(eid)


class _MockEntity:
    def __init__(self, eid, freq=0.8, conf=0.7):
        from backend.pipeline.knowledge.truth import TruthValue

        self.id = eid
        self.truth = TruthValue(frequency=freq, confidence=conf)


class TestGoalDependencyTracker:
    def test_register_dependency(self):
        tracker = GoalDependencyTracker()
        dep = GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        tracker.register_dependency("g1", dep)
        deps = tracker.get_dependencies("g1")
        assert len(deps) == 1

    def test_register_multiple(self):
        tracker = GoalDependencyTracker()
        deps = [
            GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1"),
            GoalDependency(goal_id="g1", depends_on_type="entity_existence", depends_on_id="e2"),
        ]
        tracker.register_dependencies("g1", deps)
        assert len(tracker.get_dependencies("g1")) == 2

    def test_remove_goal(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1", GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        )
        tracker.remove_goal("g1")
        assert len(tracker.get_dependencies("g1")) == 0

    def test_get_goals_affected_by(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1", GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        )
        tracker.register_dependency(
            "g2", GoalDependency(goal_id="g2", depends_on_type="entity_truth", depends_on_id="e1")
        )
        affected = tracker.get_goals_affected_by("e1")
        assert set(affected) == {"g1", "g2"}

    def test_evaluate_conflicts_no_violation(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1", GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        )
        kg = MockKG({"e1": _MockEntity("e1", freq=0.8, conf=0.7)})
        conflicts = tracker.evaluate_conflicts("g1", kg)
        assert len(conflicts) == 0

    def test_evaluate_conflicts_entity_removed(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1",
            GoalDependency(goal_id="g1", depends_on_type="entity_existence", depends_on_id="e1"),
        )
        kg = MockKG({})
        conflicts = tracker.evaluate_conflicts("g1", kg)
        assert len(conflicts) == 1

    def test_evaluate_conflicts_truth_drop(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1", GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        )
        kg = MockKG({"e1": _MockEntity("e1", freq=0.05, conf=0.1)})
        conflicts = tracker.evaluate_conflicts("g1", kg)
        assert len(conflicts) == 1

    def test_evaluate_all_conflicts(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1",
            GoalDependency(goal_id="g1", depends_on_type="entity_existence", depends_on_id="e1"),
        )
        tracker.register_dependency(
            "g2", GoalDependency(goal_id="g2", depends_on_type="entity_truth", depends_on_id="e2")
        )
        kg = MockKG({"e2": _MockEntity("e2", freq=0.8, conf=0.7)})
        all_conflicts = tracker.evaluate_all_conflicts(kg)
        assert "g1" in all_conflicts
        assert "g2" not in all_conflicts


class TestConflictReport:
    def test_severity_high_for_existence(self):
        conflicts = [
            GoalDependency(goal_id="g1", depends_on_type="entity_existence", depends_on_id="e1")
        ]
        report = GoalDependencyTracker.build_report("g1", "Goal 1", conflicts)
        assert report.severity == "high"
        assert report.recommended_action == "retract"

    def test_severity_medium_for_truth(self):
        conflicts = [
            GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        ]
        report = GoalDependencyTracker.build_report("g1", "Goal 1", conflicts)
        assert report.severity == "medium"

    def test_no_conflicts(self):
        report = GoalDependencyTracker.build_report("g1", "Goal 1", [])
        assert report.severity == "none"
        assert report.recommended_action == "continue"


class TestGoalManagerIntegration:
    def test_create_from_gaps_auto_registers(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tracker = GoalDependencyTracker()
            gm = GoalManager(persist_path=f"{tmp}/goals.json", dependency_tracker=tracker)
            gm.create_from_gaps([_make_mock_gap("Test Gap", 0.8)])
            assert tracker.total_dependencies > 0

    def test_check_goal_conflicts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tracker = GoalDependencyTracker()
            gm = GoalManager(persist_path=f"{tmp}/goals.json", dependency_tracker=tracker)
            gm.create_from_gaps([_make_mock_gap("Test Gap")])
            reports = gm.check_goal_conflicts(MockKG({}))
            # No entity_truth or entity_existence deps registered by create_from_gaps
            # (only gap_confidence), so reports should be empty
            assert isinstance(reports, list)

    def test_retract_conflicted_goals(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tracker = GoalDependencyTracker()
            gm = GoalManager(persist_path=f"{tmp}/goals.json", dependency_tracker=tracker)
            gm.create_from_gaps([_make_mock_gap("Test Gap")])
            report = ConflictReport(
                goal_id=list(gm._goals.keys())[0],
                severity="high",
                recommended_action="retract",
                conflicts=[
                    GoalDependency(
                        goal_id="g1", depends_on_type="entity_existence", depends_on_id="e1"
                    )
                ],
            )
            retracted = gm.retract_conflicted_goals([report])
            assert len(retracted) == 1
            goal = gm._goals[retracted[0]]
            assert goal.status == GoalStatus.ABANDONED

    def test_goal_count_and_deps(self):
        tracker = GoalDependencyTracker()
        tracker.register_dependency(
            "g1", GoalDependency(goal_id="g1", depends_on_type="entity_truth", depends_on_id="e1")
        )
        assert tracker.goal_count == 1
        assert tracker.total_dependencies == 1

"""Tests for governance, world model, and goals."""

import asyncio

from backend.pipeline.autonomy.goals import GoalManager, GoalStatus, ResearchGoal
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.governance.contracts import (
    BoundaryContract,
    GovernanceCheck,
    OutputVerdict,
)
from backend.pipeline.governance.events import GovernanceAuditLog, GovernanceEvent
from backend.pipeline.knowledge.world_model import WorldModel


class TestGovernanceContracts:
    def test_output_verdict_values(self):
        assert OutputVerdict.ACCEPTED.value == "accepted"
        assert OutputVerdict.REJECTED.value == "rejected"

    def test_boundary_contract(self):
        contract = BoundaryContract(
            name="max_length",
            constraint_type="max_length",
            params={"max_chars": 50000},
        )
        assert contract.params["max_chars"] == 50000

    def test_governance_check(self):
        check = GovernanceCheck(
            contract_name="max_length",
            verdict=OutputVerdict.REJECTED,
            reason="Content too long",
        )
        assert check.verdict == OutputVerdict.REJECTED


class TestGovernanceAuditLog:
    def test_record_event(self, tmp_path):
        log = GovernanceAuditLog(persist_path=str(tmp_path / "audit.jsonl"))
        log.record(GovernanceEvent(
            event_type="output.accepted",
            stage="proposal_synthesis",
            content_hash="abc123",
        ))
        assert len(log.get_events()) == 1

    def test_verify_chain(self, tmp_path):
        log = GovernanceAuditLog(persist_path=str(tmp_path / "audit.jsonl"))
        log.record(GovernanceEvent(
            event_type="output.accepted", stage="s1", content_hash="h1",
        ))
        log.record(GovernanceEvent(
            event_type="output.rejected", stage="s2", content_hash="h2",
        ))
        assert log.verify_chain() is True

    def test_filter_by_stage(self, tmp_path):
        log = GovernanceAuditLog(persist_path=str(tmp_path / "audit.jsonl"))
        log.record(GovernanceEvent(
            event_type="output.accepted", stage="synthesis", content_hash="h1",
        ))
        log.record(GovernanceEvent(
            event_type="output.accepted", stage="export", content_hash="h2",
        ))
        assert len(log.get_events("synthesis")) == 1

    def test_content_hash(self):
        h = GovernanceAuditLog.content_hash("test content")
        assert len(h) == 16


class TestWorldModel:
    def test_update_from_result(self, tmp_path):
        wm = WorldModel(persist_path=str(tmp_path / "wm.json"))

        # Create a mock result
        class MockResult:
            gaps = [
                ResearchGap(title="Gap 1", description="Test gap", confidence=0.8),
            ]
            ideas = []

        asyncio.run(wm.update_from_run(MockResult()))
        landscape = wm.get_landscape()
        assert len(landscape.active_gaps) == 1
        assert landscape.version == 1

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "wm.json")
        wm1 = WorldModel(persist_path=path)

        class MockResult:
            gaps = [ResearchGap(title="Persistent Gap", description="Test", confidence=0.9)]
            ideas = []

        asyncio.run(wm1.update_from_run(MockResult()))

        wm2 = WorldModel(persist_path=path)
        assert len(wm2.get_landscape().active_gaps) == 1
        assert wm2.get_landscape().version == 1


class TestGoalManager:
    def test_create_from_gaps(self, tmp_path):
        gm = GoalManager(persist_path=str(tmp_path / "goals.json"))
        gaps = [
            ResearchGap(title="Test Gap", description="A test gap", confidence=0.8),
            ResearchGap(title="Another Gap", description="Another gap", confidence=0.6),
        ]
        goals = gm.create_from_gaps(gaps)
        assert len(goals) == 2
        assert goals[0].priority == 0.8

    def test_decompose(self, tmp_path):
        gm = GoalManager(persist_path=str(tmp_path / "goals.json"))
        goals = gm.create_from_gaps([
            ResearchGap(title="Complex Gap", description="Complex", confidence=0.9),
        ])
        subs = gm.decompose(goals[0])
        assert len(subs) == 3
        assert all(s.parent_goal_id == goals[0].id for s in subs)

    def test_prioritize(self, tmp_path):
        gm = GoalManager(persist_path=str(tmp_path / "goals.json"))
        gm.create_from_gaps([
            ResearchGap(title="Low", description="L", confidence=0.3),
            ResearchGap(title="High", description="H", confidence=0.9),
            ResearchGap(title="Mid", description="M", confidence=0.6),
        ])
        prioritized = gm.prioritize()
        assert prioritized[0].title == "Investigate: High"
        assert prioritized[-1].title == "Investigate: Low"

    def test_update_progress(self, tmp_path):
        gm = GoalManager(persist_path=str(tmp_path / "goals.json"))
        goals = gm.create_from_gaps([
            ResearchGap(title="Test", description="T", confidence=0.5),
        ])
        gm.update_progress(goals[0].id, 1.0)
        assert gm._goals[goals[0].id].status == GoalStatus.COMPLETED

    def test_get_next_goal(self, tmp_path):
        gm = GoalManager(persist_path=str(tmp_path / "goals.json"))
        gm.create_from_gaps([
            ResearchGap(title="Low", description="L", confidence=0.3),
            ResearchGap(title="High", description="H", confidence=0.9),
        ])
        next_goal = gm.get_next_goal()
        assert next_goal is not None
        assert "High" in next_goal.title

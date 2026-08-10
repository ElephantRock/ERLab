"""Tests for session + governance integration — policy with session context."""


from backend.pipeline.governance.condition_eval import evaluate
from backend.pipeline.governance.policy import GovernancePolicy, PolicyAction, PolicyRule
from backend.pipeline.session.manager import SessionManager
from backend.pipeline.session.models import SessionBudget


class TestSessionGovernanceIntegration:
    def test_session_budget_as_policy_context(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test", budget=SessionBudget(max_runs=3, max_total_cost_usd=10.0))
        mgr.register_run(s.id, "r1")
        mgr.complete_run(s.id, "r1", tokens_used=100, cost_usd=3.0)
        mgr.register_run(s.id, "r2")
        mgr.complete_run(s.id, "r2", tokens_used=200, cost_usd=4.0)

        budget = mgr.check_budget(s.id)
        assert budget["remaining_runs"] == 1
        assert budget["remaining_cost"] == 3.0

    def test_policy_with_session_context(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="over_budget",
                action=PolicyAction.DENY,
                condition="over_budget = True",
                scope="generate",
            ),
        ])
        decision = policy.evaluate("generate", "ideator", {"over_budget": True})
        assert decision.action == PolicyAction.DENY

    def test_policy_with_session_state(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="active_only",
                action=PolicyAction.DENY,
                condition="session_state != active",
                scope="generate",
            ),
        ])
        decision = policy.evaluate("generate", "ideator", {"session_state": "paused"})
        assert decision.action == PolicyAction.DENY

        decision2 = policy.evaluate("generate", "ideator", {"session_state": "active"})
        assert decision2.action == PolicyAction.ALLOW

    def test_policy_compound_session_budget(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="budget_and_runs",
                action=PolicyAction.GATE,
                condition="AND(remaining_runs < 2, total_cost > 8)",
                scope="generate",
            ),
        ])
        ctx = {"remaining_runs": 1, "total_cost": 9.0}
        decision = policy.evaluate("generate", "ideator", ctx)
        assert decision.action == PolicyAction.GATE
        assert decision.requires_human is True

    def test_condition_evaluator_with_session_data(self):
        ctx = {
            "session_id": "abc123",
            "session_state": "active",
            "run_count": 5,
            "total_tokens": 1_000_000,
            "total_cost": 25.0,
            "remaining_runs": 5,
            "remaining_cost": 25.0,
            "over_budget": False,
        }
        assert evaluate("AND(session_state = active, remaining_runs > 0)", ctx)
        assert evaluate("NOT(over_budget = True)", ctx)
        assert not evaluate("AND(over_budget = True, total_cost > 50)", ctx)

    def test_session_lifecycle_policy_integration(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test", budget=SessionBudget(max_runs=2))
        mgr.activate(s.id)
        mgr.register_run(s.id, "r1")
        mgr.complete_run(s.id, "r1")
        mgr.register_run(s.id, "r2")
        mgr.complete_run(s.id, "r2")

        budget = mgr.check_budget(s.id)
        assert budget["over_budget"] is False
        assert budget["remaining_runs"] == 0

    def test_or_condition_with_session_tags(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="restricted_domain",
                action=PolicyAction.DENY,
                condition="OR(tag = restricted, tag = confidential)",
                scope="generate",
            ),
        ])
        d1 = policy.evaluate("generate", "ideator", {"tag": "restricted"})
        assert d1.action == PolicyAction.DENY

        d2 = policy.evaluate("generate", "ideator", {"tag": "public"})
        assert d2.action == PolicyAction.ALLOW

    def test_not_condition_with_session_state(self):
        assert evaluate("NOT(session_state = ended)", {"session_state": "active"})
        assert not evaluate("NOT(session_state = ended)", {"session_state": "ended"})

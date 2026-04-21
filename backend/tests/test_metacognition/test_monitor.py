"""Tests for governance policy DSL and human approval gates."""

import tempfile

from backend.pipeline.governance.policy import (
    GovernancePolicy,
    PolicyAction,
    PolicyRule,
)


class TestGovernancePolicy:
    def test_default_allow(self):
        policy = GovernancePolicy()
        decision = policy.evaluate("generate", "ideator")
        assert decision.action == PolicyAction.ALLOW

    def test_deny_rule(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="block_harmful",
                    action=PolicyAction.DENY,
                    scope="generate",
                    capability="harmful",
                    message="Harmful content blocked",
                ),
            ]
        )
        decision = policy.evaluate("generate", "harmful")
        assert decision.action == PolicyAction.DENY
        assert decision.rule_name == "block_harmful"

    def test_wildcard_scope(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="global_deny",
                    action=PolicyAction.DENY,
                    scope="*",
                    capability="*",
                    message="Blocked globally",
                ),
            ]
        )
        decision = policy.evaluate("anything", "anything")
        assert decision.action == PolicyAction.DENY

    def test_gate_requires_human(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="human_review",
                    action=PolicyAction.GATE,
                    scope="export",
                    capability="publish",
                ),
            ]
        )
        decision = policy.evaluate("export", "publish")
        assert decision.requires_human
        assert decision.action == PolicyAction.GATE

    def test_approval_flow(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="review", action=PolicyAction.GATE, scope="export", capability="publish"
                ),
            ]
        )
        decision = policy.evaluate("export", "publish")
        policy.request_approval(decision)
        assert policy.pending_count == 1

        approved = policy.approve(decision)
        assert approved.action == PolicyAction.ALLOW
        assert policy.pending_count == 0

    def test_denial_with_amendment(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="review", action=PolicyAction.GATE, scope="export", capability="publish"
                ),
            ]
        )
        decision = policy.evaluate("export", "publish")
        policy.request_approval(decision)

        denied = policy.deny(decision, amendment="Remove PII")
        assert denied.action == PolicyAction.DENY
        assert denied.amendment == "Remove PII"

    def test_suggest_amendment(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="no_pii",
                    action=PolicyAction.DENY,
                    scope="*",
                    capability="export",
                    message="Contains PII",
                ),
            ]
        )
        decision = policy.evaluate("anything", "export")
        suggestion = policy.suggest_amendment(decision)
        assert suggestion is not None
        assert "no_pii" in suggestion

    def test_condition_score(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(
                    name="high_score_gate",
                    action=PolicyAction.GATE,
                    condition="score>0.8",
                    scope="generate",
                    capability="export",
                ),
            ]
        )
        decision_high = policy.evaluate("generate", "export", {"score": 0.9})
        assert decision_high.action == PolicyAction.GATE

        decision_low = policy.evaluate("generate", "export", {"score": 0.5})
        assert decision_low.action == PolicyAction.ALLOW

    def test_add_remove_rule(self):
        policy = GovernancePolicy()
        policy.add_rule(PolicyRule(name="test", action=PolicyAction.DENY))
        assert policy.rule_count == 1
        policy.remove_rule("test")
        assert policy.rule_count == 0

    def test_audit_trail(self):
        policy = GovernancePolicy(
            rules=[
                PolicyRule(name="deny_all", action=PolicyAction.DENY, scope="*", capability="*"),
            ]
        )
        policy.evaluate("gen", "test")
        assert len(policy.audit_log) == 1
        assert policy.audit_log[0]["action"] == "deny"

    def test_persistence(self):
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "rules": [
                        {
                            "name": "persisted",
                            "action": "deny",
                            "scope": "test",
                            "capability": "test",
                        }
                    ]
                },
                f,
            )
            path = f.name

        policy = GovernancePolicy(policy_path=path)
        assert policy.rule_count == 1
        decision = policy.evaluate("test", "test")
        assert decision.action == PolicyAction.DENY

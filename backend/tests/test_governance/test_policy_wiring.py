"""Tests for WP-7 governance policy activation: policy evaluation, DENY, GATE."""

import tempfile
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.pipeline.governance.events import GovernanceAuditLog, GovernanceEvent
from backend.pipeline.governance.policy import GovernancePolicy, PolicyAction, PolicyRule


class TestDefaultPolicyAllowsAll:
    def test_empty_rules_allows_all(self):
        policy = GovernancePolicy()
        decision = policy.evaluate(scope="ingestion", capability="execute")
        assert decision.action == PolicyAction.ALLOW

    def test_mismatched_scope_allows(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="deny_export",
                action=PolicyAction.DENY,
                scope="export",
                capability="publish",
            )
        ])
        decision = policy.evaluate(scope="ingestion", capability="execute")
        assert decision.action == PolicyAction.ALLOW


class TestPolicyDenySkipsStage:
    def test_deny_rule_blocks_matching_scope(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="block_ingestion",
                action=PolicyAction.DENY,
                scope="ingestion",
                capability="*",
                message="Ingestion disabled",
            )
        ])
        decision = policy.evaluate(scope="ingestion", capability="execute")
        assert decision.action == PolicyAction.DENY
        assert decision.reason == "Ingestion disabled"


class TestPolicyDenyRecordedInAudit:
    def test_deny_recorded_in_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = GovernanceAuditLog(f"{tmp}/audit.jsonl")
            policy = GovernancePolicy(rules=[
                PolicyRule(
                    name="block_export",
                    action=PolicyAction.DENY,
                    scope="export",
                    message="Export blocked",
                )
            ])

            decision = policy.evaluate(scope="export", capability="execute")
            if decision.action == PolicyAction.DENY:
                audit.record(GovernanceEvent(
                    event_type="policy.deny",
                    stage="export",
                    content_hash="",
                    checks_summary=f"Rule: {decision.rule_name}",
                ))

            events = audit.get_events()
            deny_events = [e for e in events if e.event_type == "policy.deny"]
            assert len(deny_events) == 1
            assert deny_events[0].stage == "export"


class TestPolicyGateProceedsWithWarning:
    def test_gate_rule_proceeds(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="review_synthesis",
                action=PolicyAction.GATE,
                scope="proposal_synthesis",
                message="Requires human review",
            )
        ])
        decision = policy.evaluate(scope="proposal_synthesis", capability="execute")
        assert decision.action == PolicyAction.GATE
        assert decision.requires_human is True

    def test_policy_loaded_from_file(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            policy_path = f"{tmp}/policy.json"
            rules = {
                "rules": [
                    {
                        "name": "deny_feasibility",
                        "action": "deny",
                        "scope": "feasibility_scoring",
                        "message": "Disabled",
                    }
                ]
            }
            with open(policy_path, "w") as f:
                json.dump(rules, f)

            policy = GovernancePolicy(policy_path=policy_path)
            decision = policy.evaluate(scope="feasibility_scoring", capability="execute")
            assert decision.action == PolicyAction.DENY

"""Tests for condition evaluator — atom, compound, and backward-compat."""

import pytest

from backend.pipeline.governance.condition_eval import (
    AndNode,
    AtomNode,
    NotNode,
    OrNode,
    evaluate,
    parse,
)
from backend.pipeline.governance.policy import GovernancePolicy, PolicyAction, PolicyRule


class TestAtomNode:
    def test_equals(self):
        assert evaluate("score = 0.8", {"score": 0.8})
        assert not evaluate("score = 0.8", {"score": 0.5})

    def test_not_equals(self):
        assert evaluate("status != active", {"status": "paused"})
        assert not evaluate("status != active", {"status": "active"})

    def test_less_than(self):
        assert evaluate("tokens < 500", {"tokens": 400})
        assert not evaluate("tokens < 500", {"tokens": 600})

    def test_greater_than(self):
        assert evaluate("score > 0.5", {"score": 0.8})
        assert not evaluate("score > 0.5", {"score": 0.3})

    def test_less_equal(self):
        assert evaluate("tokens <= 500", {"tokens": 500})
        assert evaluate("tokens <= 500", {"tokens": 400})

    def test_greater_equal(self):
        assert evaluate("score >= 0.5", {"score": 0.5})
        assert evaluate("score >= 0.5", {"score": 0.8})

    def test_contains(self):
        assert evaluate("text contains hello", {"text": "say hello world"})
        assert not evaluate("text contains goodbye", {"text": "say hello world"})

    def test_missing_key_defaults_none(self):
        assert not evaluate("{missing_key} > 0", {})


class TestCompoundNodes:
    def test_and_both_true(self):
        assert evaluate("AND(score > 0.5, tokens < 1000)", {"score": 0.8, "tokens": 500})

    def test_and_one_false(self):
        assert not evaluate("AND(score > 0.5, tokens < 100)", {"score": 0.8, "tokens": 500})

    def test_or_both_true(self):
        assert evaluate("OR(score > 0.5, tokens < 100)", {"score": 0.8, "tokens": 500})

    def test_or_one_true(self):
        assert evaluate("OR(risk = high, domain = safe)", {"risk": "low", "domain": "safe"})

    def test_or_both_false(self):
        assert not evaluate("OR(a = 1, b = 2)", {"a": 0, "b": 0})

    def test_not(self):
        assert evaluate("NOT(score > 0.5)", {"score": 0.3})
        assert not evaluate("NOT(score > 0.5)", {"score": 0.8})

    def test_nested_compound(self):
        assert evaluate(
            "OR(risk = high, NOT(domain = safe))",
            {"risk": "low", "domain": "unsafe"},
        )

    def test_complex_and(self):
        assert evaluate(
            "AND(budget_remaining < 10, run_count > 5)",
            {"budget_remaining": 5, "run_count": 8},
        )


class TestParseErrors:
    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse("this is not valid !!!")


class TestPolicyBackwardCompat:
    def test_existing_score_condition(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(name="quality", action=PolicyAction.DENY, condition="score>0.8"),
        ])
        decision = policy.evaluate("generate", "ideator", {"score": 0.9})
        assert decision.action == PolicyAction.DENY

    def test_existing_context_key(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(name="flag", action=PolicyAction.GATE, condition="requires_review"),
        ])
        decision = policy.evaluate("export", "publish", {"requires_review": True})
        assert decision.action == PolicyAction.GATE

    def test_new_compound_condition(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="session_limit",
                action=PolicyAction.DENY,
                condition="AND(run_count > 5, budget_remaining < 10)",
            ),
        ])
        decision = policy.evaluate("generate", "ideator", {"run_count": 8, "budget_remaining": 5})
        assert decision.action == PolicyAction.DENY

    def test_compound_condition_not_met(self):
        policy = GovernancePolicy(rules=[
            PolicyRule(
                name="session_limit",
                action=PolicyAction.DENY,
                condition="AND(run_count > 5, budget_remaining < 10)",
            ),
        ])
        decision = policy.evaluate("generate", "ideator", {"run_count": 3, "budget_remaining": 50})
        assert decision.action == PolicyAction.ALLOW  # rule skipped, default allow

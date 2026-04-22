"""Policy-governed execution with human approval gates.

YAML-based policy DSL for forbidden operations, quality gates,
capability scoping, and human-in-the-loop approval. Policies can
evolve: on denial, the system suggests minimal amendments.

Adopted from det-acp (policy-gated tool calling with scope/capability
enforcement) and governance audit trails.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    GATE = "gate"  # Require human approval
    AMEND = "amend"  # Suggest amendment


class PolicyRule(BaseModel):
    """A single governance policy rule."""

    name: str
    action: PolicyAction
    condition: str = ""  # Expression to evaluate
    scope: str = "*"  # "*" for global, or specific agent/pipeline stage
    capability: str = "*"  # "*" for all, or specific capability
    message: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    """Result of evaluating a policy."""

    action: PolicyAction
    rule_name: str
    reason: str = ""
    amendment: str | None = None
    requires_human: bool = False


class GovernancePolicy:
    """YAML-configurable governance policy with human approval gates.

    Usage:
        policy = GovernancePolicy(rules=[
            PolicyRule(name="no_harmful", action=PolicyAction.DENY,
                      condition="contains_harmful"),
            PolicyRule(name="human_review", action=PolicyAction.GATE,
                      scope="export", capability="publish"),
        ])
        decision = policy.evaluate("generate", "ideator", context)
        if decision.requires_human:
            approved = policy.request_approval(decision)
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        policy_path: str | None = None,
    ):
        self._rules = rules or []
        self._pending: list[PolicyDecision] = []
        self._audit: list[dict] = []
        if policy_path:
            self._load_from_file(policy_path)

    def _load_from_file(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        for rule_data in data.get("rules", []):
            self._rules.append(PolicyRule(**rule_data))

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def evaluate(
        self,
        scope: str,
        capability: str,
        context: dict | None = None,
    ) -> PolicyDecision:
        context = context or {}
        for rule in self._rules:
            if not self._matches_scope(rule, scope, capability):
                continue
            if rule.condition and not self._eval_condition(rule.condition, context):
                continue
            decision = PolicyDecision(
                action=rule.action,
                rule_name=rule.name,
                reason=rule.message,
                requires_human=rule.action == PolicyAction.GATE,
            )
            self._audit_decision(decision, scope, capability)
            return decision
        return PolicyDecision(action=PolicyAction.ALLOW, rule_name="default_allow")

    def request_approval(self, decision: PolicyDecision) -> PolicyDecision:
        self._pending.append(decision)
        return decision

    def approve(self, decision: PolicyDecision) -> PolicyDecision:
        if decision in self._pending:
            self._pending.remove(decision)
        approved = PolicyDecision(
            action=PolicyAction.ALLOW,
            rule_name=decision.rule_name,
            reason=f"Human approved: {decision.reason}",
        )
        self._audit_decision(approved, "approval", "human")
        return approved

    def deny(self, decision: PolicyDecision, amendment: str | None = None) -> PolicyDecision:
        if decision in self._pending:
            self._pending.remove(decision)
        denied = PolicyDecision(
            action=PolicyAction.DENY,
            rule_name=decision.rule_name,
            reason=f"Human denied: {decision.reason}",
            amendment=amendment,
        )
        self._audit_decision(denied, "denial", "human")
        return denied

    def suggest_amendment(self, decision: PolicyDecision) -> str | None:
        if decision.action != PolicyAction.DENY:
            return None
        return (
            f"To proceed, modify the request to comply with rule '{decision.rule_name}'. "
            f"Reason: {decision.reason}"
        )

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def audit_log(self) -> list[dict]:
        return list(self._audit)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def _matches_scope(self, rule: PolicyRule, scope: str, capability: str) -> bool:
        scope_match = rule.scope == "*" or rule.scope == scope
        cap_match = rule.capability == "*" or rule.capability == capability
        return scope_match and cap_match

    def _eval_condition(self, condition: str, context: dict) -> bool:
        # Backward compat: simple context key truthiness check
        if condition in context:
            return bool(context[condition])
        # Try structured condition evaluator
        try:
            from backend.pipeline.governance.condition_eval import evaluate as eval_expr

            return eval_expr(condition, context)
        except (ValueError, ImportError):
            pass
        return True

    def _audit_decision(self, decision: PolicyDecision, scope: str, capability: str) -> None:
        self._audit.append(
            {
                "action": decision.action.value,
                "rule": decision.rule_name,
                "scope": scope,
                "capability": capability,
                "reason": decision.reason,
            }
        )

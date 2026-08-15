"""Method-fidelity gate: the paper's methodology claims must match the
frozen implementation contract.

Run 2713 released a paper whose numbers were perfectly faithful but
whose methodology section misdescribed the executed protocol on four
counts: multinomial softmax training claimed instead of one-vs-rest
gradient descent, per-class calibrators claimed instead of
positive-class-only calibration, top-class-confidence ECE claimed
instead of positive-class ECE, and a rank-based AURC integral claimed
instead of a ten-fixed-threshold trapezoid estimate. The
experiment_alignment gate only verifies that the executed method NAME
is centered — it cannot see implementation-level misdescription.

This gate enforces the ``method_facts`` contract frozen on the
capability (spec_designer.py): every fact's required patterns must
appear in the paper, and no forbidden pattern may appear anywhere.
The canonical statements are injected verbatim into paper synthesis
and remediation prompts, so a compliant paper reproduces them and
passes; any paper that asserts a contradicting description is blocked
with the exact pattern and surrounding text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MethodFidelityResult:
    """Outcome of the method-fidelity check."""

    passed: bool
    reason: str
    violations: list[str]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "violations": self.violations,
        }


def _find_match(paper: str, pattern: str) -> str | None:
    """Return a short context snippet around the first match, or None."""
    m = re.search(pattern, paper, re.IGNORECASE | re.DOTALL)
    if m is None:
        return None
    start, end = m.span()
    snippet = paper[max(0, start - 40):end + 40].replace("\n", " ")
    return snippet.strip()


def evaluate_method_fidelity(
    paper_md: str,
    method_facts: dict,
) -> MethodFidelityResult:
    """Check a paper against the frozen method-facts contract.

    Args:
        paper_md: The full paper markdown.
        method_facts: fact_id -> {statement, required_patterns,
            forbidden_patterns} as frozen on the capability.

    Returns:
        MethodFidelityResult. An empty or missing contract is a pass
        (the gate is vacuous for runs without a frozen contract).
    """
    if not method_facts:
        return MethodFidelityResult(
            passed=True,
            reason="No frozen method contract for this run",
            violations=[],
        )

    violations: list[str] = []

    for fact_id, fact in method_facts.items():
        if not isinstance(fact, dict):
            continue

        for pattern in fact.get("forbidden_patterns", []):
            snippet = _find_match(paper_md, pattern)
            if snippet is not None:
                violations.append(
                    f"{fact_id}: paper asserts a description that"
                    f" contradicts the executed protocol"
                    f" (matched '{pattern}' near: \"{snippet}\")."
                    f" The frozen statement is:"
                    f" {fact.get('statement', '')[:160]}"
                )

        for pattern in fact.get("required_patterns", []):
            snippet = _find_match(paper_md, pattern)
            if snippet is None:
                violations.append(
                    f"{fact_id}: paper does not state the executed"
                    f" protocol (required pattern '{pattern}' not"
                    f" found). The methodology section must include"
                    f" the frozen statement:"
                    f" {fact.get('statement', '')[:160]}"
                )

    if violations:
        return MethodFidelityResult(
            passed=False,
            reason="; ".join(violations[:4]),
            violations=violations,
        )

    n = len(method_facts)
    return MethodFidelityResult(
        passed=True,
        reason=(
            f"All {n} frozen method fact(s) verified: required"
            f" statements present, no contradicting descriptions"
        ),
        violations=[],
    )

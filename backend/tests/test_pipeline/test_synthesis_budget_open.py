"""The opened paper-synthesis budget: infinity satisfies the invariant,
neutralizes every wait_for and insufficient-time break, and leaves the
structural validation (refusal of partial papers) untouched."""
import math

from backend.pipeline.synthesis.synthesis_budget import SynthesisBudget


def test_open_budget_is_infinite():
    b = SynthesisBudget.open()
    assert math.isinf(b.total_workflow_timeout)
    assert math.isinf(b.monolithic_attempt_timeout)
    assert math.isinf(b.section_call_timeout)
    assert b.fallback_reserved_seconds == 0.0


def test_open_budget_satisfies_invariant():
    b = SynthesisBudget.open()
    assert b.monolithic_attempt_timeout <= b.total_workflow_timeout - b.fallback_reserved_seconds


def test_open_budget_section_time_never_expires():
    b = SynthesisBudget.open()
    assert b.section_remaining(elapsed=10_000_000.0) == math.inf
    assert b.fallback_remaining(elapsed=10_000_000.0) == math.inf


def test_default_budget_still_bounded():
    b = SynthesisBudget()
    assert b.total_workflow_timeout == 1200.0
    assert b.monolithic_attempt_timeout == 400.0
    assert b.section_call_timeout == 120.0

"""Shared fixtures for metacognitive tests."""

import pytest

from backend.pipeline.metacognitive.ledger import LedgerEntry, ProgressLedger


@pytest.fixture
def ledger() -> ProgressLedger:
    return ProgressLedger()


def make_entry(
    stage: str = "test_stage",
    metric_name: str = "overall_score",
    value: float = 0.5,
    passed: bool = True,
    round_num: int | None = None,
) -> LedgerEntry:
    return LedgerEntry(
        stage=stage,
        metric_name=metric_name,
        value=value,
        passed=passed,
        round_num=round_num,
    )

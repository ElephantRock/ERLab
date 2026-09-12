"""Commissioning remediation: the faithfulness scorer must actually run.

``_post_proposal_synthesis`` called the async ``score_proposal`` via
``asyncio.get_event_loop().run_until_complete`` inside a running loop —
the call raised immediately, left the coroutine never-awaited, and the
bare ``except Exception: logger.debug`` swallowed it, so the advertised
faithfulness evaluation silently never executed.
"""

from unittest.mock import MagicMock

import pytest

from backend.pipeline.orchestrator.stage_lifecycle import StageLifecycle
from backend.pipeline.result import PipelineResult


class _RecordingScorer:
    calls = 0

    def __init__(self, provider=None):
        pass

    async def score_proposal(self, **kwargs):
        type(self).calls += 1
        return {"score": 1.0}


@pytest.fixture
def recorded_scorer(monkeypatch):
    _RecordingScorer.calls = 0
    import backend.pipeline.evaluation.faithfulness_scorer as mod

    monkeypatch.setattr(mod, "FaithfulnessScorer", _RecordingScorer)
    return _RecordingScorer


def _lifecycle() -> StageLifecycle:
    lc = StageLifecycle.__new__(StageLifecycle)
    lc._persistence = MagicMock()
    lc._processor = MagicMock()
    from types import SimpleNamespace

    lc._settings = SimpleNamespace(provenance_check_enabled=False)
    return lc


@pytest.mark.anyio
async def test_score_proposal_is_awaited_per_proposal(recorded_scorer):
    from types import SimpleNamespace

    result = PipelineResult()
    proposal = SimpleNamespace(title="T", methodology="M", id=None)
    result.proposals = {0: proposal}

    ctx = MagicMock()
    ctx.all_papers = []

    lc = _lifecycle()
    await lc._post_proposal_synthesis(result, ctx, None)

    assert _RecordingScorer.calls == 1, (
        "score_proposal must be awaited once per proposal — a skipped run "
        "means the advertised evaluation did not execute"
    )
    assert proposal._faithfulness_report == {"score": 1.0}


@pytest.mark.anyio
async def test_scorer_failure_is_visible_not_debug_silent(recorded_scorer, monkeypatch):
    from types import SimpleNamespace

    async def _boom(self, **kwargs):
        raise RuntimeError("scorer exploded")

    monkeypatch.setattr(_RecordingScorer, "score_proposal", _boom)

    warnings: list[str] = []
    lc = _lifecycle()

    import logging

    handler = logging.Handler()
    handler.emit = lambda record: warnings.append(record.getMessage())
    logging.getLogger("backend.pipeline.orchestrator.stage_lifecycle").addHandler(handler)
    try:
        result = PipelineResult()
        result.proposals = {0: SimpleNamespace(title="T", methodology="M", id=None)}
        ctx = MagicMock()
        ctx.all_papers = []
        await lc._post_proposal_synthesis(result, ctx, None)
    finally:
        logging.getLogger("backend.pipeline.orchestrator.stage_lifecycle").removeHandler(handler)

    assert any("Faithfulness scoring skipped" in w for w in warnings), (
        "scorer failure must be logged at warning level, not debug"
    )

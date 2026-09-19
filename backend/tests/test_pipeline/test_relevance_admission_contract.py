"""Citation-integrity regression proof: relevance-admission contract.

Covers the four proofs required for the admission corrective:
1. A provider that strictly accepts ``list[str]`` (the filter must call the
   batch contract — the scalar-string call path is the defect this locks out).
2. Deterministic ranking over known vectors (threshold and floor select by
   score, never by insertion order).
3. Malformed provider output (wrong cardinality / dimension / non-finite
   components) is rejected — it never becomes a legitimate 0.0 score and its
   paper is never admitted.
4. Provider-level failure is fail-closed: the stage's admission decision
   raises instead of proceeding with an unfiltered corpus.

Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.relevance_filter import (
    LiteratureAdmissionError,
    RelevanceFilter,
    RelevanceFilterError,
)

_DOMAIN = "morphology domain query"


class StrictBatchProvider:
    """Embedding provider that refuses any call outside the batch contract.

    Vector lookup: the first table key appearing as a substring of the text.
    """

    def __init__(self, table: dict[str, list[float]]):
        self._table = table
        self.scalar_calls = 0

    def _hit(self, text: str) -> str | None:
        return next((k for k in self._table if k in text), None)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            self.scalar_calls += 1
            raise AssertionError("provider called outside the list[str] contract")
        out = []
        for t in texts:
            hit = self._hit(t)
            if hit is None:
                raise AssertionError(f"no vector configured for text: {t[:60]}")
            out.append(list(self._table[hit]))
        return out


class MalformedProvider(StrictBatchProvider):
    """Batch-contract provider that returns malformed output for one key."""

    def __init__(self, table: dict[str, list[float]], bad_key: str, mode: str):
        super().__init__(table)
        self._bad_key = bad_key
        self._mode = mode

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            self.scalar_calls += 1
            raise AssertionError("provider called outside the list[str] contract")
        if self._bad_key is not None and any(self._hit(t) == self._bad_key for t in texts):
            if self._mode == "cardinality":
                # Two vectors for one text — the pre-remediation scalar bug shape.
                return [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
            if self._mode == "dimension":
                return [[0.1, 0.2]]
            if self._mode == "nonfinite":
                return [[float("nan"), float("inf")]]
        return await super().embed(texts)


def _result(pid: str, title: str, vec_key: str) -> SearchResult:
    return SearchResult(
        paper=Paper(id=pid, title=title, abstract=f"abstract:{vec_key}", source="test"),
        relevance_score=None,
        source="test",
    )


def _table(entries: list[tuple[str, list[float]]]) -> dict[str, list[float]]:
    return {_DOMAIN: [1.0, 0.0, 0.0, 0.0], **dict(entries)}


# ── 1. Batch contract ────────────────────────────────────────────


def test_filter_calls_batch_contract_not_scalar():
    """The filter passes [text] lists; a strict provider never sees a scalar."""
    table = _table(
        [
            ("t:morph paper", [0.9, 0.1, 0.0, 0.0]),
            ("t:other paper", [0.1, 0.9, 0.0, 0.0]),
        ]
    )
    provider = StrictBatchProvider(table)
    f = RelevanceFilter(embedding_provider=provider, threshold=0.3)
    papers = [
        _result("p1", "Morph paper", "t:morph paper"),
        _result("p2", "Other paper", "t:other paper"),
    ]
    outcome = asyncio.run(f.filter_with_scores(papers, _DOMAIN))
    assert provider.scalar_calls == 0
    assert outcome.failures == {}
    assert set(outcome.scores) == {"p1", "p2"}


# ── 2. Deterministic ranking ─────────────────────────────────────


def test_threshold_admits_by_score_threshold_only():
    """Survivors are exactly the papers at or above the threshold."""
    table = _table(
        [
            ("k:strong", [1.0, 0.0, 0.0, 0.0]),   # cos 1.0
            ("k:mid", [0.8, 0.6, 0.0, 0.0]),      # cos 0.8
            ("k:weak", [0.0, 1.0, 0.0, 0.0]),     # cos 0.0
            ("k:anti", [-1.0, 0.0, 0.0, 0.0]),    # cos -1.0
        ]
    )
    f = RelevanceFilter(embedding_provider=StrictBatchProvider(table), threshold=0.3)
    papers = [
        _result("a_weak", "Weak", "k:weak"),
        _result("b_strong", "Strong", "k:strong"),
        _result("c_anti", "Anti", "k:anti"),
        _result("d_mid", "Mid", "k:mid"),
    ]
    outcome = asyncio.run(f.filter_with_scores(papers, _DOMAIN))
    assert [p.paper.id for p in outcome.survivors] == ["b_strong", "d_mid"]
    assert outcome.scores["b_strong"] == pytest.approx(1.0)
    assert outcome.scores["d_mid"] == pytest.approx(0.8)
    assert outcome.scores["a_weak"] == pytest.approx(0.0)
    assert outcome.scores["c_anti"] == pytest.approx(-1.0)


def test_floor_selects_top_scored_never_insertion_order():
    """When nothing passes the threshold, the floor takes the best scores.

    Input order is the reverse of score order: the pre-remediation defect
    would have admitted the first five papers in list order.
    """
    table = _table(
        [
            ("k:1", [0.29, 0.9571, 0.0, 0.0]),
            ("k:2", [0.28, 0.9596, 0.0, 0.0]),
            ("k:3", [0.27, 0.9629, 0.0, 0.0]),
            ("k:4", [0.26, 0.9656, 0.0, 0.0]),
            ("k:5", [0.25, 0.9682, 0.0, 0.0]),
            ("k:6", [0.24, 0.9708, 0.0, 0.0]),
        ]
    )
    f = RelevanceFilter(embedding_provider=StrictBatchProvider(table), threshold=0.3)
    papers = [
        _result("p6", "Six", "k:6"),
        _result("p5", "Five", "k:5"),
        _result("p4", "Four", "k:4"),
        _result("p3", "Three", "k:3"),
        _result("p2", "Two", "k:2"),
        _result("p1", "One", "k:1"),
    ]
    outcome = asyncio.run(f.filter_with_scores(papers, _DOMAIN))
    assert len(outcome.survivors) == 5
    assert [p.paper.id for p in outcome.survivors] == ["p1", "p2", "p3", "p4", "p5"]
    assert "p6" not in [p.paper.id for p in outcome.survivors]


# ── 3. Malformed output rejection ────────────────────────────────


@pytest.mark.parametrize("mode", ["cardinality", "dimension", "nonfinite"])
def test_malformed_vector_rejected_not_scored_zero(mode):
    """Malformed provider output excludes the paper; valid papers score on."""
    table = _table(
        [
            ("t:good", [0.9, 0.1, 0.0, 0.0]),
            ("t:bad", [0.5, 0.5, 0.0, 0.0]),
        ]
    )
    provider = MalformedProvider(table, "t:bad", mode)
    f = RelevanceFilter(embedding_provider=provider, threshold=0.3)
    papers = [
        _result("bad_paper", "Bad", "t:bad"),
        _result("good_paper", "Good", "t:good"),
    ]
    outcome = asyncio.run(f.filter_with_scores(papers, _DOMAIN))
    assert "bad_paper" in outcome.failures
    assert "bad_paper" not in outcome.scores
    assert outcome.scores.get("bad_paper") is None
    assert "good_paper" in outcome.scores
    assert [p.paper.id for p in outcome.survivors] == ["good_paper"]


def test_all_papers_unscorable_admits_nothing():
    """If nothing can be validly scored, the admitted set is empty."""
    provider = MalformedProvider(_table([]), "t:any", "cardinality")
    f = RelevanceFilter(embedding_provider=provider, threshold=0.3)
    papers = [_result("p1", "One", "t:any"), _result("p2", "Two", "t:any")]
    outcome = asyncio.run(f.filter_with_scores(papers, _DOMAIN))
    assert outcome.survivors == []
    assert outcome.scores == {}
    assert set(outcome.failures) == {"p1", "p2"}


def test_query_embedding_failure_raises():
    """A failing domain-query embedding raises — no corpus pass-through."""
    provider = StrictBatchProvider(_table([]))

    async def broken(texts):
        raise RuntimeError("provider down")

    provider.embed = broken
    f = RelevanceFilter(embedding_provider=provider)
    with pytest.raises(RelevanceFilterError):
        asyncio.run(f.filter_with_scores([_result("p1", "One", "k:x")], _DOMAIN))


# ── 4. Stage-level fail-closed ───────────────────────────────────


def _mk_stage():
    from backend.pipeline.stages import LiteratureSearchStage

    return LiteratureSearchStage(search=None, hooks=None)


def test_stage_admission_provider_failure_fails_closed(monkeypatch):
    """Stage admission raises LiteratureAdmissionError on provider failure."""
    from backend.pipeline.knowledge import embedding_providers as ep

    class Dead:
        async def embed(self, texts):
            raise RuntimeError("provider down")

    monkeypatch.setattr(ep, "create_embedding_provider", lambda **kwargs: Dead())
    stage = _mk_stage()
    papers = [_result("p1", "One", "k:x")]
    with pytest.raises(LiteratureAdmissionError):
        asyncio.run(stage._admit_corpus(papers, _DOMAIN))


def test_stage_admission_all_unscorable_fails_closed(monkeypatch):
    """A corpus where every candidate fails scoring fails the stage.

    Zero survivors from all-failed scoring is an admission-scoring
    failure, not a valid empty admission — the stage must raise.
    """
    from backend.pipeline.knowledge import embedding_providers as ep

    provider = MalformedProvider(_table([]), "t:any", "cardinality")
    monkeypatch.setattr(ep, "create_embedding_provider", lambda **kwargs: provider)
    stage = _mk_stage()
    papers = [_result("p1", "One", "t:any").paper, _result("p2", "Two", "t:any").paper]
    with pytest.raises(LiteratureAdmissionError):
        asyncio.run(stage._admit_corpus(papers, _DOMAIN))


def test_stage_admission_all_below_threshold_is_valid_empty(monkeypatch):
    """Valid scoring that admits nobody is a legitimate empty decision.

    Every candidate scores validly but below the threshold with no floor
    available; the stage completes with an explicitly empty admission —
    it must NOT raise, distinguishing scored-out from unscorable.
    """
    from backend.pipeline.knowledge import embedding_providers as ep

    table = _table(
        [("t:low", [0.0, 1.0, 0.0, 0.0])]  # cos 0.0 against the domain
    )
    monkeypatch.setattr(
        ep, "create_embedding_provider", lambda **kwargs: StrictBatchProvider(table)
    )
    stage = _mk_stage()
    papers = [_result("p1", "One", "t:low").paper, _result("p2", "Two", "t:low").paper]
    unique, admitted, scores, exclusions = asyncio.run(
        stage._admit_corpus(papers, _DOMAIN)
    )
    assert unique == []
    assert admitted == set()
    assert set(scores) == {"p1", "p2"}
    assert scores["p1"] == pytest.approx(0.0)
    assert exclusions == {}


def test_stage_admission_returns_decision(monkeypatch):
    """The happy path returns admitted papers plus full score/exclusion maps."""
    from backend.pipeline.knowledge import embedding_providers as ep

    table = _table(
        [
            ("t:on", [0.9, 0.1, 0.0, 0.0]),
            ("t:off", [0.0, 1.0, 0.0, 0.0]),
        ]
    )
    monkeypatch.setattr(
        ep, "create_embedding_provider", lambda **kwargs: StrictBatchProvider(table)
    )
    stage = _mk_stage()
    papers = [
        _result("src:on", "On-domain", "t:on").paper,
        _result("src:off", "Off-domain", "t:off").paper,
    ]
    unique, admitted, scores, exclusions = asyncio.run(
        stage._admit_corpus(papers, _DOMAIN)
    )
    assert [p.id for p in unique] == ["src:on"]
    assert admitted == {"src:on"}
    # cos([0.9,0.1,0,0],[1,0,0,0]) and cos([0,1,0,0],[1,0,0,0])
    assert scores["src:on"] == pytest.approx(0.9938837346736189)
    assert scores["src:off"] == pytest.approx(0.0)
    assert exclusions == {}

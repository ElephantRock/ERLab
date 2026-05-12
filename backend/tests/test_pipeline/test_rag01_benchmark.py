"""Tests for BATCH-RAG-01: Benchmark Generator + Retrieval Benchmark Runner.

Tests cover:
  1. Benchmark data models (BenchmarkQuestion, BenchmarkDataset)
  2. BenchmarkGenerator with template fallback (no LLM)
  3. Metric computation: Hit Rate, MRR, nDCG@K
  4. RetrievalBenchmarkRunner with mock search
  5. API endpoint registration
"""

import asyncio
import math

import pytest

from backend.pipeline.evaluation.benchmark_models import (
    BenchmarkDataset,
    BenchmarkQuestion,
    BenchmarkRunReport,
    RetrievalResult,
)
from backend.pipeline.evaluation.benchmark_generator import BenchmarkGenerator
from backend.pipeline.evaluation.retrieval_benchmark import (
    RetrievalBenchmarkRunner,
    compute_hit_rate,
    compute_mrr,
    compute_ndcg,
    compute_precision_at_k,
)
from backend.pipeline.literature.models import Author, Paper


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_papers() -> list[Paper]:
    """Create sample papers for testing."""
    return [
        Paper(
            id="paper-1",
            source="test",
            title="Attention Is All You Need",
            abstract="We propose a new simple network architecture, the Transformer, "
            "based solely on attention mechanisms, dispensing with recurrence and "
            "convolutions entirely. The Transformer achieves state-of-the-art results "
            "on machine translation tasks.",
            authors=[Author(name="Ashish Vaswani")],
            year=2017,
        ),
        Paper(
            id="paper-2",
            source="test",
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            abstract="We introduce BERT, which stands for Bidirectional Encoder "
            "Representations from Transformers. BERT is designed to pre-train deep "
            "bidirectional representations from unlabeled text by jointly conditioning "
            "on both left and right context.",
            authors=[Author(name="Jacob Devlin")],
            year=2018,
        ),
        Paper(
            id="paper-3",
            source="test",
            title="GPT-3: Language Models are Few-Shot Learners",
            abstract="We demonstrate that scaling up language models greatly improves "
            "task-agnostic, few-shot performance. GPT-3 has 175 billion parameters "
            "and achieves strong performance on many NLP tasks without fine-tuning.",
            authors=[Author(name="Tom Brown")],
            year=2020,
        ),
    ]


@pytest.fixture
def sample_questions() -> list[BenchmarkQuestion]:
    """Create sample benchmark questions."""
    return [
        BenchmarkQuestion(
            question="What is the Transformer architecture?",
            source_paper_id="paper-1",
            source_paper_title="Attention Is All You Need",
            expected_answer="A network based solely on attention mechanisms",
            difficulty="easy",
        ),
        BenchmarkQuestion(
            question="How does BERT achieve bidirectional representations?",
            source_paper_id="paper-2",
            source_paper_title="BERT",
            expected_answer="By jointly conditioning on left and right context",
            difficulty="medium",
        ),
        BenchmarkQuestion(
            question="How many parameters does GPT-3 have?",
            source_paper_id="paper-3",
            source_paper_title="GPT-3",
            expected_answer="175 billion",
            difficulty="easy",
        ),
    ]


# ── Model Tests ────────────────────────────────────────────────────────

def test_benchmark_question_creation():
    """BenchmarkQuestion stores all required fields."""
    q = BenchmarkQuestion(
        question="What is X?",
        source_paper_id="p1",
        source_paper_title="Paper One",
        expected_answer="X is Y",
        difficulty="medium",
    )
    assert q.question == "What is X?"
    assert q.source_paper_id == "p1"
    assert q.difficulty == "medium"


def test_benchmark_dataset_total_questions(sample_questions):
    """BenchmarkDataset.total_questions returns correct count."""
    ds = BenchmarkDataset(id="test", questions=sample_questions)
    assert ds.total_questions == 3


def test_benchmark_dataset_serialization(sample_questions):
    """BenchmarkDataset round-trips through to_dict/from_dict."""
    ds = BenchmarkDataset(id="test", name="Test Dataset", questions=sample_questions)
    data = ds.to_dict()
    restored = BenchmarkDataset.from_dict(data)
    assert restored.id == "test"
    assert restored.total_questions == 3
    assert restored.questions[0].question == "What is the Transformer architecture?"


def test_retrieval_result_found():
    """RetrievalResult correctly records found/not found."""
    r = RetrievalResult(
        question="q",
        source_paper_id="p1",
        retrieved_paper_ids=["p2", "p1", "p3"],
        rank_of_correct=2,
        found=True,
    )
    assert r.found is True
    assert r.rank_of_correct == 2


def test_benchmark_run_report_coverage():
    """BenchmarkRunReport.coverage returns correct fraction."""
    report = BenchmarkRunReport(total_questions=10, questions_found=7)
    assert report.coverage == 0.7


# ── Generator Tests ────────────────────────────────────────────────────

def test_generator_template_fallback(sample_papers):
    """BenchmarkGenerator produces template questions when no LLM provided."""
    gen = BenchmarkGenerator(provider=None, questions_per_paper=2)
    ds = asyncio.run(gen.generate(papers=sample_papers, domain="AI/NLP"))
    assert ds.total_questions > 0
    assert ds.domain == "AI/NLP"
    # Template generates 2 questions per paper
    assert ds.total_questions == 6  # 3 papers x 2 questions


def test_generator_skips_short_abstracts():
    """BenchmarkGenerator skips papers with abstracts shorter than 50 chars."""
    papers = [
        Paper(id="p1", source="test", title="Short", abstract="Too short"),
        Paper(id="p2", source="test", title="Long enough",
              abstract="This is a sufficiently long abstract that exceeds the 50 character minimum threshold for benchmark generation."),
    ]
    gen = BenchmarkGenerator(provider=None)
    ds = asyncio.run(gen.generate(papers=papers))
    # Only paper-2 should generate questions
    assert all(q.source_paper_id == "p2" for q in ds.questions)


def test_generator_respects_questions_per_paper(sample_papers):
    """BenchmarkGenerator limits questions per paper to configured value."""
    gen = BenchmarkGenerator(provider=None, questions_per_paper=1)
    ds = asyncio.run(gen.generate(papers=sample_papers))
    # Template fallback generates 1 question per paper with questions_per_paper=1
    assert ds.total_questions == 3


def test_generator_handles_empty_papers():
    """BenchmarkGenerator handles empty paper list gracefully."""
    gen = BenchmarkGenerator(provider=None)
    ds = asyncio.run(gen.generate(papers=[]))
    assert ds.total_questions == 0


# ── Metric Computation Tests ───────────────────────────────────────────

def test_hit_rate_all_found():
    """Hit rate is 1.0 when all queries find correct doc."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=1),
        RetrievalResult(question="q2", source_paper_id="p2", found=True, rank_of_correct=3),
    ]
    assert compute_hit_rate(results) == 1.0


def test_hit_rate_none_found():
    """Hit rate is 0.0 when no queries find correct doc."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=False),
        RetrievalResult(question="q2", source_paper_id="p2", found=False),
    ]
    assert compute_hit_rate(results) == 0.0


def test_hit_rate_partial():
    """Hit rate is 0.5 when half of queries find correct doc."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=1),
        RetrievalResult(question="q2", source_paper_id="p2", found=False),
    ]
    assert compute_hit_rate(results) == 0.5


def test_hit_rate_empty():
    """Hit rate is 0.0 for empty results."""
    assert compute_hit_rate([]) == 0.0


def test_mrr_perfect():
    """MRR is 1.0 when correct doc always at rank 1."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=1),
        RetrievalResult(question="q2", source_paper_id="p2", found=True, rank_of_correct=1),
    ]
    assert compute_mrr(results) == 1.0


def test_mrr_mixed():
    """MRR computes correctly for mixed ranks."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=1),
        RetrievalResult(question="q2", source_paper_id="p2", found=True, rank_of_correct=2),
        RetrievalResult(question="q3", source_paper_id="p3", found=True, rank_of_correct=4),
    ]
    expected = (1.0 / 1 + 1.0 / 2 + 1.0 / 4) / 3
    assert abs(compute_mrr(results) - expected) < 0.001


def test_mrr_not_found():
    """MRR treats not-found as 0 contribution."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=2),
        RetrievalResult(question="q2", source_paper_id="p2", found=False),
    ]
    expected = (0.5 + 0.0) / 2
    assert abs(compute_mrr(results) - expected) < 0.001


def test_ndcg_perfect():
    """nDCG is 1.0 when correct doc always at rank 1."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=1),
    ]
    # DCG = 1/log2(2) = 1.0, IDCG = 1.0
    assert abs(compute_ndcg(results, k=10) - 1.0) < 0.001


def test_ndcg_rank_2():
    """nDCG computes correctly for rank 2."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=2),
    ]
    # DCG = 1/log2(3) = 0.6309, IDCG = 1.0
    expected = 1.0 / math.log2(3)
    assert abs(compute_ndcg(results, k=10) - expected) < 0.001


def test_ndcg_not_found():
    """nDCG is 0.0 when correct doc not found."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=False),
    ]
    assert compute_ndcg(results, k=10) == 0.0


def test_precision_at_k():
    """Precision@K counts correctly."""
    results = [
        RetrievalResult(question="q1", source_paper_id="p1", found=True, rank_of_correct=3),
        RetrievalResult(question="q2", source_paper_id="p2", found=True, rank_of_correct=8),
        RetrievalResult(question="q3", source_paper_id="p3", found=False),
    ]
    # P@10: q1 found (rank 3 <= 10), q2 found (rank 8 <= 10), q3 not found
    assert compute_precision_at_k(results, k=10) == pytest.approx(2.0 / 3.0)
    # P@5: q1 found (rank 3 <= 5), q2 NOT (rank 8 > 5), q3 not found
    assert compute_precision_at_k(results, k=5) == pytest.approx(1.0 / 3.0)


# ── BenchmarkRunner Tests ──────────────────────────────────────────────

class MockSearchService:
    """Mock search service that returns predetermined results."""

    def __init__(self, results_map: dict[str, list[str]] | None = None):
        self._results_map = results_map or {}

    async def search_all(self, query: str, **kwargs) -> list[Paper]:
        """Return papers based on query mapping."""
        paper_ids = self._results_map.get(query, [])
        return [
            Paper(id=pid, source="mock", title=f"Paper {pid}")
            for pid in paper_ids
        ]


def test_benchmark_runner_all_found(sample_questions):
    """BenchmarkRunner finds all correct papers."""
    # Map each question to results containing its source paper
    results_map = {
        q.question: [q.source_paper_id, "other-1", "other-2"]
        for q in sample_questions
    }
    mock_search = MockSearchService(results_map)
    runner = RetrievalBenchmarkRunner(search_service=mock_search, top_k=10)
    dataset = BenchmarkDataset(id="test", questions=sample_questions)

    report = asyncio.run(runner.run(dataset))
    assert report.hit_rate == 1.0
    assert report.mrr == 1.0  # All at rank 1
    assert report.total_questions == 3


def test_benchmark_runner_partial_found(sample_questions):
    """BenchmarkRunner handles partial retrieval correctly."""
    # Only first question finds its paper
    results_map = {
        sample_questions[0].question: [sample_questions[0].source_paper_id, "other"],
        sample_questions[1].question: ["other-1", "other-2"],  # paper-2 not found
        sample_questions[2].question: ["other-3", "other-4"],  # paper-3 not found
    }
    mock_search = MockSearchService(results_map)
    runner = RetrievalBenchmarkRunner(search_service=mock_search)
    dataset = BenchmarkDataset(id="test", questions=sample_questions)

    report = asyncio.run(runner.run(dataset))
    assert report.hit_rate == pytest.approx(1.0 / 3.0)
    assert report.questions_found == 1


def test_benchmark_runner_handles_search_errors(sample_questions):
    """BenchmarkRunner gracefully handles search failures."""
    class FailingSearch:
        async def search_all(self, query: str, **kwargs):
            raise RuntimeError("Search unavailable")

    runner = RetrievalBenchmarkRunner(search_service=FailingSearch())
    dataset = BenchmarkDataset(id="test", questions=sample_questions)

    report = asyncio.run(runner.run(dataset))
    assert report.hit_rate == 0.0
    assert report.total_questions == 3

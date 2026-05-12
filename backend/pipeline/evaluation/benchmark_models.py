"""Data models for benchmark evaluation — synthetic ground-truth datasets.

BATCH-RAG-01/TASK-01: Defines the benchmark data format used to evaluate
retrieval quality. A benchmark dataset consists of questions generated from
paper abstracts, paired with the source paper IDs as ground truth.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BenchmarkQuestion(BaseModel):
    """A single benchmark question with ground-truth answer."""

    question: str
    source_paper_id: str
    source_paper_title: str
    expected_answer: str = ""
    domain: str = ""
    difficulty: str = "medium"  # easy / medium / hard
    generated_at: datetime = Field(default_factory=datetime.now)


class BenchmarkDataset(BaseModel):
    """A collection of benchmark questions for evaluating retrieval quality."""

    id: str = ""
    name: str = ""
    domain: str = ""
    questions: list[BenchmarkQuestion] = Field(default_factory=list)
    source_run_id: str | None = None
    papers_count: int = 0
    questions_per_paper: int = 3
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> BenchmarkDataset:
        return cls.model_validate(data)


class RetrievalResult(BaseModel):
    """Result of running a single benchmark question through search."""

    question: str
    source_paper_id: str
    retrieved_paper_ids: list[str] = Field(default_factory=list)
    retrieved_titles: list[str] = Field(default_factory=list)
    rank_of_correct: int | None = None  # 1-indexed, None if not found
    found: bool = False
    relevance_scores: list[float] = Field(default_factory=list)


class BenchmarkRunReport(BaseModel):
    """Report from running a full benchmark evaluation."""

    dataset_id: str = ""
    dataset_name: str = ""
    strategy: str = ""
    total_questions: int = 0
    questions_found: int = 0
    hit_rate: float = 0.0
    mrr: float = 0.0  # Mean Reciprocal Rank
    ndcg_at_k: float = 0.0  # nDCG@K
    k: int = 10
    results: list[RetrievalResult] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def coverage(self) -> float:
        """Fraction of questions where the correct paper was found."""
        if self.total_questions == 0:
            return 0.0
        return self.questions_found / self.total_questions

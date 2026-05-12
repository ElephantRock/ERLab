"""Domain gold benchmark datasets — pre-built evaluation benchmarks.

BATCH-RAG-07: Generates benchmark questions from gold-standard gap lists.
Provides ready-to-use evaluation datasets for 4 domains.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.pipeline.evaluation.benchmark_models import (
    BenchmarkDataset,
    BenchmarkQuestion,
)
from backend.pipeline.verification.gold_standards import GOLD_STANDARD_GAPS

logger = logging.getLogger(__name__)

BENCHMARKS_DIR = Path(__file__).parent / "benchmarks"


def _generate_from_gold_gaps(domain: str) -> BenchmarkDataset:
    """Generate benchmark questions from gold-standard gaps."""
    gold_gaps = GOLD_STANDARD_GAPS.get(domain, GOLD_STANDARD_GAPS.get("AI/NLP", []))
    questions = []

    for gap in gold_gaps:
        # Generate 2 questions per known gap
        questions.append(
            BenchmarkQuestion(
                question=f"What are the current challenges in {gap}?",
                source_paper_id="gold_standard",
                source_paper_title=f"Gold Standard: {gap}",
                expected_answer=gap,
                domain=domain,
                difficulty="medium",
            )
        )
        questions.append(
            BenchmarkQuestion(
                question=f"What recent approaches address {gap}?",
                source_paper_id="gold_standard",
                source_paper_title=f"Gold Standard: {gap}",
                expected_answer=gap,
                domain=domain,
                difficulty="hard",
            )
        )

    return BenchmarkDataset(
        id=f"gold_{domain.replace('/', '_').lower()}",
        name=f"Gold Standard Benchmark: {domain}",
        domain=domain,
        questions=questions,
        papers_count=0,
        questions_per_paper=2,
    )


def get_gold_benchmark(domain: str) -> BenchmarkDataset:
    """Get the gold benchmark for a domain.

    Tries to load from JSON file first, falls back to generating from gold standards.
    """
    # Try loading from file
    domain_slug = domain.replace("/", "_").lower()
    json_path = BENCHMARKS_DIR / f"{domain_slug}.json"

    if json_path.exists():
        with open(json_path) as f:
            data = json.load(f)
        return BenchmarkDataset.from_dict(data)

    # Generate from gold standards
    return _generate_from_gold_gaps(domain)


def list_gold_benchmarks() -> list[dict]:
    """List available gold benchmark datasets."""
    domains = list(GOLD_STANDARD_GAPS.keys())
    benchmarks = []
    for domain in domains:
        ds = get_gold_benchmark(domain)
        benchmarks.append({
            "domain": domain,
            "id": ds.id,
            "name": ds.name,
            "questions": ds.total_questions,
        })
    return benchmarks


def generate_all_json_files() -> int:
    """Generate JSON benchmark files for all domains.

    Returns the number of files generated.
    """
    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for domain in GOLD_STANDARD_GAPS:
        ds = _generate_from_gold_gaps(domain)
        domain_slug = domain.replace("/", "_").lower()
        json_path = BENCHMARKS_DIR / f"{domain_slug}.json"

        with open(json_path, "w") as f:
            json.dump(ds.to_dict(), f, indent=2)
        count += 1

    logger.info("Generated %d gold benchmark JSON files", count)
    return count

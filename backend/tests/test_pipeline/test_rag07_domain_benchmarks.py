"""Tests for BATCH-RAG-07: Domain Gold Benchmark Datasets."""

import json
import pytest
from pathlib import Path

from backend.pipeline.evaluation.domain_benchmarks import (
    get_gold_benchmark,
    list_gold_benchmarks,
    generate_all_json_files,
    BENCHMARKS_DIR,
)


def test_get_gold_benchmark_ai_nlp():
    """get_gold_benchmark returns benchmark for AI/NLP domain."""
    ds = get_gold_benchmark("AI/NLP")
    assert ds.total_questions > 0
    assert "NLP" in ds.name or "AI" in ds.name
    assert all(q.domain == "AI/NLP" for q in ds.questions)


def test_get_gold_benchmark_biomedical():
    """get_gold_benchmark returns benchmark for Biomedical domain."""
    ds = get_gold_benchmark("Biomedical")
    assert ds.total_questions > 0
    assert ds.domain == "Biomedical"


def test_get_gold_benchmark_all_domains():
    """get_gold_benchmark works for all known domains."""
    for domain in ["AI/NLP", "AI/Reasoning", "Biomedical", "Computer Science"]:
        ds = get_gold_benchmark(domain)
        assert ds.total_questions > 0


def test_gold_benchmark_has_two_questions_per_gap():
    """Gold benchmark generates 2 questions per known gap."""
    ds = get_gold_benchmark("AI/NLP")
    # AI/NLP has 8 gold gaps → 16 questions
    assert ds.total_questions == 16


def test_list_gold_benchmarks():
    """list_gold_benchmarks returns all domains."""
    benchmarks = list_gold_benchmarks()
    assert len(benchmarks) >= 4
    domains = [b["domain"] for b in benchmarks]
    assert "AI/NLP" in domains
    assert "Biomedical" in domains


def test_generate_all_json_files(tmp_path):
    """generate_all_json_files creates valid JSON files."""
    # Generate to temp dir to avoid polluting source
    import backend.pipeline.evaluation.domain_benchmarks as mod
    original_dir = mod.BENCHMARKS_DIR
    try:
        mod.BENCHMARKS_DIR = tmp_path
        count = generate_all_json_files()
        assert count >= 4

        # Verify files are valid JSON
        for json_file in tmp_path.glob("*.json"):
            data = json.loads(json_file.read_text())
            assert "questions" in data
            assert len(data["questions"]) > 0
    finally:
        mod.BENCHMARKS_DIR = original_dir

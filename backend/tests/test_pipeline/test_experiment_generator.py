"""Tests for ExperimentGenerator — BATCH-66/TASK-01.

TEST-66-01-01: generate(idea) returns non-empty Python code string
TEST-66-01-02: Code includes hypothesis test and baseline comparison
TEST-66-01-03: Code uses standard libraries only (no pip install)
"""

from __future__ import annotations

import ast

import pytest

from backend.pipeline.experiment.experiment_generator import ExperimentGenerator
from backend.pipeline.generation.models import IdeaCandidate


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def sample_idea() -> IdeaCandidate:
    """A mock IdeaCandidate for testing."""
    return IdeaCandidate(
        title="Retrieval-Augmented Generation with Cross-Attention Fusion",
        problem_statement=(
            "Current RAG systems suffer from hallucination when retrieved "
            "passages are irrelevant or conflicting, reducing factual accuracy."
        ),
        proposed_method=(
            "A two-stage pipeline combining dense passage retrieval with "
            "cross-attention fusion layers that dynamically weight passage "
            "relevance during decoding."
        ),
        expected_contributions=(
            "Reduced hallucination rate and improved factual grounding "
            "on standard benchmarks."
        ),
        evaluation_approach=(
            "Evaluate on SQuAD and Natural Questions with ablation studies "
            "comparing against vanilla RAG and no-retrieval baselines."
        ),
    )


@pytest.fixture
def generator() -> ExperimentGenerator:
    """ExperimentGenerator without LLM provider (template mode)."""
    return ExperimentGenerator(provider=None)


# ── TEST-66-01-01: Non-empty Python code ────────────────────────────

@pytest.mark.anyio
async def test_generate_returns_nonempty_python_code(
    generator: ExperimentGenerator,
    sample_idea: IdeaCandidate,
) -> None:
    """AC-01-01: generate(idea) returns a non-empty Python code string."""
    code = await generator.generate(sample_idea)

    # Must be a non-empty string
    assert isinstance(code, str)
    assert len(code) > 0, "Generated code must not be empty"

    # Must be valid Python syntax
    tree = ast.parse(code)
    assert tree is not None, "Generated code must parse as valid Python"

    # Must be a script with real substance (functions, imports, etc.)
    function_defs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert len(function_defs) >= 2, (
        f"Expected at least 2 function definitions, got {len(function_defs)}"
    )


# ── TEST-66-01-02: Hypothesis test + baseline comparison ───────────

@pytest.mark.anyio
async def test_code_includes_hypothesis_and_baseline(
    generator: ExperimentGenerator,
    sample_idea: IdeaCandidate,
) -> None:
    """AC-01-02: Generated code includes hypothesis and baseline comparison."""
    code = await generator.generate(sample_idea)

    # Hypothesis / problem statement embedded in the code
    assert "HYPOTHESIS" in code or "hypothesis" in code, (
        "Generated code must include a hypothesis statement"
    )
    # The idea's problem statement should appear in the comments/output
    assert "hallucination" in code, (
        "Generated code should reference the problem statement keywords"
    )

    # Baseline comparison
    assert "baseline" in code.lower(), (
        "Generated code must include baseline comparison logic"
    )
    assert "random" in code.lower(), (
        "Generated code must include a random baseline"
    )
    assert "heuristic" in code.lower(), (
        "Generated code must include a heuristic/proposed-method baseline"
    )

    # Must compute metrics (accuracy / precision / recall / f1)
    assert "accuracy" in code, "Generated code must compute accuracy"
    assert "f1" in code.lower(), "Generated code must compute F1 score"

    # Must output results as JSON
    assert "json.dumps" in code or "json.dumps" in code, (
        "Generated code must output results as JSON"
    )


# ── TEST-66-01-03: Standard libraries only ──────────────────────────

@pytest.mark.anyio
async def test_code_uses_standard_libraries_only(
    generator: ExperimentGenerator,
    sample_idea: IdeaCandidate,
) -> None:
    """AC-01-03: Code uses standard libraries only — no pip install required."""
    code = await generator.generate(sample_idea)

    # Parse and extract all import statements
    tree = ast.parse(code)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    # Allowed standard-library modules
    allowed = {"json", "random", "statistics", "time", "__future__", "typing"}
    non_standard = imported_modules - allowed
    assert not non_standard, (
        f"Generated code imports non-standard modules: {non_standard}. "
        f"All imports: {imported_modules}"
    )

    # Verify the expected modules ARE present
    assert "json" in imported_modules, "Should import json"
    assert "random" in imported_modules, "Should import random"
    assert "statistics" in imported_modules, "Should import statistics"
    assert "time" in imported_modules, "Should import time"


# ── Extra: idea content is embedded correctly ───────────────────────

@pytest.mark.anyio
async def test_generated_code_embeds_idea_content(
    generator: ExperimentGenerator,
    sample_idea: IdeaCandidate,
) -> None:
    """Verify that key fields from the idea appear in the generated code."""
    code = await generator.generate(sample_idea)

    # Title should appear
    assert "Retrieval-Augmented" in code, "Title should be embedded in code"
    # Proposed method keywords
    assert "dense passage retrieval" in code.lower() or "two-stage" in code.lower(), (
        "Proposed method should be referenced"
    )

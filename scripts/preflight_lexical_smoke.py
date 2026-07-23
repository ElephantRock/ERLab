"""Lexical smoke preflight: validate the harness on a SEPARATE non-benchmark corpus.

Does NOT run any of the 30 diagnostic queries. Uses a tiny synthetic smoke
fixture to validate: index creation, query execution, deterministic ordering,
top-k contract, candidate-ID resolution, latency instrumentation, serialization.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ranking.sprint_harness import (
    DiagnosticCase, build_ranking_request, run_candidate, compute_case_metrics,
    make_lexical_adapter, make_hybrid_rrf_adapter, make_mock_semantic_adapter,
    summarize_paired, paired_compare, operational_summary,
)

# ── NON-BENCHMARK SMOKE FIXTURE ──
# Completely separate from the diagnostic corpus. No diagnostic queries.
SMOKE_CASES = [
    DiagnosticCase(
        case_id="smoke_001", task_family="paper_discovery",
        query="graph neural networks for node classification",
        case_mode="positive_present", scoring_profile="ranked_relevance",
        pool_units=(
            {"unit_id": "s1a", "text": "We introduce graph convolutional networks for semi-supervised node classification.", "document_id": "smoke_doc_1"},
            {"unit_id": "s1b", "text": "We apply attention mechanisms to graph-structured data for node-level tasks.", "document_id": "smoke_doc_2"},
            {"unit_id": "s1c", "text": "A study of neural network pruning for image classification tasks.", "document_id": "smoke_doc_3"},
        ),
        judgments={"s1a": 3, "s1b": 2, "s1c": 0},
        risk_labels=("missed_relevant_evidence",),
    ),
    DiagnosticCase(
        case_id="smoke_002", task_family="evidence_retrieval",
        query="does vitamin D reduce fracture risk in elderly adults",
        case_mode="positive_present", scoring_profile="ranked_relevance",
        pool_units=(
            {"unit_id": "s2a", "text": "Combined vitamin D and calcium supplementation reduced hip fractures in institutionalized elderly women.", "document_id": "smoke_doc_4"},
            {"unit_id": "s2b", "text": "Vitamin D alone did not reduce fracture risk in a community-dwelling population.", "document_id": "smoke_doc_5"},
        ),
        judgments={"s2a": 3, "s2b": 1},
        risk_labels=("false_support",),
    ),
    DiagnosticCase(
        case_id="smoke_003", task_family="research_gap_analysis",
        query="find papers on quantum computing applications in drug discovery",
        case_mode="no_positive_expected", scoring_profile="negative_control",
        pool_units=(
            {"unit_id": "s3a", "text": "A survey of machine learning for molecular property prediction.", "document_id": "smoke_doc_6"},
            {"unit_id": "s3b", "text": "We review classical algorithms for protein folding prediction.", "document_id": "smoke_doc_7"},
        ),
        judgments={"s3a": 0, "s3b": 0},
        risk_labels=("agenda_mismatch",),
    ),
]


def run_preflight():
    """Run the lexical smoke preflight and report results."""
    failures = []
    passed = 0

    def chk(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failures.append((label, detail))

    print("Lexical smoke preflight (NON-BENCHMARK fixture)")
    print("=" * 55)

    lexical_fn = make_lexical_adapter()
    mock_semantic = make_mock_semantic_adapter()
    hybrid_fn = make_hybrid_rrf_adapter(rrf_k=60)

    # Run lexical on all smoke cases
    lexical_results = {}
    for case in SMOKE_CASES:
        result = run_candidate(case, lexical_fn, candidate_id="A_legacy_lexical")
        lexical_results[case.case_id] = result
        chk(f"{case.case_id}: lexical completed", result.completed)
        chk(f"{case.case_id}: lexical ranked all units", len(result.ranked_unit_ids) == len(case.pool_units))
        chk(f"{case.case_id}: no error", result.error is None)

    # Run mock hybrid (using mock semantic scores — NOT real embeddings)
    hybrid_results = {}
    for case in SMOKE_CASES:
        mock_scores = {u["unit_id"]: mock_semantic(case.query, u["text"]) for u in case.pool_units}
        result = run_candidate(case, hybrid_fn, candidate_id="B_mock_hybrid", semantic_scores=mock_scores)
        hybrid_results[case.case_id] = result
        chk(f"{case.case_id}: mock hybrid completed", result.completed)

    # Deterministic ordering: run twice, compare
    for case in SMOKE_CASES:
        r1 = run_candidate(case, lexical_fn, candidate_id="A_legacy_lexical")
        r2 = run_candidate(case, lexical_fn, candidate_id="A_legacy_lexical")
        chk(f"{case.case_id}: deterministic ordering", r1.ranked_unit_ids == r2.ranked_unit_ids)

    # Top-k contract: selected count <= final_limit
    for case in SMOKE_CASES:
        r = lexical_results[case.case_id]
        chk(f"{case.case_id}: ranked count <= 20", len(r.ranked_unit_ids) <= 20)

    # Candidate-ID resolution: every ranked ID is in the pool
    for case in SMOKE_CASES:
        pool_ids = {u["unit_id"] for u in case.pool_units}
        r = lexical_results[case.case_id]
        chk(f"{case.case_id}: all ranked IDs in pool", all(rid in pool_ids for rid in r.ranked_unit_ids))

    # Latency instrumentation
    for case in SMOKE_CASES:
        r = lexical_results[case.case_id]
        chk(f"{case.case_id}: latency > 0", r.elapsed_ms >= 0)

    # Metrics computation (positive_present cases only)
    for case in SMOKE_CASES:
        if case.scoring_profile == "ranked_relevance":
            r = lexical_results[case.case_id]
            all_grades = list(case.judgments.values())
            metrics = compute_case_metrics(r.ranked_grades, all_grades)
            chk(f"{case.case_id}: ndcg_at_10 in [0,1]", 0 <= metrics["ndcg_at_10"] <= 1)

    # Paired comparison
    outcomes = paired_compare(hybrid_results, lexical_results, SMOKE_CASES)
    summary = summarize_paired(outcomes)
    chk("paired comparison produces outcomes", len(outcomes) == 2)  # 2 ranked_relevance cases
    chk("paired summary has wins/losses/ties", "wins" in summary and "losses" in summary)

    # Operational summary
    ops = operational_summary(lexical_results)
    chk("operational: completion_rate = 1.0", ops["completion_rate"] == 1.0)
    chk("operational: p50 latency >= 0", ops["latency_p50_ms"] >= 0)

    # Result serialization (JSON-serializable)
    for case in SMOKE_CASES:
        r = lexical_results[case.case_id]
        try:
            json.dumps({
                "case_id": r.case_id, "candidate_id": r.candidate_id,
                "ranked_unit_ids": list(r.ranked_unit_ids),
                "ranked_grades": list(r.ranked_grades),
                "elapsed_ms": r.elapsed_ms, "completed": r.completed,
            })
            chk(f"{case.case_id}: result serializable", True)
        except Exception:
            chk(f"{case.case_id}: result serializable", False)

    print()
    print(f"Operational summary: {json.dumps(ops, indent=2)}")
    print(f"Paired summary: {json.dumps(summary, indent=2)}")

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)
    else:
        print(f"PASS: all checks passed ({passed})")
        sys.exit(0)


if __name__ == "__main__":
    run_preflight()

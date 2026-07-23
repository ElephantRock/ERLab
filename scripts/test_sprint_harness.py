"""Sprint harness contract tests.

Validates the harness plumbing (adapters, metrics, paired comparison,
negative-control scoring, operational metrics, serialization) using mock
adapters and the non-benchmark smoke fixture. Does NOT access any diagnostic
benchmark data.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ranking.sprint_harness import (
    DiagnosticCase, build_ranking_request, run_candidate, compute_case_metrics,
    compute_negative_control_metrics, paired_compare, summarize_paired,
    operational_summary, make_lexical_adapter, make_hybrid_rrf_adapter,
    make_mock_semantic_adapter,
)

failures = []
passed = 0

def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
    else:
        failures.append((label, detail))

# Smoke fixture (same as preflight_lexical_smoke)
SMOKE = [
    DiagnosticCase(
        case_id="ct_001", task_family="paper_discovery",
        query="graph neural networks", case_mode="positive_present",
        scoring_profile="ranked_relevance",
        pool_units=(
            {"unit_id": "u1", "text": "Graph convolutional networks for node classification.", "document_id": "d1"},
            {"unit_id": "u2", "text": "Attention mechanisms for graph data.", "document_id": "d2"},
            {"unit_id": "u3", "text": "Image classification with CNNs.", "document_id": "d3"},
        ),
        judgments={"u1": 3, "u2": 2, "u3": 0},
        risk_labels=("missed_relevant_evidence",),
    ),
    DiagnosticCase(
        case_id="ct_002", task_family="evidence_retrieval",
        query="vitamin D fracture risk", case_mode="positive_present",
        scoring_profile="ranked_relevance",
        pool_units=(
            {"unit_id": "u4", "text": "Vitamin D plus calcium reduces fractures in elderly.", "document_id": "d4"},
            {"unit_id": "u5", "text": "Vitamin D alone has no effect on fractures.", "document_id": "d5"},
        ),
        judgments={"u4": 3, "u5": 1},
        risk_labels=("false_support",),
    ),
    DiagnosticCase(
        case_id="ct_003", task_family="research_gap_analysis",
        query="quantum computing drug discovery", case_mode="no_positive_expected",
        scoring_profile="negative_control",
        pool_units=(
            {"unit_id": "u6", "text": "ML for molecular property prediction.", "document_id": "d6"},
            {"unit_id": "u7", "text": "Classical protein folding algorithms.", "document_id": "d7"},
        ),
        judgments={"u6": 0, "u7": 0},
        risk_labels=("agenda_mismatch",),
    ),
]


def test_lexical_adapter():
    print("\n[1] Lexical adapter")
    fn = make_lexical_adapter()
    for case in SMOKE:
        result = run_candidate(case, fn, candidate_id="A_lexical")
        chk(f"{case.case_id}: completed", result.completed)
        chk(f"{case.case_id}: all units ranked", len(result.ranked_unit_ids) == len(case.pool_units))
        chk(f"{case.case_id}: no error", result.error is None)
        chk(f"{case.case_id}: latency recorded", result.elapsed_ms >= 0)


def test_mock_hybrid_adapter():
    print("\n[2] Mock hybrid adapter (mock semantic scores)")
    fn = make_hybrid_rrf_adapter(rrf_k=60)
    mock_sem = make_mock_semantic_adapter()
    for case in SMOKE:
        scores = {u["unit_id"]: mock_sem(case.query, u["text"]) for u in case.pool_units}
        result = run_candidate(case, fn, candidate_id="B_mock", semantic_scores=scores)
        chk(f"{case.case_id}: mock hybrid completed", result.completed)
        chk(f"{case.case_id}: all units ranked", len(result.ranked_unit_ids) == len(case.pool_units))


def test_deterministic_ordering():
    print("\n[3] Deterministic ordering")
    fn = make_lexical_adapter()
    for case in SMOKE:
        r1 = run_candidate(case, fn, candidate_id="A_lexical")
        r2 = run_candidate(case, fn, candidate_id="A_lexical")
        chk(f"{case.case_id}: identical ordering on rerun", r1.ranked_unit_ids == r2.ranked_unit_ids)


def test_top_k_contract():
    print("\n[4] Top-k contract")
    fn = make_lexical_adapter()
    for case in SMOKE:
        r = run_candidate(case, fn, candidate_id="A_lexical")
        chk(f"{case.case_id}: ranked <= 20", len(r.ranked_unit_ids) <= 20)


def test_candidate_id_resolution():
    print("\n[5] Candidate-ID resolution")
    fn = make_lexical_adapter()
    for case in SMOKE:
        pool_ids = {u["unit_id"] for u in case.pool_units}
        r = run_candidate(case, fn, candidate_id="A_lexical")
        chk(f"{case.case_id}: all ranked IDs in pool", all(rid in pool_ids for rid in r.ranked_unit_ids))


def test_metrics_computation():
    print("\n[6] Metrics computation")
    fn = make_lexical_adapter()
    for case in SMOKE:
        if case.scoring_profile != "ranked_relevance":
            continue
        r = run_candidate(case, fn, candidate_id="A_lexical")
        all_grades = list(case.judgments.values())
        m = compute_case_metrics(r.ranked_grades, all_grades)
        chk(f"{case.case_id}: ndcg_at_10 in [0,1]", 0 <= m["ndcg_at_10"] <= 1)
        chk(f"{case.case_id}: recall_at_20 in [0,1]", 0 <= m["recall_at_20"] <= 1)


def test_negative_control_scoring():
    print("\n[7] Negative-control scoring")
    fn = make_lexical_adapter()
    for case in SMOKE:
        if case.scoring_profile != "negative_control":
            continue
        r = run_candidate(case, fn, candidate_id="A_lexical")
        nc = compute_negative_control_metrics(r.ranked_grades)
        chk(f"{case.case_id}: false_match_in_top_k is 0 or 1", nc["false_match_in_top_k"] in (0.0, 1.0))
        chk(f"{case.case_id}: correct_no_match is 0 or 1", nc["correct_no_match"] in (0.0, 1.0))


def test_paired_comparison():
    print("\n[8] Paired comparison")
    lex_fn = make_lexical_adapter()
    hyb_fn = make_hybrid_rrf_adapter()
    mock_sem = make_mock_semantic_adapter()
    lex_results, hyb_results = {}, {}
    for case in SMOKE:
        lex_results[case.case_id] = run_candidate(case, lex_fn, candidate_id="A_lexical")
        scores = {u["unit_id"]: mock_sem(case.query, u["text"]) for u in case.pool_units}
        hyb_results[case.case_id] = run_candidate(case, hyb_fn, candidate_id="B_mock", semantic_scores=scores)
    outcomes = paired_compare(hyb_results, lex_results, SMOKE)
    summary = summarize_paired(outcomes)
    chk("outcomes for 2 ranked cases", len(outcomes) == 2)
    chk("summary has wins+losses+ties", summary["wins"] + summary["losses"] + summary["ties"] == 2)
    chk("summary has net_wins", "net_wins" in summary)


def test_operational_metrics():
    print("\n[9] Operational metrics")
    fn = make_lexical_adapter()
    results = {}
    for case in SMOKE:
        results[case.case_id] = run_candidate(case, fn, candidate_id="A_lexical")
    ops = operational_summary(results)
    chk("completion_rate = 1.0", ops["completion_rate"] == 1.0)
    chk("completed = 3", ops["completed"] == 3)
    chk("p50 >= 0", ops["latency_p50_ms"] >= 0)
    chk("p95 >= 0", ops["latency_p95_ms"] >= 0)
    chk("fallbacks = 0", ops["fallbacks"] == 0)
    chk("errors empty", len(ops["errors"]) == 0)


def test_serialization():
    print("\n[10] Result serialization")
    fn = make_lexical_adapter()
    for case in SMOKE:
        r = run_candidate(case, fn, candidate_id="A_lexical")
        try:
            s = json.dumps({
                "case_id": r.case_id, "candidate_id": r.candidate_id,
                "ranked_unit_ids": list(r.ranked_unit_ids),
                "ranked_grades": list(r.ranked_grades),
                "elapsed_ms": r.elapsed_ms, "completed": r.completed,
                "fallback_used": r.fallback_used, "error": r.error,
            }, sort_keys=True)
            chk(f"{case.case_id}: serializable", len(s) > 0)
        except Exception as e:
            chk(f"{case.case_id}: serializable", False, str(e))


def test_no_benchmark_access():
    print("\n[11] No benchmark access (smoke fixture is separate)")
    # Verify smoke fixture case IDs don't collide with diagnostic IDs
    diag_ids = {"diag_er_001", "diag_er_002", "diag_cr_001", "diag_pd_001"}
    smoke_ids = {c.case_id for c in SMOKE}
    chk("no ID collision with diagnostic", diag_ids.isdisjoint(smoke_ids))


if __name__ == "__main__":
    test_lexical_adapter()
    test_mock_hybrid_adapter()
    test_deterministic_ordering()
    test_top_k_contract()
    test_candidate_id_resolution()
    test_metrics_computation()
    test_negative_control_scoring()
    test_paired_comparison()
    test_operational_metrics()
    test_serialization()
    test_no_benchmark_access()

    print("\n" + "=" * 50)
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)
    else:
        print(f"PASS: all contract tests passed ({passed})")
        sys.exit(0)

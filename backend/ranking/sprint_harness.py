"""Sprint retrieval decision harness.

Evaluates candidate retrieval policies against the diagnostic benchmark.
Reuses the existing ranking contracts (RankingRequest → RankingResult) and
metric implementations from backend/ranking/.

This harness adds:
  - diagnostic-corpus indexing (title+abstract passages from the P1D.2 corpus)
  - candidate adapters (lexical, qwen-hybrid, bge-m3-hybrid) with mock fallbacks
  - per-case paired comparison against lexical baseline
  - negative-control case scoring (false-match / abstention; NOT recall/nDCG)
  - operational metrics (latency, completion, fallbacks)
  - deterministic result capture and serialization

DESIGN: policies are pure functions (RankingRequest) -> RankingResult, matching
the existing backend/ranking/policies.py interface. The harness wraps them with
timing, error capture, and metrics computation.

NOT a production module. Does not modify any production retrieval code.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Reuse existing ranking infrastructure
from backend.ranking.contracts import (
    RankingRequest, RankingResult, RankedCandidate, RankingCandidate,
    DISPOSITION_SELECTED, DISPOSITION_EXCLUDED_RANK,
    compute_tie_break_key, validate_ranking_result,
)
from backend.ranking.policies import _keyword_overlap, rank_legacy_lexical, rank_hybrid_rrf
from backend.ranking.evaluation import _ndcg_at_k, _mrr_at_k, _precision_at_k, _recall_at_k

REPO = Path(__file__).resolve().parent.parent
DIAGNOSTIC_DIR = REPO / "docs" / "retrieval"


@dataclass(frozen=True)
class DiagnosticCase:
    """A diagnostic case loaded from the P1D.2 JSONL, ready for evaluation."""
    case_id: str
    task_family: str
    query: str
    case_mode: str  # positive_present | no_positive_expected
    scoring_profile: str  # ranked_relevance | negative_control
    pool_units: tuple[dict, ...]  # each: {unit_id, text, document_id}
    judgments: dict  # unit_id -> grade (from reviewed judgments; EMPTY if not yet reviewed)
    risk_labels: tuple[str, ...]


@dataclass(frozen=True)
class CandidateResult:
    """Per-case result for one candidate."""
    case_id: str
    candidate_id: str
    ranked_unit_ids: tuple[str, ...]
    ranked_grades: tuple[int, ...]
    elapsed_ms: float
    completed: bool
    fallback_used: str | None
    error: str | None


@dataclass(frozen=True)
class PairedOutcome:
    """Paired comparison of a candidate vs lexical on one case."""
    case_id: str
    candidate_id: str
    metric: str
    candidate_value: float
    lexical_value: float
    delta: float
    outcome: str  # win | loss | tie


def load_diagnostic_corpus() -> list[dict]:
    """Load the 43 source documents from the P1D.2 diagnostic corpus."""
    path = DIAGNOSTIC_DIR / "p1d2_diagnostic_seed_sources.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_diagnostic_cases(judgments_path: Path | None = None) -> list[DiagnosticCase]:
    """Load diagnostic cases. If judgments_path is None, judgments are EMPTY
    (cases are loaded but NOT scoreable — preserves the review gate).

    When judgments are available (after independent review), pass the path to
    the reviewed judgments JSONL to populate the grade mapping.
    """
    cases_path = DIAGNOSTIC_DIR / "p1d2_diagnostic_seed_cases.jsonl"
    raw_cases = [json.loads(l) for l in cases_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    sources = {s["document_id"]: s for s in load_diagnostic_corpus()}

    # Load reviewed judgments if provided
    reviewed_grades: dict[str, dict[str, int]] = {}  # case_id -> {unit_id -> grade}
    if judgments_path and judgments_path.exists():
        for line in judgments_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            j = json.loads(line)
            if j.get("eligible_for_scoring"):
                reviewed_grades.setdefault(j["case_id"], {})[j["unit_id"]] = j["research_utility_grade"]

    cases = []
    for rc in raw_cases:
        # Build pool units with text (extract from source corpus)
        pool_units = []
        for uid in rc["candidate_pool"]["candidate_unit_ids"]:
            pp = rc["passages"].get(uid, {})
            src = sources.get(pp.get("document_id", ""), {})
            try:
                _, rng = pp["passage_locator"].split(" ")
                s, e = map(int, rng.split("-"))
                text = src["full_text"][s:e]
            except Exception:
                text = ""
            pool_units.append({"unit_id": uid, "text": text, "document_id": pp.get("document_id", "")})

        # Grades: empty if not reviewed, populated if reviewed+scoreable
        grades = reviewed_grades.get(rc["case_id"], {})

        cases.append(DiagnosticCase(
            case_id=rc["case_id"],
            task_family=rc["task_family"],
            query=rc["query_or_claim"],
            case_mode=rc["case_mode"],
            scoring_profile=rc["scoring_profile"],
            pool_units=tuple(pool_units),
            judgments=grades,
            risk_labels=tuple(rc["risk_labels"]),
        ))
    return cases


def build_ranking_request(case: DiagnosticCase, *, policy_id: str,
                          semantic_scores: dict[str, float] | None = None,
                          final_limit: int = 20) -> RankingRequest:
    """Build a RankingRequest from a diagnostic case. Matches the P1B interface."""
    candidates = []
    for u in case.pool_units:
        lex = _keyword_overlap(case.query, u["text"])
        sem = semantic_scores.get(u["unit_id"]) if semantic_scores else None
        candidates.append(RankingCandidate(
            candidate_id=u["unit_id"],
            target_kind="passage" if "passage" in case.pool_units[0]["unit_id"] else "paper",
            canonical_text_hash=hashlib.sha256(u["text"].encode()).hexdigest(),
            lexical_input_score=lex,
            semantic_input_score=sem,
            metadata={"text": u["text"]},
        ))
    return RankingRequest(
        ranking_surface="retrieval_ranking",
        ranking_intent="general_research_relevance",
        query_text=case.query,
        candidates=tuple(candidates),
        ranking_policy_id=policy_id,
        final_limit=final_limit,
    )


def run_candidate(case: DiagnosticCase, rank_fn: Callable[[RankingRequest], RankingResult],
                  *, candidate_id: str, semantic_scores: dict[str, float] | None = None) -> CandidateResult:
    """Run one candidate on one case with timing and error capture."""
    start = time.perf_counter()
    try:
        req = build_ranking_request(case, policy_id=candidate_id, semantic_scores=semantic_scores)
        result = rank_fn(req)
        elapsed_ms = (time.perf_counter() - start) * 1000

        ranked_ids = tuple(rc.candidate_id for rc in result.ranked)
        ranked_grades = tuple(case.judgments.get(uid, 0) for uid in ranked_ids)

        return CandidateResult(
            case_id=case.case_id, candidate_id=candidate_id,
            ranked_unit_ids=ranked_ids, ranked_grades=ranked_grades,
            elapsed_ms=round(elapsed_ms, 3), completed=True,
            fallback_used=result.fallback_used, error=None,
        )
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CandidateResult(
            case_id=case.case_id, candidate_id=candidate_id,
            ranked_unit_ids=(), ranked_grades=(),
            elapsed_ms=round(elapsed_ms, 3), completed=False,
            fallback_used=None, error=str(e)[:200],
        )


def compute_case_metrics(grades: tuple[int, ...], all_grades: list[int]) -> dict[str, float]:
    """Compute standard ranking metrics for a positive_present case."""
    return {
        "ndcg_at_5": round(_ndcg_at_k(grades, 5), 4),
        "ndcg_at_10": round(_ndcg_at_k(grades, 10), 4),
        "mrr_at_10": round(_mrr_at_k(grades, 10), 4),
        "precision_at_5": round(_precision_at_k(grades, 5), 4),
        "recall_at_20": round(_recall_at_k(grades, 20, all_grades), 4),
    }


def compute_negative_control_metrics(grades: tuple[int, ...], top_k: int = 5) -> dict[str, float]:
    """Score negative-control cases: false-match rate, abstention.
    These do NOT compute recall/nDCG (no positive exists)."""
    false_match_in_top_k = any(g >= 2 for g in grades[:top_k])  # grade>=2 = looks relevant
    high_confidence_mismatch = any(g >= 1 for g in grades[:1])  # top-1 is grade>=1
    return {
        "false_match_in_top_k": 1.0 if false_match_in_top_k else 0.0,
        "high_confidence_mismatch": 1.0 if high_confidence_mismatch else 0.0,
        "correct_no_match": 0.0 if any(g >= 2 for g in grades) else 1.0,
    }


def paired_compare(candidate_results: dict[str, CandidateResult],
                   lexical_results: dict[str, CandidateResult],
                   cases: list[DiagnosticCase],
                   metric_name: str = "ndcg_at_10") -> list[PairedOutcome]:
    """Paired case-level comparison of candidate vs lexical."""
    outcomes = []
    for case in cases:
        if case.scoring_profile != "ranked_relevance":
            continue  # negative controls scored separately
        cand_r = candidate_results.get(case.case_id)
        lex_r = lexical_results.get(case.case_id)
        if not cand_r or not lex_r or not cand_r.completed or not lex_r.completed:
            continue

        all_grades = list(case.judgments.values())
        cand_m = compute_case_metrics(cand_r.ranked_grades, all_grades)
        lex_m = compute_case_metrics(lex_r.ranked_grades, all_grades)

        delta = cand_m[metric_name] - lex_m[metric_name]
        if delta > 0.001:
            outcome = "win"
        elif delta < -0.001:
            outcome = "loss"
        else:
            outcome = "tie"

        outcomes.append(PairedOutcome(
            case_id=case.case_id, candidate_id=cand_r.candidate_id,
            metric=metric_name, candidate_value=cand_m[metric_name],
            lexical_value=lex_m[metric_name], delta=round(delta, 4),
            outcome=outcome,
        ))
    return outcomes


def summarize_paired(outcomes: list[PairedOutcome]) -> dict:
    """Summarize paired outcomes into wins/losses/ties."""
    from collections import Counter
    counts = Counter(o.outcome for o in outcomes)
    return {
        "total_cases": len(outcomes),
        "wins": counts.get("win", 0),
        "losses": counts.get("loss", 0),
        "ties": counts.get("tie", 0),
        "net_wins": counts.get("win", 0) - counts.get("loss", 0),
    }


def operational_summary(results: dict[str, CandidateResult]) -> dict:
    """Summarize operational metrics across all cases for one candidate."""
    completed = sum(1 for r in results.values() if r.completed)
    total = len(results)
    latencies = [r.elapsed_ms for r in results.values() if r.completed]
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)] if latencies_sorted else 0
    fallbacks = sum(1 for r in results.values() if r.fallback_used)
    errors = [r.error for r in results.values() if r.error]
    return {
        "completion_rate": round(completed / total, 4) if total else 0,
        "completed": completed,
        "total": total,
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "fallbacks": fallbacks,
        "errors": errors[:5],
    }


# ── Candidate adapter factory ──

def make_lexical_adapter() -> Callable[[RankingRequest], RankingResult]:
    """Candidate A: pure lexical (no embeddings needed)."""
    return rank_legacy_lexical


def make_hybrid_rrf_adapter(rrf_k: int = 60) -> Callable[[RankingRequest], RankingResult]:
    """Candidates B and C: RRF hybrid (lexical + semantic). The semantic scores
    must be pre-computed and passed via semantic_scores in build_ranking_request."""
    def adapter(req: RankingRequest) -> RankingResult:
        return rank_hybrid_rrf(req, rrf_k=rrf_k)
    return adapter


def make_mock_semantic_adapter(dimension: int = 1024, seed: int = 42) -> Callable[[str, str], float]:
    """Mock semantic scorer for contract tests. Returns a deterministic pseudo-cosine
    based on text-hash XOR. NOT a real embedding — just a stable mock for testing
    that the harness plumbing works end-to-end."""
    def mock_score(query_text: str, candidate_text: str) -> float:
        qh = int(hashlib.sha256(query_text.encode()).hexdigest()[:8], 16)
        ch = int(hashlib.sha256(candidate_text.encode()).hexdigest()[:8], 16)
        xor = qh ^ ch
        return (xor % 10000) / 10000.0  # 0.0 - 0.9999
    return mock_score

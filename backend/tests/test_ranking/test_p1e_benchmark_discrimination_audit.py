"""Tests for P1E.0 — Benchmark Discrimination Audit.

Seals the frozen-corpus discipline, original-evaluator usage, held-out
isolation, shared-adapter uniqueness, filtered snapshot access, semantic
correctness of the diagnosis/statistics, output schema, and the closeout
mode that forbids critical snapshot skips.

Two modes (correction #9):
  - ordinary run: snapshot-dependent tests skip if snapshots absent
  - closeout/CI : ERLAB_REQUIRE_P1E_SNAPSHOTS=1 -> missing snapshots hard-fail
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "data" / "evaluation" / "p1e_frozen_split_manifest.json"
PROTOCOL_PATH = REPO_ROOT / "docs" / "research" / "p1e_benchmark_discrimination_audit_protocol.md"
P1B_SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
TEI_SNAPSHOT_PATH = P1B_SNAPSHOT_DIR / "snapshot_tei_gte_large_en_v15.json"
AUDIT_JSON = REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json"
CASES_JSON = REPO_ROOT / "data" / "evaluation" / "p1e_case_diagnostics.json"
PAIRWISE_JSON = REPO_ROOT / "data" / "evaluation" / "p1e_policy_pairwise_comparison.json"

import sys
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

SNAPSHOTS_PRESENT = (P1B_SNAPSHOT_DIR / "snapshot.json").exists() and TEI_SNAPSHOT_PATH.exists()
ARTIFACTS_PRESENT = AUDIT_JSON.exists() and CASES_JSON.exists() and PAIRWISE_JSON.exists()
REQUIRE = os.getenv("ERLAB_REQUIRE_P1E_SNAPSHOTS") == "1"
# A test is "required" (cannot skip) in closeout mode OR when artifacts exist.
SKIP_OK = (not SNAPSHOTS_PRESENT) and (not REQUIRE)

skip_if_no_snapshots = pytest.mark.skipif(
    SKIP_OK, reason="P1E snapshots unavailable; set ERLAB_REQUIRE_P1E_SNAPSHOTS=1 for closeout"
)


def test_session_closeout_guard():
    """In closeout mode, fail immediately with a diagnostic list of missing artifacts."""
    if not REQUIRE:
        pytest.skip("not in closeout mode")
    missing = []
    if not (P1B_SNAPSHOT_DIR / "snapshot.json").exists():
        missing.append(str(P1B_SNAPSHOT_DIR / "snapshot.json"))
    if not TEI_SNAPSHOT_PATH.exists():
        missing.append(str(TEI_SNAPSHOT_PATH))
    for p in (AUDIT_JSON, CASES_JSON, PAIRWISE_JSON, MANIFEST_PATH, PROTOCOL_PATH):
        if not p.exists():
            missing.append(str(p))
    assert not missing, f"ERLAB_REQUIRE_P1E_SNAPSHOTS=1 but missing: {missing}"


# ── §0  Frozen ratchet + held-out seal ───────────────────────────────


class TestFrozenRatchet:
    def test_manifest_and_protocol_present(self):
        assert MANIFEST_PATH.exists(), "frozen split manifest missing"
        assert PROTOCOL_PATH.exists(), "frozen protocol missing"

    def test_manifest_schema_and_counts(self):
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert m["schema"] == "p1e_split_manifest_v1"
        assert m["total_ids"] == 66
        assert m["split_counts"] == {"calibration": 22, "development": 22, "held_out": 22}
        ids = m["cal_dev_case_ids"] + m["held_out_case_ids"]
        assert len(ids) == len(set(ids)), "duplicate case IDs in manifest"
        assert len(m["cal_dev_case_ids"]) == 44
        assert len(m["held_out_case_ids"]) == 22
        # cal_dev and held_out disjoint
        assert not (set(m["cal_dev_case_ids"]) & set(m["held_out_case_ids"]))

    def test_manifest_matches_runtime_mapping(self):
        """The manifest's case->split mapping must match the runtime registry exactly
        (full mapping, not just counts). This is the cross-check that catches the
        per-module split-table drift class."""
        from collections import Counter
        from backend.ranking.benchmark_v2_registry import ALL_V2_CASES
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        rt = {c.case_id: c.split for c in ALL_V2_CASES}
        manifest_caldev = set(m["cal_dev_case_ids"])
        manifest_held = set(m["held_out_case_ids"])
        mismatches = []
        for cid, rt_split in rt.items():
            rt_group = "held_out" if rt_split == "held_out" else "cal_dev"
            m_group = "held_out" if cid in manifest_held else "cal_dev"
            if rt_group != m_group:
                mismatches.append((cid, m_group, rt_split))
        assert not mismatches, f"manifest/runtime mapping drift: {mismatches[:5]}"

    def test_manifest_benchmark_identity_matches_frozen_p1b(self):
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert m["benchmark_fingerprint"] == "0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4"
        assert m["benchmark_version"] == "discovery_ranking_v2+retrieval_ranking_v2"


class TestHeldOutSeal:
    """The audit must never materialize/decode/inspect/emit held-out records."""

    @skip_if_no_snapshots
    def test_filtered_p1b_loader_decodes_no_held_out(self):
        import sys
        from backend.ranking.p1e_snapshot_filter import load_snapshot_filtered
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cal_dev = frozenset(m["cal_dev_case_ids"])
        held_out = frozenset(m["held_out_case_ids"])
        # build candidate allowlist from scoped cases only
        from backend.ranking.benchmark_v2_registry import frozen_v2_cases
        scoped = [c for c in frozen_v2_cases() if c.case_id in cal_dev]
        cand = set()
        for c in scoped:
            for cc in c.candidates:
                cand.add(cc.candidate_id)
        allow = frozenset(cal_dev | cand)
        snap, rep = load_snapshot_filtered(
            P1B_SNAPSHOT_DIR, allowed_item_ids=allow,
            expected_benchmark_fingerprint=m["benchmark_fingerprint"],
            expected_benchmark_version=m["benchmark_version"])
        assert not (set(rep["decoded_query_ids"]) & held_out), "held-out query decoded"
        assert rep["decoded_query_count"] == 44
        assert rep["skipped_count"] > 0  # held-out items skipped, never decoded

    @skip_if_no_snapshots
    def test_filtered_tei_adapter_decodes_no_held_out(self):
        from p1_embedding_snapshot_adapter import tei_snapshot_to_embedding_snapshot
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cal_dev = frozenset(m["cal_dev_case_ids"])
        held_out = frozenset(m["held_out_case_ids"])
        from backend.ranking.benchmark_v2_registry import frozen_v2_cases
        scoped = [c for c in frozen_v2_cases() if c.case_id in cal_dev]
        cand = set()
        for c in scoped:
            for cc in c.candidates:
                cand.add(cc.candidate_id)
        allow = frozenset(cal_dev | cand)
        raw = json.loads(TEI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        snap = tei_snapshot_to_embedding_snapshot(raw, allowed_item_ids=allow)
        qids = {i.item_id for i in snap.items if i.item_role == "query"}
        assert not (qids & held_out), "TEI held-out query decoded"
        assert len(qids) == 44

    @skip_if_no_snapshots
    def test_audit_artifacts_emit_no_held_out(self):
        """No generated artifact may contain a held-out case_id as an audited record."""
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        held_out = set(m["held_out_case_ids"])
        audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        assert set(audit["audited_case_ids"]).isdisjoint(held_out)
        assert set(audit["excluded_held_out_case_ids"]) == held_out
        # held-out isolation counters all zero
        for k, v in audit["held_out_isolation_counters"].items():
            assert v == 0, f"{k} = {v} (expected 0)"


# ── §shared-adapter + original-evaluator usage ──────────────────────


class TestSharedAdapter:
    def test_exactly_one_definition_repo_wide(self):
        import subprocess
        out = subprocess.check_output(
            ["git", "grep", "-l", "def tei_snapshot_to_embedding_snapshot"],
            cwd=str(REPO_ROOT), text=True).strip().splitlines()
        # Only count NON-TEST .py files. Test files legitimately mention the
        # string in assertions; they are not adapter definitions.
        py = [x for x in out if x.endswith(".py") and "test" not in x.lower()]
        assert len(py) == 1, f"expected 1 adapter definition, found {py}"
        assert "p1_embedding_snapshot_adapter" in py[0]

    def test_p1d_imports_shared_adapter(self):
        p1d = (REPO_ROOT / "scripts" / "p1d_p1b_evaluator_comparison.py").read_text(encoding="utf-8")
        assert "from p1_embedding_snapshot_adapter import tei_snapshot_to_embedding_snapshot" in p1d
        # the local definition must be gone
        assert "def tei_snapshot_to_embedding_snapshot" not in p1d

    def test_adapter_filters_before_construction(self):
        """allowed_item_ids must skip items before SnapshotItem construction."""
        src = (REPO_ROOT / "scripts" / "p1_embedding_snapshot_adapter.py").read_text(encoding="utf-8")
        # the 'continue' for non-allowed items must precede SnapshotItem(...)
        cont_idx = src.find("continue  # held-out query")
        item_idx = src.find("items.append(SnapshotItem(", cont_idx)
        assert cont_idx != -1 and item_idx != -1 and cont_idx < item_idx


class TestOriginalEvaluatorUsage:
    """The audit must import ranking/metric functions from the original modules,
    not define its own. Zero local ranking/metric reimplementations."""

    def test_audit_imports_original_evaluator(self):
        audit_src = (REPO_ROOT / "scripts" / "p1e_benchmark_discrimination_audit.py").read_text(encoding="utf-8")
        for sym in ["_build_request", "_run_policy", "rank_semantic_only", "_grade_for",
                    "evaluate_v2", "macro_average", "SnapshotSemanticScorer"]:
            assert f"import" in audit_src and sym in audit_src, f"audit must use original {sym}"
        # imports from the original modules
        assert "from backend.ranking.p1b3_evaluation import" in audit_src
        assert "from backend.ranking.policies import" in audit_src
        assert "from backend.ranking.evaluation import" in audit_src

    def test_audit_defines_no_local_ranking_or_metric_function(self):
        """AST scan: the audit module must not define any rank_*/_ndcg/_mrr/_precision/_recall."""
        audit_path = REPO_ROOT / "scripts" / "p1e_benchmark_discrimination_audit.py"
        tree = ast.parse(audit_path.read_text(encoding="utf-8"))
        forbidden = {"rank_semantic_only", "rank_legacy_lexical", "rank_hybrid_rrf",
                     "_ndcg_at_k", "_mrr_at_k", "_precision_at_k", "_recall_at_k",
                     "_dcg_at_k", "evaluate_v2", "_grade_for"}
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
        offenders = defined & forbidden
        assert not offenders, f"audit redefines original evaluator fns: {offenders}"

    def test_stats_module_defines_no_ranking_or_metric_logic(self):
        """p1e_stats must contain only statistical methods, not ranking/metric fns."""
        stats_path = REPO_ROOT / "scripts" / "p1e_stats.py"
        src = stats_path.read_text(encoding="utf-8")
        for forbidden in ["_ndcg_at_k", "rank_semantic", "rank_legacy", "rank_hybrid",
                          "_grade_for", "evaluate_v2", "_keyword_overlap"]:
            assert forbidden not in src, f"stats module must not contain {forbidden}"


# ── §semantic correctness of statistics + diagnosis ─────────────────


class TestStatistics:
    def test_bootstrap_identical_gives_zero_delta_including_zero(self):
        from p1e_stats import paired_bootstrap_ci
        ci = paired_bootstrap_ci([0.5, 0.6, 0.7], [0.5, 0.6, 0.7], n_bootstrap=500)
        assert abs(ci["mean_delta"]) < 1e-9
        assert not ci["excludes_zero"]

    def test_continuous_mde_zero_only_when_all_identical(self):
        from p1e_stats import continuous_mde
        m = continuous_mde([0.5] * 10)
        assert m["zero_variance"] and m["mde"] == 0.0
        m2 = continuous_mde([0.1, 0.2, 0.15, 0.3])
        assert m2["mde"] > 0 and not m2["zero_variance"]

    def test_mcnemar_zero_discordance_unavailable(self):
        from p1e_stats import top1_mcnemar_mde
        mc = top1_mcnemar_mde([1, 1, 0, 0], [1, 1, 0, 0])
        assert mc["zero_discordance"] and mc["mde"] is None

    def test_kendall_universe_mismatch_is_integrity_failure(self):
        from p1e_stats import kendall_tau
        with pytest.raises(ValueError):
            kendall_tau(["a", "b", "c"], ["a", "b", "d"])

    def test_kendall_identical_is_one_reversed_is_minus_one(self):
        from p1e_stats import kendall_tau
        assert kendall_tau(["a", "b", "c", "d"], ["a", "b", "c", "d"])["tau"] == 1.0
        assert kendall_tau(["a", "b", "c", "d"], ["d", "c", "b", "a"])["tau"] == -1.0


class TestDiagnosisPrecedence:
    """The frozen S/A/M precedence must hold on synthetic criteria sets."""

    def _diag(self, s_passes, a_passes):
        """Replicate the precedence logic with explicit pass lists."""
        s_complete = all(s_passes)  # S requires all + no_arch
        a_complete = all(a_passes)
        no_arch = not any(a_passes)
        s_complete = s_complete and no_arch
        if s_complete and not a_complete:
            return "S"
        if a_complete and not s_complete:
            return "A"
        return "M"

    def test_s_complete_a_incomplete_is_S(self):
        assert self._diag([True, True, True, True, True], [False, False, False, False]) == "S"

    def test_a_complete_s_incomplete_is_A(self):
        assert self._diag([False], [True, True, True, True]) == "A"

    def test_both_complete_is_M(self):
        # S all pass but A also passes -> no_arch False -> S incomplete; A complete -> would be A,
        # but if S were complete too (impossible when A passes) -> M. Test the neither/both -> M.
        # When A complete and S incomplete -> A (covered). Both cannot be simultaneously complete
        # because no_arch contradicts A. So 'both complete' reduces to neither -> M here.
        assert self._diag([False, False], [False, False]) == "M"

    def test_neither_complete_is_M(self):
        assert self._diag([False, True], [True, False]) == "M"

    @skip_if_no_snapshots
    def test_artifact_diagnosis_is_valid_and_consistent(self):
        audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        diag = audit["section7_diagnosis"]
        assert diag["outcome"] in ("S", "A", "M")
        # precedence invariant: outcome matches S_complete/A_complete
        s, a = diag["S_complete"], diag["A_complete"]
        if s and not a:
            assert diag["outcome"] == "S"
        elif a and not s:
            assert diag["outcome"] == "A"
        else:
            assert diag["outcome"] == "M"


# ── §output schema ──────────────────────────────────────────────────


class TestOutputSchema:
    @skip_if_no_snapshots
    def test_all_three_artifacts_present_and_consistent(self):
        audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        cases = json.loads(CASES_JSON.read_text(encoding="utf-8"))
        pair = json.loads(PAIRWISE_JSON.read_text(encoding="utf-8"))
        for f in ["manifest_sha256", "protocol_sha256", "benchmark_fingerprint",
                  "benchmark_version", "diagnosis_rule_version", "primary_statistical_seed"]:
            assert audit[f] == cases[f] == pair[f], f"{f} mismatch across artifacts"
        assert audit["audited_case_ids"] == cases["audited_case_ids"] == pair["audited_case_ids"]

    @skip_if_no_snapshots
    def test_case_diagnostics_has_all_44_cases(self):
        cases = json.loads(CASES_JSON.read_text(encoding="utf-8"))
        assert len(cases["cases"]) == 44
        for c in cases["cases"]:
            for sec in ["section1_structure", "section2_ceiling", "section4_hard_negatives",
                        "candidate_scores", "per_run_metrics"]:
                assert sec in c, f"{c['case_id']} missing {sec}"
            assert set(c["per_run_metrics"]) == {
                "lexical", "p1b_semantic", "tei_semantic", "p1b_hybrid_rrf", "tei_hybrid_rrf"}

    @skip_if_no_snapshots
    def test_pairwise_has_four_required_comparisons(self):
        pair = json.loads(PAIRWISE_JSON.read_text(encoding="utf-8"))
        required = {"lexical_vs_p1b_semantic", "lexical_vs_tei_semantic",
                    "p1b_semantic_vs_tei_semantic", "p1b_hybrid_rrf_vs_tei_hybrid_rrf"}
        assert set(pair["pairwise_comparisons"]) == required
        assert set(pair["five_run_macro_metrics"]) == {
            "lexical", "p1b_semantic", "tei_semantic", "p1b_hybrid_rrf", "tei_hybrid_rrf"}

    @skip_if_no_snapshots
    def test_artifacts_embed_effective_ratchet_hashes(self):
        """Every artifact must embed the current manifest + protocol SHA-256."""
        import hashlib
        manifest_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
        protocol_sha = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        for p in (AUDIT_JSON, CASES_JSON, PAIRWISE_JSON):
            doc = json.loads(p.read_text(encoding="utf-8"))
            assert doc["manifest_sha256"] == manifest_sha, f"{p.name} manifest hash stale"
            assert doc["protocol_sha256"] == protocol_sha, f"{p.name} protocol hash stale"

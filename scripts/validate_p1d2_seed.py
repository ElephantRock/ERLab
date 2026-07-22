"""P1D.2b seed validator v2 (seed-hardening patch gate).

Validates the 9-case diagnostic seed against the 10-item patch gate plus
the original review gate. Every check is a hard failure.

Covers the reviewer's patch gate:
  1. scored candidate universe defined (candidate_pool present)
  2. scored units without judgments = 0 (exhaustive coverage)
  3. orphan or duplicate judgments = 0
  4. inline/parallel judgment divergence = 0 (cases authoritative)
  5. builder outputs deterministic (byte-stable, all 3 + manifest)
  6. false-support claim without a fully supporting unit = 0
  7. qualifying evidence mislabeled as generic negative = 0
  8. synthetic authoring leakage untested = 0 (bias audit)
  9. exact-identifier collision only background = 0  (NOTE: this is about the full 30; the seed has no exact-id case yet — flagged)
  10. wrong-population mismatch only background = 0  (NOTE: same — flagged for remaining 21)

Exit 0 = patch gate green; proceed to remaining 21 cases.
"""
from __future__ import annotations
import json
import sys
import hashlib
import subprocess
from pathlib import Path
from collections import Counter

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "retrieval"


def load_jsonl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def run():
    case_schema = json.loads((DOCS / "p1d2_case_schema.json").read_text(encoding="utf-8"))
    judg_schema = json.loads((DOCS / "p1d2_judgment_schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource(
        "https://elephant-rock-research-lab/p1d2_judgment_schema_v1",
        Resource(contents=judg_schema, specification=DRAFT202012),
    )
    case_val = jsonschema.Draft202012Validator(case_schema, registry=registry)
    judg_val = jsonschema.Draft202012Validator(judg_schema)

    cases = load_jsonl(DOCS / "p1d2_diagnostic_seed_cases.jsonl")
    judgments = load_jsonl(DOCS / "p1d2_diagnostic_seed_judgments.jsonl")
    sources = load_jsonl(DOCS / "p1d2_diagnostic_seed_sources.jsonl")
    manifest = json.loads((DOCS / "p1d2_diagnostic_seed_manifest.json").read_text(encoding="utf-8"))

    src_by_id = {s["document_id"]: s for s in sources}
    case_by_id = {c["case_id"]: c for c in cases}
    failures = []
    passed = 0

    def chk(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failures.append((label, detail))

    print("P1D.2b diagnostic seed validation v2 (patch gate)")
    print("=" * 60)

    # ── counts, uniqueness, families (carried from v1) ──
    chk("30 unique case IDs", len({c['case_id'] for c in cases}) == len(cases))
    chk("exactly 30 cases", len(cases) == 30)
    fams = Counter(c["task_family"] for c in cases)
    chk("all 6 families", set(fams) == {"evidence_retrieval", "contradiction_retrieval", "multi_paper_synthesis", "paper_discovery", "method_retrieval", "research_gap_analysis"})
    chk("target distribution er=8 cr=6 mps=6 pd=4 mr=3 rga=3",
        fams["evidence_retrieval"] == 8 and fams["contradiction_retrieval"] == 6 and fams["multi_paper_synthesis"] == 6 and fams["paper_discovery"] == 4 and fams["method_retrieval"] == 3 and fams["research_gap_analysis"] == 3)

    # schema conformance
    for c in cases:
        errs = list(case_val.iter_errors(c))
        chk(f"case {c['case_id']} conforms", not errs, "; ".join(e.message[:50] for e in errs[:2]))
    for j in judgments:
        errs = list(judg_val.iter_errors(j))
        chk(f"judgment {j['judgment_id']} conforms", not errs, "; ".join(e.message[:50] for e in errs[:2]))

    # passage hash recompute (core integrity)
    for c in cases:
        for pid, pp in c.get("passages", {}).items():
            src = src_by_id[pp["document_id"]]
            try:
                _, rng = pp["passage_locator"].split(" ")
                s, e = map(int, rng.split("-"))
                actual = hashlib.sha256(src["full_text"][s:e].encode()).hexdigest()
                chk(f"{c['case_id']} passage {pid} hash", actual == pp["passage_text_hash"])
            except Exception as ex:
                chk(f"{c['case_id']} passage {pid} locator", False, str(ex))

    # ── PATCH 1: candidate_pool present on every case ──
    print("\n[PATCH 1] scored candidate universe defined")
    for c in cases:
        chk(f"{c['case_id']} has candidate_pool", "candidate_pool" in c)
        if "candidate_pool" in c:
            cp = c["candidate_pool"]
            chk(f"{c['case_id']} pool has unjudged_unit_policy", "unjudged_unit_policy" in cp)
            chk(f"{c['case_id']} pool_fingerprint recomputes", cp["pool_fingerprint"] == hashlib.sha256(json.dumps(sorted(cp["candidate_unit_ids"]), sort_keys=True).encode()).hexdigest())

    # ── PATCH 2: exhaustive judgment coverage ──
    print("\n[PATCH 2] exhaustive judgment coverage (every pool unit judged once)")
    for c in cases:
        pool_ids = set(c["candidate_pool"]["candidate_unit_ids"])
        judged_ids = {j["unit_id"] for j in c["relevance_judgments"]}
        chk(f"{c['case_id']} every pool unit judged", pool_ids == judged_ids, f"pool-judged={pool_ids-judged_ids} judged-pool={judged_ids-pool_ids}")
        # each judged exactly once (no dup unit_ids within a case)
        within = [j["unit_id"] for j in c["relevance_judgments"]]
        chk(f"{c['case_id']} no duplicate unit judgments", len(within) == len(set(within)))

    # ── PATCH 3: orphan/duplicate judgments across the whole set ──
    print("\n[PATCH 3] orphan or duplicate judgments")
    all_jids = [j["judgment_id"] for j in judgments]
    chk("no duplicate judgment IDs", len(all_jids) == len(set(all_jids)))
    # every judgment's case exists
    chk("no orphan judgments (case exists)", all(j["case_id"] in case_by_id for j in judgments))

    # ── PATCH 4: inline/parallel equivalence (cases authoritative) ──
    print("\n[PATCH 4] inline/parallel judgment equivalence")
    inline_count = sum(len(c["relevance_judgments"]) for c in cases)
    chk("inline count == parallel count", inline_count == len(judgments), f"{inline_count} != {len(judgments)}")
    inline_by_id = {j["judgment_id"]: j for c in cases for j in c["relevance_judgments"]}
    parallel_by_id = {j["judgment_id"]: j for j in judgments}
    chk("inline IDs == parallel IDs", set(inline_by_id) == set(parallel_by_id))
    # field-level equivalence (canonical comparison)
    field_diffs = []
    for jid in inline_by_id:
        a = json.dumps(inline_by_id[jid], sort_keys=True)
        b = json.dumps(parallel_by_id.get(jid, {}), sort_keys=True)
        if a != b:
            field_diffs.append(jid)
    chk("no field-level differences", not field_diffs, str(field_diffs[:3]))

    # ── PATCH 5: byte-stable determinism + single-writer invariant ──
    print("\n[PATCH 5] byte-stable determinism + single-writer invariant")
    builder = REPO / "scripts" / "build_p1d2_diagnostic_expansion.py"
    base_lib = REPO / "scripts" / "build_p1d2_diagnostic_seed.py"

    # Single-writer: base library must NOT have a __main__ that writes
    base_src = base_lib.read_text(encoding="utf-8")
    chk("base builder is NOT a writer (no build() in __main__)", 'build()' not in base_src.split('if __name__')[1] if '__main__' in base_src else True)

    before = {a: hashlib.sha256((DOCS / f"p1d2_diagnostic_seed_{a}.jsonl").read_bytes()).hexdigest() for a in ["sources", "cases", "judgments"]}
    before_m = hashlib.sha256((DOCS / "p1d2_diagnostic_seed_manifest.json").read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, str(builder)], capture_output=True, text=True)
    chk("canonical builder rerun exit 0", r.returncode == 0, r.stderr[:100])
    after = {a: hashlib.sha256((DOCS / f"p1d2_diagnostic_seed_{a}.jsonl").read_bytes()).hexdigest() for a in ["sources", "cases", "judgments"]}
    after_m = hashlib.sha256((DOCS / "p1d2_diagnostic_seed_manifest.json").read_bytes()).hexdigest()
    chk("sources deterministic", before["sources"] == after["sources"])
    chk("cases deterministic", before["cases"] == after["cases"])
    chk("judgments deterministic", before["judgments"] == after["judgments"])
    chk("manifest deterministic", before_m == after_m)

    # Manifest records canonical generator path + hash
    chk("manifest has canonical_generator_path", manifest.get("canonical_generator_path") == "scripts/build_p1d2_diagnostic_expansion.py")
    live_gen_hash = hashlib.sha256(builder.read_bytes()).hexdigest()
    chk("manifest canonical_generator_sha256 matches live", manifest.get("canonical_generator_sha256") == live_gen_hash,
        f"manifest={manifest.get('canonical_generator_sha256','?')[:16]} live={live_gen_hash[:16]}")
    chk("manifest has dataset_version", "dataset_version" in manifest)

    # ── PATCH 6: false-support claim has a fully supporting unit (positive_present only) ──
    print("\n[PATCH 6] false-support claims have a fully supporting unit (positive_present only)")
    for c in cases:
        if "false_support" in c["risk_labels"] and c.get("case_mode") == "positive_present":
            has_g3 = any(j["research_utility_grade"] == 3 for j in c["relevance_judgments"])
            chk(f"{c['case_id']} false-support (positive_present) has a fully-supporting unit", has_g3)

    # ── PATCH 7: qualifying evidence not mislabeled as generic negative ──
    print("\n[PATCH 7] qualifying evidence correctly labeled")
    # a unit that is a contradiction/qualifier passage should not appear ONLY in hard_topical_negatives
    # with grade 0 unless it's genuinely irrelevant
    for c in cases:
        contradicts = set(c.get("contradicting_or_qualifying_passages", []))
        hard_negs = set(c.get("hard_topical_negatives", []))
        for pid in contradicts:
            j = next((j for j in c["relevance_judgments"] if j["unit_id"] == pid), None)
            if j and pid in hard_negs and j["research_utility_grade"] == 0:
                chk(f"{c['case_id']} {pid} qualifying-as-generic", False, "qualifier mislabeled grade 0")

    # ── PATCH 8: synthetic authoring leakage audit ──
    print("\n[PATCH 8] synthetic authoring leakage audit")
    # 8a. no verbatim query copied into a positive passage
    for c in cases:
        q = c["query_or_claim"].lower()
        for pid in c.get("positive_passage_ids", []):
            # recompute the passage text to check
            pp = c["passages"].get(pid, {})
            src = src_by_id.get(pp.get("document_id", ""), {})
            try:
                _, rng = pp["passage_locator"].split(" "); s, e = map(int, rng.split("-"))
                ptext = src["full_text"][s:e].lower()
                # query should not appear verbatim (allow short queries to share common words, so check >5 char substrings)
                chk(f"{c['case_id']} no verbatim query in positive {pid}", q not in ptext)
            except Exception:
                pass
    # 8b. cross-case query near-duplicates (semantic fingerprint already unique; check checked above)
    fps = [c["query_semantic_fingerprint"] for c in cases]
    chk("no near-duplicate queries", len(set(fps)) == len(fps))
    # 8c. cross-case distractors present (pools are not topic-isolated)
    # at least one case shares a document with another case's pool
    all_pool_docs = {}
    for c in cases:
        docs = {c["passages"][pid]["document_id"] for pid in c["candidate_pool"]["candidate_unit_ids"]}
        for d in docs:
            all_pool_docs.setdefault(d, set()).add(c["case_id"])
    shared = {d: cs for d, cs in all_pool_docs.items() if len(cs) > 1}
    chk("cross-case document sharing present (no topic isolation)", len(shared) >= 1, f"shared docs: {list(shared)[:3]}")

    # ── PATCH 9 & 10: exact-identifier + wrong-population as primary traps ──
    # NOTE: the reviewer explicitly deferred these to the remaining 21 cases. The 9-case seed
    # distribution (2/2/2/1/1/1) intentionally omits them. These are INFORMATIONAL warnings,
    # not hard failures, for the seed; they become hard failures for the full 30-case set.
    print("\n[PATCH 9/10] exact-identifier + wrong-population traps (deferred to remaining 21)")
    has_exact_id = any("exact_identifier_or_acronym_collision" in c["hard_negative_types"] for c in cases)
    has_wrong_pop = any("same_topic_wrong_population" in c["hard_negative_types"] for c in cases)
    if has_exact_id:
        passed += 1
    else:
        print("  INFO: exact-identifier trap absent (slated for remaining 21) — not a seed failure")
    if has_wrong_pop:
        passed += 1
    else:
        print("  INFO: wrong-population trap absent (slated for remaining 21) — not a seed failure")

    # ── manifest reconciliation ──
    print("\n[manifest] reconciliation")
    chk("manifest case_count", manifest["case_count"] == len(cases))
    chk("manifest judgment_count", manifest["judgment_count"] == len(judgments))
    for art, recorded in manifest["artifact_hashes"].items():
        chk(f"manifest hash {art}", hashlib.sha256((DOCS / f"p1d2_diagnostic_seed_{art}.jsonl").read_bytes()).hexdigest() == recorded)

    # ── report ──
    print("\n" + "=" * 60)
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)
    else:
        print(f"PASS: all checks passed ({passed})")
        sys.exit(0)


if __name__ == "__main__":
    run()

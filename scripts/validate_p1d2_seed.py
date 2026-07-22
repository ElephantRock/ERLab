"""P1D.2b seed validator: vertical-slice quality gate.

Validates the 9-case diagnostic seed against the seed review gate. Every
assertion is a hard failure. Run after build_p1d2_diagnostic_seed.py.

Exit 0 = seed passes; proceed to remaining 21 cases.
Non-zero = defects present; fix before authoring more.
"""
from __future__ import annotations
import json
import sys
import hashlib
from pathlib import Path
from collections import Counter

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "retrieval"

CASES_PATH = DOCS / "p1d2_diagnostic_seed_cases.jsonl"
JUDG_PATH = DOCS / "p1d2_diagnostic_seed_judgments.jsonl"
SRC_PATH = DOCS / "p1d2_diagnostic_seed_sources.jsonl"
MANIFEST_PATH = DOCS / "p1d2_diagnostic_seed_manifest.json"


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

    cases = load_jsonl(CASES_PATH)
    judgments = load_jsonl(JUDG_PATH)
    sources = load_jsonl(SRC_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    src_by_id = {s["document_id"]: s for s in sources}
    judg_by_id = {j["judgment_id"]: j for j in judgments}
    case_by_id = {c["case_id"]: c for c in cases}

    failures = []
    passed = 0

    def chk(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failures.append((label, detail))

    print("P1D.2b diagnostic seed validation")
    print("=" * 60)

    # ── 1. counts and uniqueness ──
    print("\n[1] counts and uniqueness")
    chk("exactly 9 cases", len(cases) == 9, f"got {len(cases)}")
    chk("9 unique case IDs", len({c['case_id'] for c in cases}) == 9, "duplicate IDs")
    chk("unique judgment IDs", len({j['judgment_id'] for j in judgments}) == len(judgments), "duplicate judgment IDs")
    print(f"  cases={len(cases)} judgments={len(judgments)} sources={len(sources)}")

    # ── 2. task family coverage ──
    print("\n[2] task family coverage")
    fams = Counter(c["task_family"] for c in cases)
    chk("all 6 families present", set(fams) == {
        "evidence_retrieval", "contradiction_retrieval", "multi_paper_synthesis",
        "paper_discovery", "method_retrieval", "research_gap_analysis"}, f"got {set(fams)}")
    chk("evidence_retrieval = 2", fams.get("evidence_retrieval", 0) == 2, f"got {fams.get('evidence_retrieval', 0)}")
    chk("contradiction_retrieval = 2", fams.get("contradiction_retrieval", 0) == 2, f"got {fams.get('contradiction_retrieval', 0)}")
    chk("multi_paper_synthesis = 2", fams.get("multi_paper_synthesis", 0) == 2, f"got {fams.get('multi_paper_synthesis', 0)}")
    chk("paper_discovery >= 1", fams.get("paper_discovery", 0) >= 1)
    chk("method_retrieval >= 1", fams.get("method_retrieval", 0) >= 1)
    chk("research_gap_analysis >= 1", fams.get("research_gap_analysis", 0) >= 1)
    print(f"  distribution: {dict(sorted(fams.items()))}")

    # ── 3. schema conformance ──
    print("\n[3] schema conformance (case + judgment)")
    for c in cases:
        errs = list(case_val.iter_errors(c))
        chk(f"case {c['case_id']} conforms", not errs, "; ".join(e.message[:60] for e in errs[:2]))
    for j in judgments:
        errs = list(judg_val.iter_errors(j))
        chk(f"judgment {j['judgment_id']} conforms", not errs, "; ".join(e.message[:60] for e in errs[:2]))

    # ── 4. reference resolution: every passage in every case resolves to a real source ──
    print("\n[4] reference resolution (documents + passages)")
    for c in cases:
        for doc_id in c.get("source_document_ids", []):
            chk(f"{c['case_id']}: source doc {doc_id} exists", doc_id in src_by_id, f"missing {doc_id}")
        for pid, pp in c.get("passages", {}).items():
            # the passage record's document must exist
            did = pp["document_id"]
            chk(f"{c['case_id']}: passage {pid} doc {did} exists", did in src_by_id, f"missing doc {did}")
            # the document_content_hash must match the source document's hash
            src = src_by_id[did]
            chk(f"{c['case_id']}: passage {pid} document_content_hash matches source",
                pp["document_content_hash"] == src["document_content_hash"],
                f"hash mismatch for {did}")

    # ── 5. passage text hashes recompute correctly from source text ──
    print("\n[5] passage text hashes recompute from source text (the core integrity check)")
    for c in cases:
        for pid, pp in c.get("passages", {}).items():
            src = src_by_id[pp["document_id"]]
            # parse the locator "chars START-END"
            loc = pp["passage_locator"]
            try:
                _, rng = loc.split(" ")
                s, e = rng.split("-")
                s, e = int(s), int(e)
                actual_text = src["full_text"][s:e]
                actual_hash = hashlib.sha256(actual_text.encode("utf-8")).hexdigest()
                chk(f"{c['case_id']}: passage {pid} text hash matches extracted text",
                    actual_hash == pp["passage_text_hash"],
                    f"locator {loc} recomputed {actual_hash[:12]} != recorded {pp['passage_text_hash'][:12]}")
            except Exception as ex:
                chk(f"{c['case_id']}: passage {pid} locator parseable", False, f"locator {loc}: {ex}")

    # ── 6. every judgment references a passage that exists in its case ──
    print("\n[6] judgments reference resolvable units")
    for j in judgments:
        cid = j["case_id"]
        chk(f"{j['judgment_id']}: case exists", cid in case_by_id, f"missing case {cid}")
        if cid in case_by_id:
            c = case_by_id[cid]
            # judgment unit must be a positive or negative or contradiction passage in the case
            all_units = set(c.get("passages", {}).keys())
            chk(f"{j['judgment_id']}: unit {j['unit_id']} in case passages",
                j["unit_id"] in all_units, f"unit {j['unit_id']} not in case {cid} passages")
            # judgment unit_text_hash must match the passage's hash
            if j["unit_id"] in c.get("passages", {}):
                chk(f"{j['judgment_id']}: unit_text_hash matches passage hash",
                    j["unit_text_hash"] == c["passages"][j["unit_id"]]["passage_text_hash"])

    # ── 7. every case has a risk-shaped hard negative (not generic) ──
    print("\n[7] risk-shaped hard negatives")
    for c in cases:
        chk(f"{c['case_id']}: has hard_negative_types", len(c.get("hard_negative_types", [])) >= 1, "no hard negative types")
        # hard negative must resolve: either a passage in case.passages or a known source doc
        for hn in c.get("hard_topical_negatives", []):
            resolves = hn in c.get("passages", {}) or hn in src_by_id
            chk(f"{c['case_id']}: hard negative {hn} resolves", resolves, f"unresolved {hn}")

    # ── 8. evidence_lineage_id is real and tested (at least one MPS case distinguishes lineages) ──
    print("\n[8] evidence lineage distinction")
    mps_cases = [c for c in cases if c["task_family"] == "multi_paper_synthesis"]
    for c in mps_cases:
        lineages = {pp["evidence_lineage_id"] for pp in c.get("passages", {}).values()}
        chk(f"{c['case_id']}: spans >=2 distinct lineages", len(lineages) >= 2,
            f"only {lineages}; lineage field untested")
    # specifically, diag_mps_001 must have the Amsterdam+Stanford distinction
    if "diag_mps_001" in case_by_id:
        mps1 = case_by_id["diag_mps_001"]
        lins = {pp["evidence_lineage_id"] for pp in mps1.get("passages", {}).values()}
        chk("diag_mps_001: Amsterdam + Stanford lineages both present",
            "elin_gnn_amsterdam" in lins and "elin_gnn_stanford" in lins, f"got {lins}")

    # ── 9. all judgments provisional, non-scoreable, non-sealable ──
    print("\n[9] provisional-only judgment state")
    for j in judgments:
        chk(f"{j['judgment_id']}: review_status=provisional", j["review_status"] == "provisional")
        chk(f"{j['judgment_id']}: eligible_for_scoring=false", j["eligible_for_scoring"] is False)
        chk(f"{j['judgment_id']}: eligible_for_seal=false", j["eligible_for_seal"] is False)
        chk(f"{j['judgment_id']}: requires_external_dual_review=true", j["requires_external_dual_review"] is True)

    # ── 10. no policy-output leakage ──
    print("\n[10] authoring blindness / no policy leakage")
    for j in judgments:
        chk(f"{j['judgment_id']}: policy_outputs_visible_to_reviewers=false",
            j.get("policy_outputs_visible_to_reviewers") is False)
    for c in cases:
        chk(f"{c['case_id']}: benchmark_role=diagnostic", c["benchmark_role"] == "diagnostic")

    # ── 11. passage tasks not at paper level ──
    print("\n[11] passage-granularity tasks enforced")
    for c in cases:
        if c["task_family"] in ("evidence_retrieval", "contradiction_retrieval"):
            chk(f"{c['case_id']}: retrieved_unit=passage", c["retrieved_unit"] == "passage")

    # ── 12. deterministic manifest ──
    print("\n[12] deterministic manifest")
    chk("manifest case_count matches", manifest["case_count"] == len(cases), f"{manifest['case_count']} != {len(cases)}")
    chk("manifest judgment_count matches", manifest["judgment_count"] == len(judgments))
    chk("manifest source_count matches", manifest["source_document_count"] == len(sources))
    # recompute manifest hashes
    def fp(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    for art, recorded in manifest["artifact_hashes"].items():
        path = DOCS / f"p1d2_diagnostic_seed_{art}.jsonl"
        chk(f"manifest hash {art} matches file", fp(path) == recorded, f"{art}: {fp(path)[:12]} != {recorded[:12]}")

    # ── 13. no near-duplicate queries (semantic fingerprint) ──
    print("\n[13] no near-duplicate queries")
    fps = [c["query_semantic_fingerprint"] for c in cases]
    chk("all query semantic fingerprints unique", len(set(fps)) == len(fps), f"{len(fps)-len(set(fps))} duplicates")

    # ── report ──
    print("\n" + "=" * 60)
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)
    else:
        print(f"PASS: all checks passed ({passed})")
        print("Seed meets the review gate. Proceed to remaining 21 cases.")
        sys.exit(0)


if __name__ == "__main__":
    run()

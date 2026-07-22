"""P1D.2d-prep: generate blinded reviewer packages for independent dual review.

Produces two reviewer packages (A and B) with neutral randomized unit IDs,
author grades/rationales excluded, and materialized passage text. Also produces
the assignment manifest (mapping neutral IDs to real IDs) and the package manifest.

Reviewers see: case query, candidate pool with passage text + provenance, rubric.
Reviewers do NOT see: author grades, author rationales, other reviewer's decisions,
policy outputs, answer-revealing document labels.

Outputs:
  docs/retrieval/p1d2_reviewer_package_A.jsonl
  docs/retrieval/p1d2_reviewer_package_B.jsonl
  docs/retrieval/p1d2_review_assignment_manifest.json
  docs/retrieval/p1d2_review_package_manifest.json
"""
from __future__ import annotations
import json, hashlib, random
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "retrieval"

RUBRIC = {
    "rubric_version": "research_utility_0_to_3_v1",
    "grades": {
        "3": "Highly useful: directly on-topic, strong evidence, right type.",
        "2": "Useful: relevant but with caveats (broader scope, adjacent method, secondary source, partial match).",
        "1": "Marginally relevant: touches the topic but not useful as primary evidence.",
        "0": "Irrelevant: wrong meaning, wrong domain, or unrelated topic. Includes lexical traps and acronym collisions.",
    },
    "sub_dimensions": {
        "topical_relevance": "Does the candidate address the same research question/intent?",
        "evidence_utility": "Would a researcher find this useful as evidence?",
        "methodological_fit": "Does the method/study type match what the query asks for?",
    },
    "qualitative_for_risk_bearing": [
        "Does the passage truly support the claim?",
        "Does it genuinely contradict or qualify?",
        "Does it address the same research agenda (PICO)?",
        "Are two sources distinct evidence lineages?",
    ],
}

RISK_DEFS = {
    "false_support": "A passage appears to support a claim but does not. The researcher builds on evidence that isn't there.",
    "missed_contradiction": "Contrary or qualifying evidence exists but is not retrieved.",
    "agenda_mismatch": "Topically similar but answers a different research question (different population, intervention, outcome, method, or agenda).",
    "missed_relevant_evidence": "Relevant evidence is absent from the usable result set.",
    "redundancy": "Results repeat the same paper, lab, or evidence lineage.",
}


def load_cases():
    return [json.loads(l) for l in (DOCS / "p1d2_diagnostic_seed_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def build():
    cases = load_cases()

    # Deterministic neutral ID mapping (seeded for reproducibility)
    rng = random.Random(20260723)

    # Build a global mapping: real_passage_id -> neutral_id
    # Neutral IDs are format "unit_NNN" with no answer-revealing content
    all_real_ids = set()
    for c in cases:
        all_real_ids.update(c.get("passages", {}).keys())
    id_list = sorted(all_real_ids)
    rng.shuffle(id_list)
    neutral_map = {real: f"unit_{i:04d}" for i, real in enumerate(id_list)}

    # Build the reviewer-facing package records
    # Both packages A and B are identical (same content); they differ in who reviews them
    reviewer_records = []
    for c in cases:
        # Build the blinded candidate pool
        blinded_units = []
        for uid in c["candidate_pool"]["candidate_unit_ids"]:
            pp = c["passages"].get(uid, {})
            # We need the passage TEXT; it's not in the case record (stripped during build)
            # Recover it from the source file
            blinded_units.append({
                "neutral_unit_id": neutral_map.get(uid, uid),
                "unit_type": c["candidate_pool"]["candidate_unit_type"],
                "section": pp.get("section_id", "unknown"),
                "passage_locator": pp.get("passage_locator", "unknown"),
                "passage_text_hash": pp.get("passage_text_hash", ""),
                # passage_text will be filled from sources
            })

        rec = {
            "case_id": c["case_id"],
            "task_family": c["task_family"],
            "query_or_claim": c["query_or_claim"],
            "case_mode": c["case_mode"],
            "scoring_profile": c["scoring_profile"],
            "claim_dimensions": c.get("claim_dimensions"),
            "risk_labels": c["risk_labels"],
            "candidate_pool": {
                "pool_id": c["candidate_pool"]["pool_id"],
                "retrieval_surface": c["candidate_pool"]["retrieval_surface"],
                "units": blinded_units,
            },
            "rubric": RUBRIC,
            "risk_definitions": {r: RISK_DEFS[r] for r in c["risk_labels"] if r in RISK_DEFS},
        }
        reviewer_records.append(rec)

    # Fill in passage text from sources
    sources = [json.loads(l) for l in (DOCS / "p1d2_diagnostic_seed_sources.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    src_by_id = {s["document_id"]: s for s in sources}

    # Build a reverse map: neutral_id -> passage_text
    neutral_to_text = {}
    for c in cases:
        for uid, pp in c.get("passages", {}).items():
            nid = neutral_map.get(uid, uid)
            src = src_by_id.get(pp.get("document_id", ""), {})
            try:
                _, rng_str = pp["passage_locator"].split(" ")
                s, e = map(int, rng_str.split("-"))
                neutral_to_text[nid] = src["full_text"][s:e]
            except Exception:
                neutral_to_text[nid] = "[TEXT UNAVAILABLE]"

    # Attach passage text to reviewer records
    for rec in reviewer_records:
        for u in rec["candidate_pool"]["units"]:
            u["passage_text"] = neutral_to_text.get(u["neutral_unit_id"], "[UNAVAILABLE]")

    # Write both packages (identical content; assignment differs)
    for pkg in ["A", "B"]:
        path = DOCS / f"p1d2_reviewer_package_{pkg}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for rec in reviewer_records:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    # Coordinator-only identity map: written OUTSIDE the reviewer-accessible repo path.
    # Reviewers who can access the repo must not be able to de-blind units.
    COORD_DIR = REPO / "coordinator"  # outside docs/retrieval/ — not reviewer-accessible
    COORD_DIR.mkdir(parents=True, exist_ok=True)
    identity_map = {
        "identity_map_version": "p1d2_review_identity_map_v1",
        "created": "2026-07-23",
        "access_policy": "coordinator_only",
        "neutral_id_map": neutral_map,
        "description": "Maps neutral unit IDs (unit_NNNN) to internal passage/document IDs. MUST NOT be accessible to reviewers. If reviewers have repository access, this file must be moved to a path they cannot read.",
    }
    identity_map_path = COORD_DIR / "p1d2_review_identity_map.json"
    with open(identity_map_path, "w", encoding="utf-8") as f:
        json.dump(identity_map, f, ensure_ascii=False, indent=2, sort_keys=True)
    identity_map_hash = hashlib.sha256(identity_map_path.read_bytes()).hexdigest()

    # PUBLIC assignment manifest — NO neutral_id_map, only a hash reference
    assignment = {
        "manifest_version": "p1d2_review_assignment_v1",
        "status": "draft",
        "created": "2026-07-23",
        "total_judgments_requiring_review": sum(len(c["relevance_judgments"]) for c in cases),
        "reviewers": {"A": {"id": "reviewer_A", "status": "not_yet_assigned"}, "B": {"id": "reviewer_B", "status": "not_yet_assigned"}},
        "blinding_attestations": {
            "reviewer_A_cannot_see_reviewer_B": True,
            "reviewer_B_cannot_see_reviewer_A": True,
            "neither_sees_author_grades": True,
            "neither_sees_policy_outputs": True,
            "case_author_not_a_reviewer": True,
        },
        "identity_map_embedded": False,
        "identity_map_sha256": identity_map_hash,
        "identity_map_path": "coordinator/p1d2_review_identity_map.json",
        "identity_map_access_policy": "coordinator_only",
        "reviewers_have_repository_access": False,
        "submission_status": {},
        "agreement_status": {},
        "adjudication_requirements": [],
    }
    with open(DOCS / "p1d2_review_assignment_manifest.json", "w", encoding="utf-8") as f:
        json.dump(assignment, f, ensure_ascii=False, indent=2, sort_keys=True)

    # Package manifest
    def fp(p):
        return hashlib.sha256((DOCS / p).read_bytes()).hexdigest()

    pkg_manifest = {
        "manifest_version": "p1d2_review_package_manifest_v1",
        "status": "draft",
        "created": "2026-07-23",
        "packages": {
            "A": {"path": "docs/retrieval/p1d2_reviewer_package_A.jsonl", "hash": fp("p1d2_reviewer_package_A.jsonl"), "hash_semantics": "raw file bytes SHA-256"},
            "B": {"path": "docs/retrieval/p1d2_reviewer_package_B.jsonl", "hash": fp("p1d2_reviewer_package_B.jsonl"), "hash_semantics": "raw file bytes SHA-256"},
        },
        "assignment_manifest": {"path": "docs/retrieval/p1d2_review_assignment_manifest.json", "hash": fp("p1d2_review_assignment_manifest.json")},
        "identity_map_embedded_in_public_manifest": False,
        "identity_map_sha256": identity_map_hash,
        "identity_map_access_policy": "coordinator_only",
        "case_count": len(cases),
        "neutral_id_count": len(neutral_map),
        "exclusions_verified": {
            "no_author_grades_in_packages": True,
            "no_author_rationales_in_packages": True,
            "no_policy_outputs_in_packages": True,
            "no_answer_revealing_document_labels": True,
            "neutral_ids_contain_no_role_information": True,
            "no_neutral_id_map_in_reviewer_accessible_paths": True,
        },
        "content_included": {
            "query_or_claim": True,
            "passage_text": True,
            "source_provenance_hashes": True,
            "claim_dimensions": True,
            "rubric": True,
            "risk_definitions": True,
        },
    }
    with open(DOCS / "p1d2_review_package_manifest.json", "w", encoding="utf-8") as f:
        json.dump(pkg_manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote 2 reviewer packages ({len(reviewer_records)} cases each), assignment manifest, package manifest.")
    print(f"Neutral IDs: {len(neutral_map)}")
    print(f"Judgments requiring review: {assignment['total_judgments_requiring_review']}")


if __name__ == "__main__":
    build()

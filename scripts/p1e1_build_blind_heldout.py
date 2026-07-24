"""P1E.1 Commit 3 — Build the blind held-out package + custody receipt.

The blind package contains ONLY opaque IDs and candidate content (title +
abstract). It recursively excludes all judgment/provenance/mining/lineage
metadata. The reconciliation map (opaque-id -> v3-id mapping) is generated
under separate custody and NOT committed to the repository — only its
SHA-256 and custody receipt are recorded.
"""

from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v3_corpus import build_v3_corpus
from backend.ranking.p1e1_canon import canonical_json, canonical_json_hash, sha256_file

OUT_PKG = REPO_ROOT / "data" / "evaluation" / "p1e1_blind_heldout_package.json"
OUT_RECEIPT = REPO_ROOT / "data" / "evaluation" / "p1e1_reconciliation_map_custody_receipt.json"
# The map itself is written OUTSIDE the repo (separate custody) — only the
# receipt (hash + custodian) is committed.
MAP_EXTERNAL_PATH = REPO_ROOT.parent / "p1e1_reconciliation_map_SEPARATE_CUSTODY.json"

# Keys/values recursively prohibited in the blind package
FORBIDDEN_KEYS = {
    "split", "grade", "relevance", "judgment", "judgment_rationale",
    "judgment_rationale_text", "mining_score", "mining_method", "mining_rationale",
    "mining_role", "constructed_lexical_trap", "near_duplicate_of",
    "near_duplicate_declaration", "parent_v2_case_id", "parent_v2_candidate_id",
    "candidate_provenance", "v3_case_id", "v3_candidate_id",
    "lineage_type", "content_unchanged_from_parent", "source_rank",
    "query_generation_anchor_candidate_id", "primary_slice", "secondary_slices",
    "research_domain", "ranking_surface", "ranking_intent",
}


def _opaque_id() -> str:
    """128-bit opaque ID (32-char lowercase hex)."""
    return secrets.token_hex(16)


def _build_blind_package():
    cases = build_v3_corpus()
    held_out = [c for c in cases if c.split == "held_out"]
    assert len(held_out) == 22, f"expected 22 held-out, got {len(held_out)}"

    reconciliation_map = {}  # opaque_id -> v3_id; NOT committed
    blind_cases = []
    issued_ids = set()

    for case in held_out:
        # opaque case ID
        while True:
            ocid = _opaque_id()
            if ocid not in issued_ids:
                break
        issued_ids.add(ocid)
        reconciliation_map[ocid] = case.case_id

        blind_candidates = []
        for cc in case.candidates:
            while True:
                ocan = _opaque_id()
                if ocan not in issued_ids:
                    break
            issued_ids.add(ocan)
            reconciliation_map[ocan] = cc.candidate_id
            blind_candidates.append({
                "opaque_candidate_id": ocan,
                "title": cc.title,
                "abstract": cc.abstract,
            })
        blind_cases.append({
            "opaque_case_id": ocid,
            "query_text": case.query_text,
            "candidates": blind_candidates,
        })

    return blind_cases, reconciliation_map


def _recursive_leakage_check(obj, path="") -> list[str]:
    """Recursively find any forbidden key or v3-prefixed value."""
    leaks = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                leaks.append(f"{path}.{k}")
            if isinstance(v, str) and v.startswith("v3_"):
                leaks.append(f"{path}.{k}=v3-prefixed-value")
            leaks.extend(_recursive_leakage_check(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            leaks.extend(_recursive_leakage_check(x, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if obj.startswith("v3_"):
            leaks.append(f"{path}=v3-prefixed-value")
    return leaks


def main() -> int:
    # verify seals
    pkg = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_package.json").read_text())
    assert pkg["protocol_commit"] == "679bc0052d0851bef48ab87663166b7a08f85bd6"

    blind_cases, recon_map = _build_blind_package()

    # leakage check (recursive)
    leaks = _recursive_leakage_check(blind_cases)
    if leaks:
        raise SystemExit(f"FATAL: blind package leaks: {leaks[:10]}")

    blind_pkg = {
        "schema": "p1e1_blind_heldout_package_v1",
        "package_version": "blind_heldout_v1",
        "held_out_cases": len(blind_cases),
        "opaque_case_ids_unique": len({c["opaque_case_id"] for c in blind_cases}) == len(blind_cases),
        "opaque_candidate_ids_unique": len({cc["opaque_candidate_id"]
                                            for c in blind_cases for cc in c["candidates"]}) ==
                                       sum(len(c["candidates"]) for c in blind_cases),
        "minimum_id_entropy_bits": 128,
        "cases": blind_cases,
    }
    blind_pkg["blind_package_sha256"] = canonical_json_hash(blind_cases)

    # write blind package (committed)
    OUT_PKG.parent.mkdir(parents=True, exist_ok=True)
    OUT_PKG.write_text(canonical_json(blind_pkg) + "\n", encoding="utf-8")

    # write reconciliation map OUTSIDE the repo (separate custody)
    map_blob = canonical_json(recon_map).encode("utf-8")
    map_sha = canonical_json_hash(recon_map)
    MAP_EXTERNAL_PATH.write_bytes(map_blob)

    # custody receipt (committed; binds package to map without exposing the map)
    receipt = {
        "receipt_schema": "p1e1_reconciliation_custody_receipt_v1",
        "blind_package_sha256": blind_pkg["blind_package_sha256"],
        "reconciliation_map_sha256": map_sha,
        "mapping_entry_count": len(recon_map),
        "opaque_id_algorithm": "secrets.token_hex(16), 128-bit CSPRNG",
        "entropy_bits": 128,
        "generator_implementation": f"Python secrets module ({sys.version.split()[0]})",
        "custodian_role": "P1E.2 Reconciliation Custodian",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authorized_retrieval_procedure": "P1E.2 custodian presents receipt; map loaded from separate custody for reconciliation only; never delivered to adjudicator",
        "map_location": str(MAP_EXTERNAL_PATH) + " (OUTSIDE repository; separate custody)",
        "map_committed_to_repository": False,
        "regeneration_policy": "blind package + map immutable once sealed; regen requires a new blind-package version and new receipt",
    }
    OUT_RECEIPT.write_text(canonical_json(receipt) + "\n", encoding="utf-8")

    print(f"wrote {OUT_PKG}")
    print(f"  held-out cases: {len(blind_cases)}")
    print(f"  opaque case IDs unique: {blind_pkg['opaque_case_ids_unique']}")
    print(f"  opaque candidate IDs unique: {blind_pkg['opaque_candidate_ids_unique']}")
    print(f"  leakage findings: 0")
    print(f"  blind_package_sha256: {blind_pkg['blind_package_sha256']}")
    print(f"wrote {OUT_RECEIPT}")
    print(f"  reconciliation_map_sha256: {map_sha}")
    print(f"  mapping entries: {len(recon_map)}")
    print(f"  map committed to repository: False (separate custody)")
    print(f"wrote reconciliation map to {MAP_EXTERNAL_PATH} (OUTSIDE repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

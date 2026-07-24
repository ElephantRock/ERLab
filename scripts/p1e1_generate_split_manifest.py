"""P1E.1 — Generate the v3 split manifest.

The v3 corpus is built dynamically by `benchmark_v3_corpus.build_v3_corpus()`,
so (unlike P1E.0, which parsed raw source) the split mapping is read from the
constructed in-memory corpus. This is acceptable because the corpus is itself
frozen by its candidate_corpus_fingerprint; the manifest records the canonical
case->split mapping and is cross-checked against the constructed corpus at
generation time.

Output: data/evaluation/p1e1_split_manifest.json (schema p1e1_split_manifest_v1)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v3_corpus import build_v3_corpus
from backend.ranking.benchmark_v3_registry import V3_CANDIDATE_BENCHMARK_VERSION
from backend.ranking.p1e1_canon import canonical_json_hash, sha256_file

OUT = REPO_ROOT / "data" / "evaluation" / "p1e1_split_manifest.json"


def main() -> int:
    cases = build_v3_corpus()
    items = [{"v3_case_id": c.case_id, "split": c.split,
              "lineage_type": c.lineage_type,
              "parent_v2_case_id": c.parent_v2_case_id} for c in cases]
    items.sort(key=lambda x: x["v3_case_id"])

    # integrity invariants
    ids = [it["v3_case_id"] for it in items]
    assert len(ids) == len(set(ids)), "duplicate v3 case IDs"
    splits = Counter(it["split"] for it in items)
    assert splits == {"calibration": 33, "development": 33, "held_out": 22}, dict(splits)
    lineage = Counter(it["lineage_type"] for it in items)
    assert lineage == {"v2_extended": 44, "fully_new": 44}, dict(lineage)
    # 0 v2 held-out lineage
    v2_held = sum(1 for it in items if it["lineage_type"] == "v2_extended" and it["parent_v2_case_id"] is None)
    assert v2_held == 0

    manifest = {
        "schema": "p1e1_split_manifest_v1",
        "protocol_commit": "42ff0e6",
        "protocol_sha256": sha256_file(REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension_protocol_v2.md"),
        "protocol_version": "p1e1_protocol_v2",
        "allocation_table_sha256": "93aa5e62cd89f2e704db918078a63dfa2f0930af21f3da3d98b5044fda9e2b87",
        "parent_allowlist_sha256": "4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70",
        "benchmark_candidate_version": V3_CANDIDATE_BENCHMARK_VERSION,
        "total_cases": len(items),
        "split_counts": dict(splits),
        "lineage_counts": dict(lineage),
        "calibration_case_ids": sorted(it["v3_case_id"] for it in items if it["split"] == "calibration"),
        "development_case_ids": sorted(it["v3_case_id"] for it in items if it["split"] == "development"),
        "held_out_case_ids": sorted(it["v3_case_id"] for it in items if it["split"] == "held_out"),
        "items": items,
        "split_manifest_sha256": canonical_json_hash(items),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    from backend.ranking.p1e1_canon import canonical_json
    OUT.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  total={manifest['total_cases']} splits={manifest['split_counts']} lineage={manifest['lineage_counts']}")
    print(f"  split_manifest_sha256={manifest['split_manifest_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

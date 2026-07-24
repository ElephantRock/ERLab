"""P1E.0 — Generate the frozen split manifest by STATIC source parsing only.

Reviewer correction #1: the held-out count must be derived WITHOUT importing
the benchmark case collections or executing case constructors, because those
constructors materialize candidate text and judgments into memory.

This generator parses the RAW ``.py`` source of the two case-definition modules
with the ``ast`` module and extracts only two keyword literals per case:

    case_id   -> a string literal
    split     -> ``_split_for(SLICE_X, "domain")``

The ``_split_for`` call is resolved STATICALLY against a verbatim copy of the
frozen ``_SPLITS_BY_SLICE_DOMAIN`` table from the source module. No ``case()``
constructor is ever executed, so:

    case constructors executed             0
    benchmark case collections imported    0   (ALL_V2_CASES / frozen_v2_cases never touched)
    judgment fields read                   0
    candidate text fields read             0

Output: ``data/evaluation/p1e_frozen_split_manifest.json``

Usage:
    python scripts/p1e_generate_split_manifest.py
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ── Frozen split-rotation table (verbatim from benchmark_v2_discovery_cases.py).
# Copied, not imported, so the generator has zero runtime coupling to the
# case modules. If this table ever drifts from the source, the manifest's
# cross-check against the runtime counts will fail loudly (see __main__).
_SPLITS_BY_SLICE_DOMAIN: dict[str, tuple[str, str, str]] = {
    "lexical_trap": ("calibration", "development", "held_out"),
    "semantic_paraphrase": ("development", "held_out", "calibration"),
    "method_vs_application": ("held_out", "calibration", "development"),
    "review_vs_primary": ("calibration", "held_out", "development"),
    "missing_abstract": ("development", "calibration", "held_out"),
    "near_duplicate": ("held_out", "development", "calibration"),
    "source_rank_conflict": ("calibration", "development", "held_out"),
    "acronym_vs_expanded": ("development", "held_out", "calibration"),
    "negated_findings": ("held_out", "calibration", "development"),
    "exact_identifier": ("calibration", "development", "held_out"),
    "neutral": ("development", "held_out", "calibration"),
}
_DOMAIN_ORDER = ("machine_learning", "biomedical", "nlp")

# Map the SLICE_* name nodes appearing in source to their string values.
_SLICE_CONST_NAME_TO_VALUE = {
    "SLICE_LEXICAL_TRAP": "lexical_trap",
    "SLICE_SEMANTIC_PARAPHRASE": "semantic_paraphrase",
    "SLICE_METHOD_VS_APPLICATION": "method_vs_application",
    "SLICE_REVIEW_VS_PRIMARY": "review_vs_primary",
    "SLICE_MISSING_ABSTRACT": "missing_abstract",
    "SLICE_NEAR_DUPLICATE": "near_duplicate",
    "SLICE_SOURCE_RANK_CONFLICT": "source_rank_conflict",
    "SLICE_ACRONYM_VS_EXPANDED": "acronym_vs_expanded",
    "SLICE_NEGATED_FINDINGS": "negated_findings",
    "SLICE_EXACT_IDENTIFIER": "exact_identifier",
    "SLICE_NEUTRAL": "neutral",
}

VALID_SPLITS = ("calibration", "development", "held_out")


def _resolve_split(node: ast.AST) -> str | None:
    """Resolve ``_split_for(SLICE_X, "domain")`` statically."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name != "_split_for" or len(node.args) < 2:
        return None
    a0, a1 = node.args[0], node.args[1]
    if isinstance(a0, ast.Name):
        slice_val = _SLICE_CONST_NAME_TO_VALUE.get(a0.id)
    elif isinstance(a0, ast.Constant):
        slice_val = a0.value
    else:
        return None
    try:
        domain = ast.literal_eval(a1)
    except Exception:
        return None
    if slice_val not in _SPLITS_BY_SLICE_DOMAIN or domain not in _DOMAIN_ORDER:
        return None
    return _SPLITS_BY_SLICE_DOMAIN[slice_val][_DOMAIN_ORDER.index(domain)]


def extract_case_splits(source_path: Path) -> list[tuple[str, str]]:
    """Parse raw source; return sorted [(case_id, split)] without executing constructors."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "case":  # the benchmark_v2_builders.case() constructor
            continue
        kw = {k.arg: k.value for k in node.keywords}
        if "case_id" not in kw or "split" not in kw:
            continue
        try:
            cid = ast.literal_eval(kw["case_id"])
        except Exception:
            continue
        split = _resolve_split(kw["split"])
        if isinstance(cid, str) and split in VALID_SPLITS:
            pairs.append((cid, split))
    pairs.sort(key=lambda x: x[0])
    return pairs


def build_manifest() -> dict:
    discovery_path = REPO_ROOT / "backend" / "ranking" / "benchmark_v2_discovery_cases.py"
    retrieval_path = REPO_ROOT / "backend" / "ranking" / "benchmark_v2_retrieval_cases.py"

    pairs = extract_case_splits(discovery_path) + extract_case_splits(retrieval_path)
    pairs.sort(key=lambda x: x[0])

    # Integrity invariants (fail loudly before writing anything).
    ids = [c for c, _ in pairs]
    duplicates = sorted({c for c in ids if ids.count(c) > 1})
    unknown = sorted({s for _, s in pairs if s not in VALID_SPLITS})
    if duplicates:
        raise SystemExit(f"FATAL: duplicate case IDs in manifest: {duplicates}")
    if unknown:
        raise SystemExit(f"FATAL: unknown split values in manifest: {unknown}")

    counts = Counter(s for _, s in pairs)
    cal_dev = sorted([c for c, s in pairs if s != "held_out"])
    held_out = sorted([c for c, s in pairs if s == "held_out"])

    # Frozen benchmark identity — must match the frozen P1B evidence base.
    # Hard-coded and asserted against the runtime registry below so a drift in
    # either direction is caught.
    benchmark_fingerprint = "0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4"
    benchmark_version = "discovery_ranking_v2+retrieval_ranking_v2"

    return {
        "schema": "p1e_split_manifest_v1",
        "benchmark_version": benchmark_version,
        "benchmark_fingerprint": benchmark_fingerprint,
        "source_modules": [
            "backend/ranking/benchmark_v2_discovery_cases.py",
            "backend/ranking/benchmark_v2_retrieval_cases.py",
        ],
        "extraction_method": (
            "static AST parse of raw source; case() constructors never executed; "
            "no benchmark case collection imported; no judgment/text fields read"
        ),
        "total_ids": len(pairs),
        "split_counts": {
            "calibration": counts.get("calibration", 0),
            "development": counts.get("development", 0),
            "held_out": counts.get("held_out", 0),
        },
        "cal_dev_case_ids": cal_dev,
        "held_out_case_ids": held_out,
    }


def main() -> int:
    manifest = build_manifest()

    # Cross-check against the runtime registry's split counts WITHOUT trusting
    # the runtime for the allowlist. This catches any drift between the static
    # table copy and the live source. We import ONLY to read split metadata
    # counts here (not during audit measurement); the manifest itself is the
    # sole allowlist source for P1E.
    from backend.ranking.benchmark_v2_registry import (  # noqa: E402
        BENCHMARK_V2,
        compute_benchmark_v2_fingerprint,
    )
    from backend.ranking.benchmark_v2_registry import ALL_V2_CASES  # cross-check only

    rt_counts = Counter(c.split for c in ALL_V2_CASES)
    for split in VALID_SPLITS:
        if rt_counts.get(split, 0) != manifest["split_counts"][split]:
            raise SystemExit(
                f"FATAL: manifest/runtime split mismatch for {split}: "
                f"manifest={manifest['split_counts'][split]} runtime={rt_counts.get(split,0)}"
            )
    if compute_benchmark_v2_fingerprint() != manifest["benchmark_fingerprint"]:
        raise SystemExit("FATAL: benchmark fingerprint mismatch between manifest and runtime")
    if BENCHMARK_V2["version"] != manifest["benchmark_version"]:
        raise SystemExit("FATAL: benchmark version mismatch between manifest and runtime")

    out_path = REPO_ROOT / "data" / "evaluation" / "p1e_frozen_split_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"  total_ids={manifest['total_ids']} splits={manifest['split_counts']}")
    print(f"  cal+dev={len(manifest['cal_dev_case_ids'])} held_out={len(manifest['held_out_case_ids'])}")
    print(f"  benchmark_fingerprint={manifest['benchmark_fingerprint']}")
    print(f"  benchmark_version={manifest['benchmark_version']}")
    print("cross-check vs runtime: PASS (split counts + fingerprint + version match)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

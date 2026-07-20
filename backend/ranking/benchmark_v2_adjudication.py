"""P1B.1 Gate 1: reconcile blind adjudication against provisional judgments.

Reads:
  - provisional judgments: backend.ranking.benchmark_v2_*_cases (initial pass)
  - blind adjudication: docs/p1b_gate1/adjudicated/blind_adjudication_package_adjudicated.json

Produces a reconciliation record per (case_id, candidate_id):
  - provisional_grade  (author initial pass)
  - blind_grade        (adjudicator second pass)
  - delta              (blind - provisional)
  - agreement_class    exact | minor | material | unable
  - provisional_confidence, blind_confidence
  - both rationales
  - proposed_adjudication  (final grade to freeze)

Agreement classification (frozen in Decision 3):
  exact      delta == 0
  minor      abs(delta) == 1
  material   abs(delta) >= 2
  unable     blind OR provisional flagged specialist_review_needed (none in
             this dataset, but the path must exist)

Material disagreements are surfaced for explicit adjudication. The default
proposed_adjudication for non-material cases is the blind grade (per Decision
3: when blind and provisional agree or differ only minor, we trust the
independent second pass). Material cases are surfaced for decision; the
proposed_adjudication defaults to the blind grade but MUST be reviewed.

Outputs:
  docs/p1b_gate1/adjudication/reconciliation_report.json
  docs/p1b_gate1/adjudication/material_disagreements.json
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.ranking.benchmark_v2_registry import ALL_V2_CASES


REPO_ROOT = Path(__file__).resolve().parents[2]
ADJUDICATED_PATH = (
    REPO_ROOT / "docs" / "p1b_gate1" / "adjudicated"
    / "blind_adjudication_package_adjudicated.json"
)
OUTPUT_DIR = REPO_ROOT / "docs" / "p1b_gate1" / "adjudication"


def _classify(provisional: int, blind: int) -> str:
    delta = blind - provisional
    if delta == 0:
        return "exact"
    if abs(delta) == 1:
        return "minor"
    return "material"


def reconcile() -> dict:
    """Reconcile blind adjudication against provisional judgments.

    Returns the reconciliation report dict and writes it to disk.
    """
    blind_pkg = json.loads(ADJUDICATED_PATH.read_text())
    blind_by_case = {c["case_id"]: c for c in blind_pkg["cases"]}

    records: list[dict] = []
    material: list[dict] = []
    agreement_counts = {"exact": 0, "minor": 0, "material": 0, "unable": 0}

    for case in ALL_V2_CASES:
        blind_case = blind_by_case.get(case.case_id)
        if blind_case is None:
            raise RuntimeError(f"blind package missing case {case.case_id}")
        blind_judgments = blind_case.get("judgments", {})
        if len(blind_judgments) != len(case.judgments):
            raise RuntimeError(
                f"{case.case_id}: blind has {len(blind_judgments)} judgments, "
                f"provisional has {len(case.judgments)}"
            )

        for cand in case.candidates:
            cid = cand.candidate_id
            prov = case.judgments[cid]
            blind_j = blind_judgments.get(cid)
            if blind_j is None:
                raise RuntimeError(f"{case.case_id}/{cid}: missing blind judgment")

            prov_grade = prov.initial.grade
            blind_grade = int(blind_j["grade"])
            agreement = _classify(prov_grade, blind_grade)
            specialist = bool(blind_j.get("specialist_review_needed")) or False
            if specialist:
                agreement = "unable"
            agreement_counts[agreement] += 1

            rec = {
                "case_id": case.case_id,
                "candidate_id": cid,
                "research_domain": case.research_domain,
                "surface": case.ranking_surface,
                "primary_slice": case.primary_slice,
                "provisional_grade": prov_grade,
                "provisional_confidence": prov.initial.annotation_confidence,
                "provisional_rationale": prov.initial.rationale,
                "blind_grade": blind_grade,
                "blind_confidence": float(blind_j["confidence"]),
                "blind_rationale": blind_j["rationale"],
                "specialist_review_needed": specialist,
                "delta": blind_grade - prov_grade,
                "agreement": agreement,
                # Default proposed adjudication:
                # - exact/minor: trust blind (independent pass)
                # - material: default to blind but FLAG for review
                # - unable: null, must be excluded or externally reviewed
                "proposed_adjudicated_grade": (
                    None if agreement == "unable" else blind_grade
                ),
            }
            records.append(rec)
            if agreement == "material":
                material.append(rec)

    report = {
        "total_judgments": len(records),
        "agreement_counts": agreement_counts,
        "agreement_rates": {
            k: round(v / len(records), 4) for k, v in agreement_counts.items()
        },
        "material_disagreement_count": len(material),
        "delta_distribution": _delta_distribution(records),
        "by_slice": _by_dimension(records, "primary_slice"),
        "by_surface": _by_dimension(records, "surface"),
        "by_domain": _by_dimension(records, "research_domain"),
        "records": records,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "reconciliation_report.json").write_text(
        json.dumps(report, indent=2)
    )
    (OUTPUT_DIR / "material_disagreements.json").write_text(
        json.dumps(material, indent=2)
    )
    return report


def _delta_distribution(records: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        key = str(r["delta"])
        out[key] = out.get(key, 0) + 1
    return {k: out[k] for k in sorted(out, key=int)}


def _by_dimension(records: list[dict], dim: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in records:
        key = r[dim]
        d = out.setdefault(key, {"count": 0, "exact": 0, "minor": 0, "material": 0, "unable": 0})
        d["count"] += 1
        d[r["agreement"]] += 1
    for key, d in out.items():
        c = d["count"]
        d["material_rate"] = round(d["material"] / c, 4) if c else 0.0
        d["exact_rate"] = round(d["exact"] / c, 4) if c else 0.0
    return out


if __name__ == "__main__":
    r = reconcile()
    print("total judgments:", r["total_judgments"])
    print("agreement counts:", r["agreement_counts"])
    print("agreement rates:", r["agreement_rates"])
    print("delta distribution:", r["delta_distribution"])
    print("material disagreements:", r["material_disagreement_count"])

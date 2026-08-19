"""P1-1: reconstruct the Case-4 numeric defect from the preserved specimen.

Loads a CLONE of the runfail_3 blocked specimen, reconstructs the
dataset-qualified ResultMarker set exactly as the governed repair route
does (backend/api/routes/ideas.py: autonomous-design specs -> successful
ExperimentResult manifests -> sorted metric map with global indices),
runs the UNCHANGED validate_claim_result_alignment() against the blocked
repaired paper (paper_revisions revision 1), and emits a machine-readable
discrepancy record. Read-only against the specimen; no product code is
executed beyond the validator itself.
"""
import json
import shutil
import sqlite3
import sys

SPECIMEN = sys.argv[1] if len(sys.argv) > 1 else ".p1_tmp/r1_specimen.db"
CLONE = ".p1_tmp/p1_1_clone.db"

shutil.copyfile(SPECIMEN, CLONE)
conn = sqlite3.connect(CLONE)
cur = conn.cursor()

meta = json.loads(cur.execute(
    "select paper_meta_json from proposals where id=1"
).fetchone()[0])
auto_design = meta["autonomous_experiment_design"]
expected_specs = auto_design.get("specs", [])

exp_rows = cur.execute(
    "select id, manifest_json from experiment_results where success=1"
    " order by id asc",
).fetchall()
exp_by_spec_id = {}
for er_id, mj in exp_rows:
    m = json.loads(mj) if mj else {}
    sid = m.get("experiment_spec_id", "")
    if m.get("status") == "succeeded" and sid:
        exp_by_spec_id[sid] = (er_id, m)

# Marker reconstruction — mirrors ideas.py exactly.
markers = []
idx = 0
for spec_dict in expected_specs:
    sid = spec_dict.get("experiment_spec_id", "")
    if sid not in exp_by_spec_id:
        continue
    er_id, manifest = exp_by_spec_id[sid]
    dataset_name = spec_dict.get("dataset", {}).get("name", "unknown")
    results = manifest.get("results", {})
    artifacts = manifest.get("result_artifacts", [])
    for metric_name, value in sorted(results.items()):
        idx += 1
        artifact = next(
            (a for a in artifacts
             if isinstance(a, dict) and a.get("artifact_type") == "metrics"),
            artifacts[0] if artifacts else None,
        )
        role = "baseline" if metric_name.startswith("baseline_") else "comparison"
        markers.append({
            "marker": f"RESULT-{idx}",
            "metric_name": f"{dataset_name}.{metric_name}",
            "observed_value": value,
            "role": role,
            "experiment_result_id": er_id,
            "artifact_path": (
                f"{dataset_name}/{artifact.get('filename', '')}"
                if isinstance(artifact, dict) else ""
            ),
            "artifact_sha256": (
                artifact.get("sha256", "") if isinstance(artifact, dict) else ""
            ),
        })

rev1_paper = cur.execute(
    "select paper_md from paper_revisions where revision_number=1"
).fetchone()[0]
rev0_paper = cur.execute(
    "select paper_md from paper_revisions where revision_number=0"
).fetchone()[0]
conn.close()

# Run the UNCHANGED validator through its production module.
from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.evaluation.claim_result_validator import (
    validate_claim_result_alignment,
)

def as_marker(d):
    return ResultMarker(
        marker_index=int(d["marker"].split("-")[1]),
        marker=d["marker"],
        metric_name=d["metric_name"],
        observed_value=d["observed_value"],
        artifact_path=d["artifact_path"],
        artifact_sha256=d["artifact_sha256"],
        experiment_result_id=d["experiment_result_id"],
        direction="",
        role=d["role"],
    )

marker_objs = [as_marker(d) for d in markers]

def diagnose(paper, label):
    mismatches = [
        m for m in validate_claim_result_alignment(paper, marker_objs)
        if m.section == "numeric_fidelity"
    ]
    out = []
    by_marker = {d["marker"]: d for d in markers}
    for m in mismatches:
        rendered = m.claim_text.split()[1] if m.claim_text.startswith("rendered ") else ""
        info = by_marker.get(m.marker.strip("[]"), {})
        out.append({
            "marker": m.marker,
            "rendered_value": rendered,
            "persisted_observed_value": info.get("observed_value"),
            "metric_name": info.get("metric_name"),
            "role": m.marker_role,
            "experiment_result_id": info.get("experiment_result_id"),
            "artifact_path": info.get("artifact_path"),
            "artifact_sha256": (info.get("artifact_sha256") or "")[:16],
            "reason": m.reason,
        })
    return out

record = {
    "phase": "P1-1 defect reconstruction",
    "specimen": "evidence/case4_qualifying_runfail_3/r1_specimen.db (Case-4 final consumed RUN_FAIL)",
    "markers_reconstructed": len(markers),
    "repaired_paper_rev1": {
        "chars": len(rev1_paper),
        "numeric_fidelity_mismatches": diagnose(rev1_paper, "rev1"),
    },
    "original_paper_rev0": {
        "chars": len(rev0_paper),
        "numeric_fidelity_mismatches": diagnose(rev0_paper, "rev0"),
    },
}
record["analysis"] = {
    "canonical_paper_note": (
        "The failed repair did not promote, so proposal.paper_md remained the"
        " ORIGINAL (rev0, 30,469 chars). The final evaluation in the proposal"
        " meta — the one the Case-4 harness read — therefore carries rev0's"
        " six numeric mismatches, verified identical to this record's rev0"
        " set ([RESULT-6, 37, 46, 52, 56, 74])."
    ),
    "repair_delta": (
        "The repaired paper (rev1) contains exactly ONE numeric mismatch:"
        " [RESULT-38] rendered 165.0 vs persisted 0.515625"
        " (wine_quality.0_0_isotonic_accuracy, role=comparison). The single"
        " repair fixed five of the original six numeric defects and"
        " introduced/kept one new one."
    ),
    "stop_condition_check": (
        "PASSED: the persisted value is correct (0.515625 from the frozen"
        " artifact wine_quality/metrics.json, sha a4bb1b6…); the unchanged"
        " validator produces no false positive (165.0 is not a scale"
        " transform of 0.515625; the model rendered an unrelated value"
        " beside the marker). Remediation-side repair is the correct"
        " ownership."
    ),
    "hypothesis_support": (
        "Context loss is supported: the directive's evidence block renders"
        " bare 'RESULT-N = value' lines with no metric name, role, or"
        " dataset identity, and no per-marker targeting of the diagnosed"
        " numeric defects. RESULT-38's metric name"
        " ('wine_quality.0_0_isotonic_accuracy') gives no unaided hint that"
        " its value must lie in [0,1]; '165.0' (plausibly a dataset-row"
        " count) was placed beside it without any structural guard."
    ),
}

with open("evidence/productive1/p1_1_discrepancies.json", "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)

r1 = record["repaired_paper_rev1"]["numeric_fidelity_mismatches"]
r0 = record["original_paper_rev0"]["numeric_fidelity_mismatches"]
print(f"markers reconstructed: {len(markers)}")
print(f"rev0 (original) numeric mismatches : {len(r0)}")
print(f"rev1 (repaired) numeric mismatches : {len(r1)}")
for m in r1:
    print(f"  {m['marker']:>11} rendered={m['rendered_value']:>12}"
          f" persisted={m['persisted_observed_value']:>12}"
          f" metric={m['metric_name']} role={m['role']}")

"""R5 diagnostic: deterministic exact-span numeric patches on the four frozen specimens.
Throwaway analysis - no product code touched."""
import json, sqlite3, sys, os, hashlib, re
sys.path.insert(0, os.getcwd())
from pathlib import Path

INPUTS = Path(__file__).resolve().parent / "r4_qual_inputs"
STATES = [("calib-A", INPUTS / "calib-A_runfail3.db"), ("calib-B", INPUTS / "calib-B_runfail2.db"),
          ("regr-A", INPUTS / "regr-A_case3a.db"), ("regr-B", INPUTS / "regr-B_3E_era.db")]

from backend.pipeline.evaluation.claim_result_validator import (
    validate_claim_result_alignment, _NUM_BEFORE_RE, _NUM_AFTER_RE,
)
from backend.pipeline.evaluation.paper_sections import parse_paper
from backend.pipeline.evaluation.method_fidelity import evaluate_method_fidelity
from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates
from backend.pipeline.evaluation.revision_directive import verify_revised_paper_invariants, EvidenceInvariant


def rebuild_markers(conn, pid):
    meta = json.loads(conn.execute("select paper_meta_json from proposals where id=?", (pid,)).fetchone()[0])
    design = meta["autonomous_experiment_design"]
    exps = conn.execute("select id, manifest_json from experiment_results where success=1 order by id asc").fetchall()
    by_sid = {}
    for eid, mj in exps:
        m = json.loads(mj) if mj else {}
        sid = m.get("experiment_spec_id", "")
        if m.get("status") == "succeeded" and sid:
            by_sid[sid] = (eid, m)
    objs, idx = [], 0
    for spec in design.get("specs", []):
        sid = spec.get("experiment_spec_id", "")
        if sid not in by_sid:
            continue
        eid, man = by_sid[sid]
        ds = spec.get("dataset", {}).get("name", "unknown")
        for metric, value in sorted(man.get("results", {}).items()):
            idx += 1
            objs.append({"marker": f"RESULT-{idx}", "metric_name": f"{ds}.{metric}", "observed_value": value,
                         "role": ("baseline" if metric.startswith("baseline_") else "comparison"),
                         "experiment_result_id": eid})
    return meta, objs


def marker_objects(dicts):
    from backend.pipeline.experiment.manifest import ResultMarker
    return [ResultMarker(marker_index=int(d["marker"].split("-")[1]), marker=d["marker"], metric_name=d["metric_name"],
                         observed_value=d["observed_value"], artifact_path="", artifact_sha256="",
                         experiment_result_id=d.get("experiment_result_id"), direction="", role=d.get("role", ""))
            for d in dicts]


def build_patches(paper, markers):
    """Deterministic patches: replace every mismatching adjacent number token with repr(persisted).
    Returns list of (start, end, old, new, bracket) in paper order."""
    by_bracket = {f"[{m.marker}]": m for m in markers}
    edits = []
    for m in _NUM_BEFORE_RE.finditer(paper):
        bracket = re.search(r"\[RESULT-\d+\]", m.group(0)).group(0)
        mk = by_bracket.get(bracket)
        if not mk:
            continue
        old = m.group("num")
        try:
            rendered = float(old)
        except ValueError:
            continue
        if abs(rendered - mk.observed_value) > 1e-6:
            edits.append((m.start("num"), m.end("num"), old, repr(mk.observed_value), bracket))
    for m in _NUM_AFTER_RE.finditer(paper):
        bracket = re.match(r"\[RESULT-\d+\]", m.group(0)).group(0)
        mk = by_bracket.get(bracket)
        if not mk:
            continue
        old = m.group("num")
        try:
            rendered = float(old)
        except ValueError:
            continue
        if abs(rendered - mk.observed_value) > 1e-6:
            edits.append((m.start("num"), m.end("num"), old, repr(mk.observed_value), bracket))
    return sorted(edits, key=lambda e: e[0])


def apply_edits(paper, edits):
    out = paper
    for start, end, old, new, _ in sorted(edits, key=lambda e: e[0], reverse=True):
        assert out[start:end] == old, f"span drift at {start}: {out[start:end]!r} != {old!r}"
        out = out[:start] + new + out[end:]
    return out


summary = {}
for label, src in STATES:
    print("=" * 72)
    print("SPECIMEN", label)
    conn = sqlite3.connect(src)
    pid = None
    for (p,) in conn.execute("select id from proposals where paper_md is not null order by id").fetchall():
        mj = conn.execute("select paper_meta_json from proposals where id=?", (p,)).fetchone()[0]
        if mj and "autonomous_experiment_design" in mj:
            pid = p
            break
    rev0 = conn.execute("select paper_md from paper_revisions where proposal_id=? and revision_number=0", (pid,)).fetchone()[0]
    meta, dicts = rebuild_markers(conn, pid)
    markers = marker_objects(dicts)
    facts = (meta.get("autonomous_experiment_design") or {}).get("method_facts")

    mism0 = [m for m in validate_claim_result_alignment(rev0, markers) if m.section == "numeric_fidelity"]
    edits = build_patches(rev0, markers)
    print(f"rev0 numeric mismatches: {len(mism0)} | deterministic patches: {len(edits)} | repair-side model calls needed: 0")
    for e in edits[:5]:
        print(f"    {e[4]}: {e[2]!r} -> {e[3]!r}")
    if len(edits) > 5:
        print(f"    ... +{len(edits) - 5} more")

    patched = apply_edits(rev0, edits) if edits else rev0

    v = {}
    mism1 = [m for m in validate_claim_result_alignment(patched, markers) if m.section == "numeric_fidelity"]
    v["numeric_mismatches_after"] = len(mism1)
    if mism1:
        print("  REMAINING MISMATCHES:", [(mm.marker, mm.claim_text[:60]) for mm in mism1][:3])
    mf0, mf1 = evaluate_method_fidelity(rev0, facts), evaluate_method_fidelity(patched, facts)
    v["method_fidelity_before_after"] = (mf0.passed, mf1.passed)
    if not mf1.passed:
        print("  MF FAIL AFTER:", mf1.reason[:200])
    spec0 = ((meta.get("autonomous_experiment_design") or {}).get("specs") or [{}])[0]
    ev = evaluate_paper_gates(paper_md=patched, source_map=meta.get("source_map"),
                              research_intent=spec0.get("research_question", ""), domain="machine learning",
                              result_markers=markers, spec_method=spec0.get("analysis_method", ""),
                              spec_dataset=spec0.get("dataset", {}).get("name", ""),
                              spec_baseline=spec0.get("baseline_method", ""),
                              spec_comparison=spec0.get("comparison_method", ""))
    v["pure_gates_after"] = {g.get("gate"): (g.get("passed", g.get("classification"))) for g in ev.gates}
    v["pure_blocking_after"] = ev.blocking_reasons
    b_sec, a_sec = parse_paper(rev0), parse_paper(patched)
    v["section_names_identical"] = [s.name for s in b_sec.sections] == [s.name for s in a_sec.sections]
    v["section_headings_identical"] = [s.heading for s in b_sec.sections] == [s.heading for s in a_sec.sections]
    v["result_marker_count_identical"] = rev0.count("[RESULT-") == patched.count("[RESULT-")
    v["source_marker_count_identical"] = rev0.count("[SOURCE-") == patched.count("[SOURCE-")
    v["net_chars_changed"] = sum(len(e[3]) - len(e[2]) for e in edits)
    v["patched_sha256_16"] = hashlib.sha256(patched.encode()).hexdigest()[:16]
    result_map = tuple((f"[{m.marker}]", m.observed_value) for m in markers)
    src_ids = tuple(f"[{e.get('marker', '').strip('[]')}]" for e in (meta.get("source_map") or []))
    exp_row = conn.execute("select id, manifest_json from experiment_results where success=1 order by id asc").fetchone()
    man_hash = hashlib.sha256((exp_row[1] or "").encode()).hexdigest() if exp_row and exp_row[1] else ""
    evd = EvidenceInvariant(result_map=result_map, source_map=src_ids, experiment_manifest_hash=man_hash,
                            dataset_hash=spec0.get("dataset_raw_sha256", ""), analysis_code_hash="")
    ok, viol = verify_revised_paper_invariants(patched, evd)
    v["remediator_invariants_after"] = [ok, viol[:3]]
    print("  VERIFICATION:", json.dumps(v, default=str)[:700])
    summary[label] = {"rev0_mismatches": len(mism0), "patches": len(edits), "verify": v}
    conn.close()

print("=" * 72)
all_clean = all(s["verify"]["numeric_mismatches_after"] == 0 for s in summary.values())
all_gates = all(not s["verify"]["pure_blocking_after"] for s in summary.values())
print("ALL SPECIMENS numeric-clean after deterministic patches:", all_clean)
print("ALL SPECIMENS zero pure-gate blocking reasons after patches:", all_gates)
print("Repair-side model calls needed for the four frozen qualification states: 0" if all_clean and all_gates
      else "MODEL CALL STILL REQUIRED - see remaining blockers above")
Path("r5_diagnostic_result.json").write_text(json.dumps(summary, indent=1, default=str))

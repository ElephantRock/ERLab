"""R6 diagnostic: deterministic conclusion-support repair on the preserved regr-B
trial databases. Throwaway analysis — no product code touched."""
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Next-Era\Elephant-Rock-Research-Lab")
TRIALS = Path(__file__).resolve().parent / "r5v2_artifact/evidence/productive1_r5/trials"

from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates
from backend.pipeline.evaluation.method_fidelity import evaluate_method_fidelity

AUTH_PATTERNS = [
    (r"\bwe\s+demonstrate\b", "we demonstrate"),
    (r"\bdemonstrates?\s+that\b", "demonstrates that"),
    (r"\bexperimental\s+results?\b.{0,40}\b(show|indicate)\b", "experimental results show"),
    (r"\bresults?\s+(show|indicate)\s+that\b", "results show that"),
]
RESULT_RE = re.compile(r"\[RESULT-(\d+)\]")


def stage_abstract_conclusion(paper_md: str):
    """Verbatim reproduction of stages._classify_conclusion extraction:
    full-section line scanning; conclusion includes 'discussion'."""
    abstract = ""
    conclusion = ""
    if paper_md:
        lines = paper_md.splitlines()
        abs_lines, in_section = [], False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "abstract" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                abs_lines.append(s)
        abstract = " ".join(abs_lines)
        conc_lines, in_section = [], False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "conclusion" in low or "discussion" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                conc_lines.append(s)
        conclusion = " ".join(conc_lines)
    return abstract, conclusion


def authoritative_unmapped_claims(paper_md: str):
    """Faithful reproduction of the stages.py scan (stage extraction, ±200)."""
    abstract, conclusion = stage_abstract_conclusion(paper_md)
    text = f"{abstract}\n{conclusion}"
    unmapped, mapped = [], []
    for pattern, label in AUTH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            context = text[start:end]
            entry = (label, text[max(0, m.start() - 60):m.end() + 140].replace("\n", " "))
            if not RESULT_RE.search(context):
                unmapped.append(entry)
            else:
                mapped.append(entry)
    return unmapped, mapped, len(abstract), len(conclusion)


def rebuild_markers(conn, pid):
    meta = json.loads(conn.execute("select paper_meta_json from proposals where id=?", (pid,)).fetchone()[0])
    design = meta["autonomous_experiment_design"]
    by_sid = {}
    for eid, mj in conn.execute("select id, manifest_json from experiment_results where success=1 order by id asc").fetchall():
        m = json.loads(mj) if mj else {}
        sid = m.get("experiment_spec_id", "")
        if m.get("status") == "succeeded" and sid:
            by_sid[sid] = (eid, m)
    from backend.pipeline.experiment.manifest import ResultMarker
    objs, idx = [], 0
    for spec in design.get("specs", []):
        sid = spec.get("experiment_spec_id", "")
        if sid not in by_sid:
            continue
        eid, man = by_sid[sid]
        ds = spec.get("dataset", {}).get("name", "unknown")
        for metric, value in sorted(man.get("results", {}).items()):
            idx += 1
            objs.append(ResultMarker(marker_index=idx, marker=f"RESULT-{idx}", metric_name=f"{ds}.{metric}",
                observed_value=value, artifact_path="", artifact_sha256="", experiment_result_id=eid,
                direction="", role="baseline" if metric.startswith("baseline_") else "comparison"))
    return meta, objs


def gate_battery(paper_md, meta, markers, spec0):
    ev = evaluate_paper_gates(paper_md=paper_md, source_map=meta.get("source_map"),
        research_intent=spec0.get("research_question", ""), domain="machine learning",
        result_markers=markers, spec_method=spec0.get("analysis_method", ""),
        spec_dataset=spec0.get("dataset", {}).get("name", ""),
        spec_baseline=spec0.get("baseline_method", ""),
        spec_comparison=spec0.get("comparison_method", ""))
    facts = (meta.get("autonomous_experiment_design") or {}).get("method_facts")
    mf = evaluate_method_fidelity(paper_md, facts) if facts else None
    return ev, mf


def load_trial(name):
    conn = sqlite3.connect(TRIALS / name / "trial.db")
    pid = None
    for (p,) in conn.execute("select id from proposals where paper_md is not null order by id").fetchall():
        mj = conn.execute("select paper_meta_json from proposals where id=?", (p,)).fetchone()[0]
        if mj and "autonomous_experiment_design" in mj:
            pid = p
            break
    rev0 = conn.execute("select paper_md from paper_revisions where proposal_id=? and revision_number=0", (pid,)).fetchone()[0]
    rev1 = conn.execute("select paper_md from paper_revisions where proposal_id=? and revision_number=1", (pid,)).fetchone()[0]
    meta, markers = rebuild_markers(conn, pid)
    conn.close()
    spec0 = ((meta.get("autonomous_experiment_design") or {}).get("specs") or [{}])[0]
    return rev0, rev1, meta, markers, spec0


print("=" * 76)
print("Q1/Q4: STAGE-faithful conclusion scan over all four specimens' rev1 (+ regr-B rev0)")
for trial in ("calib-A#1", "calib-B#2", "regr-A#1", "regr-B#1", "regr-B#2"):
    rev0, rev1, meta, markers, spec0 = load_trial(trial)
    unm, mapped, alen, clen = authoritative_unmapped_claims(rev1)
    print(f"  {trial:10s} | abstract {alen}ch conclusion {clen}ch | unmapped={len(unm)} mapped={len(mapped)}")
    for label, ctx in unm:
        print(f"      UNMAPPED [{label}]: ...{ctx}...")

rev0, rev1, meta, markers, spec0 = load_trial("regr-B#1")
unm0, _, _, _ = authoritative_unmapped_claims(rev0)
print(f"  regr-B rev0: unmapped={len(unm0)} (claim pre-exists at rev0: {len(unm0) >= 1})")
for label, ctx in unm0:
    print(f"      rev0 UNMAPPED [{label}]: ...{ctx}...")

print("=" * 76)
print("Q2: is the claim TRUE against persisted markers? any unique single-marker mapping?")
shape = re.compile(r"^(?P<ds>[^.]+)\.(?P<sev>0_[0-9]+)_(?P<method>ridge|huber)_(?P<metric>mae|rmse|r2)$")
by_key = collections.defaultdict(dict)
for m in markers:
    mm = shape.match(m.metric_name)
    if not mm:
        continue
    by_key[(mm.group("ds"), mm.group("sev"), mm.group("metric"))][mm.group("method")] = (
        float(m.observed_value), m.marker)
claim_checks = []
for (ds, sev, metric), methods in sorted(by_key.items()):
    if "ridge" in methods and "huber" in methods:
        rv, _ = methods["ridge"]
        hv, _ = methods["huber"]
        ok = (rv < hv) if metric == "rmse" else (rv > hv)
        claim_checks.append((ds, sev, metric, rv, hv, ok))
for c in claim_checks:
    print(f"  ridge-vs-huber sev={c[1]} {c[2]:5s} {c[0]:22s} ridge={c[3]:<12.6g} huber={c[4]:<12.6g} claim_holds={c[5]}")
n_pairs = len(claim_checks)
print(f"  aggregate claim 'ridge lower RMSE & higher R2 at EVERY severity on BOTH datasets': "
      f"{n_pairs} ridge/huber pairs checked, all hold = {all(c[5] for c in claim_checks) if claim_checks else 'N/A'}")

print("=" * 76)
print("Q3: deterministic REMOVAL repair on regr-B#1 rev1 — full battery, no gate may flip")
claim_re = re.compile(r"[^.]*\bresults?\s+show\s+that\b[^.]*\.", re.IGNORECASE)
m = claim_re.search(rev1)
assert m, "claim sentence not found in rev1"
sentence = m.group(0)
start, end = m.start(), m.end()
if rev1[end:end + 1] == " ":
    end += 1
repaired = rev1[:start] + rev1[end:]
print(f"  removed sentence ({len(sentence)} chars): {sentence[:110]}...")
ev_before, mf_before = gate_battery(rev1, meta, markers, spec0)
ev_after, mf_after = gate_battery(repaired, meta, markers, spec0)
before_gates = {g.get("gate"): g.get("passed", g.get("classification")) for g in ev_before.gates}
after_gates = {g.get("gate"): g.get("passed", g.get("classification")) for g in ev_after.gates}
print("  pure gates before:", json.dumps(before_gates))
print("  pure gates after: ", json.dumps(after_gates))
flips = [k for k in before_gates if before_gates[k] != after_gates.get(k)]
print("  gate flips:", flips or "NONE", "| new blocking after:", ev_after.blocking_reasons or "NONE")
print(f"  method_fidelity before={mf_before.passed} after={mf_after.passed}")
unm_after, mapped_after, _, _ = authoritative_unmapped_claims(repaired)
print(f"  authoritative unmapped after removal: {len(unm_after)} | mapped: {len(mapped_after)}")
print(f"  structure: RESULT count {rev1.count('[RESULT-')} -> {repaired.count('[RESULT-')} | "
      f"SOURCE count {rev1.count('[SOURCE-')} -> {repaired.count('[SOURCE-')}")
from backend.pipeline.evaluation.paper_sections import parse_paper
b, a = parse_paper(rev1), parse_paper(repaired)
print(f"  headings identical: {[s.heading for s in b.sections] == [s.heading for s in a.sections]}")
print(f"  net chars removed: {len(rev1) - len(repaired)}")
Path("r6_diagnostic_result.json").write_text(json.dumps({
    "claim_sentence": sentence,
    "claim_checks": claim_checks,
    "gates_before": before_gates, "gates_after": after_gates,
    "flips": flips, "blocking_after": ev_after.blocking_reasons,
    "mf_before": mf_before.passed, "mf_after": mf_after.passed,
    "unmapped_after": len(unm_after),
}, indent=1, default=str))

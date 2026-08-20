"""P1-12: frozen 8-trial Productive-1 qualification.

Four blocked starting states (2 calibration, 2 robust-regression) x 2
byte-identical restores each. Per trial: clone the state DB, prepare the
pre-repair blocked state (strip revisions >= 1; for promoted specimens
restore the proposal paper to rev0 bytes and recompute the blocked
evaluation with the production PURE gate evaluator), start a fresh API
process, invoke the governed /paper/repair route exactly once, capture
the response, post-diagnose numeric fidelity with the UNCHANGED
validator, and on a ready promotion perform the normal freeze + release
and verify E == F == R == H. No operator decisions occur mid-trial.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

STATES = [
    ("calib-A", "calibration", ".p1_tmp/r1_specimen.db", False),
    ("calib-B", "calibration", ".p1_tmp/runfail2_specimen.db", True),
    ("regr-A", "regression", "evidence/case3a_specimen.db", True),
    ("regr-B", "regression",
     "evidence/case4_runtime/preflight_archive/20260818T081540Z"
     "/data/elephant_rock.db", True),
]
PORT = 8772
BASE = f"http://127.0.0.1:{PORT}"


def http(method, path, timeout=900.0):
    req = urllib.request.Request(
        BASE + path, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


def rebuild_markers(conn, proposal_id):
    meta = json.loads(conn.execute(
        "select paper_meta_json from proposals where id=?",
        (proposal_id,),
    ).fetchone()[0])
    design = meta["autonomous_experiment_design"]
    exps = conn.execute(
        "select id, manifest_json from experiment_results where success=1"
        " order by id asc",
    ).fetchall()
    by_sid = {}
    for eid, mj in exps:
        m = json.loads(mj) if mj else {}
        sid = m.get("experiment_spec_id", "")
        if m.get("status") == "succeeded" and sid:
            by_sid[sid] = (eid, m)
    objs = []
    idx = 0
    for spec_dict in design.get("specs", []):
        sid = spec_dict.get("experiment_spec_id", "")
        if sid not in by_sid:
            continue
        eid, man = by_sid[sid]
        ds = spec_dict.get("dataset", {}).get("name", "unknown")
        arts = man.get("result_artifacts", [])
        for metric_name, value in sorted(man.get("results", {}).items()):
            idx += 1
            art = next((a for a in arts if isinstance(a, dict)
                        and a.get("artifact_type") == "metrics"),
                       arts[0] if arts else None)
            objs.append({
                "marker": f"RESULT-{idx}",
                "metric_name": f"{ds}.{metric_name}",
                "observed_value": value,
                "role": ("baseline" if metric_name.startswith("baseline_")
                         else "comparison"),
                "experiment_result_id": eid,
                "artifact_path": (f"{ds}/{art.get('filename', '')}"
                                  if isinstance(art, dict) else ""),
                "artifact_sha256": (art.get("sha256", "")
                                    if isinstance(art, dict) else ""),
            })
    return meta, objs


def marker_objects(dicts):
    from backend.pipeline.experiment.manifest import ResultMarker
    return [ResultMarker(
        marker_index=int(d["marker"].split("-")[1]),
        marker=d["marker"], metric_name=d["metric_name"],
        observed_value=d["observed_value"],
        artifact_path=d.get("artifact_path", ""),
        artifact_sha256=d.get("artifact_sha256", ""),
        experiment_result_id=d.get("experiment_result_id"),
        direction="", role=d.get("role", ""),
    ) for d in dicts]


def prep_trial(clone, spec_sources):
    conn = sqlite3.connect(clone)
    row = conn.execute(
        "select id from proposals where paper_md is not null order by id"
    ).fetchall()
    proposal_id = None
    for (pid,) in row:
        mj = conn.execute(
            "select paper_meta_json from proposals where id=?", (pid,)
        ).fetchone()[0]
        if mj and "autonomous_experiment_design" in mj:
            proposal_id = pid
            break
    rev0 = conn.execute(
        "select paper_md from paper_revisions where proposal_id=?"
        " and revision_number=0", (proposal_id,),
    ).fetchone()[0]
    conn.execute(
        "delete from paper_revisions where proposal_id=?"
        " and revision_number>=1", (proposal_id,),
    )
    idea_id = conn.execute(
        "select idea_id from proposals where id=?", (proposal_id,)
    ).fetchone()[0]
    needs_eval = spec_sources
    if needs_eval:
        conn.execute(
            "update proposals set paper_md=? where id=?", (rev0, proposal_id)
        )
        meta, markers = rebuild_markers(conn, proposal_id)
        from backend.pipeline.evaluation.paper_gate_evaluator import (
            evaluate_paper_gates,
        )
        d = meta["autonomous_experiment_design"]
        spec0 = (d.get("specs") or [{}])[0]
        ev = evaluate_paper_gates(
            paper_md=rev0,
            source_map=meta.get("source_map"),
            research_intent=spec0.get("research_question", ""),
            domain=spec0.get("task_type", ""),
            result_markers=marker_objects(markers),
            spec_method=spec0.get("analysis_method", ""),
            spec_dataset=spec0.get("dataset", {}).get("name", ""),
            spec_baseline=spec0.get("baseline_method", ""),
            spec_comparison=spec0.get("comparison_method", ""),
        )
        ev_data = getattr(ev, "to_dict", lambda: {
            "status": ev.status,
            "gates": getattr(ev, "gates", []),
            "paper_hash": hashlib.sha256(rev0.encode()).hexdigest(),
        })()
        if isinstance(ev_data, dict) and "paper_hash" not in ev_data:
            ev_data["paper_hash"] = hashlib.sha256(
                rev0.encode()).hexdigest()
        meta["paper_evaluation"] = ev_data
        conn.execute(
            "update proposals set paper_meta_json=? where id=?",
            (json.dumps(meta), proposal_id),
        )
    conn.commit()
    conn.close()
    return proposal_id, idea_id


def run_trial(label, family, source, needs_eval, trial_no):
    clone = ROOT / f".p1_tmp/p1_12_{label}_{trial_no}.db"
    shutil.copyfile(source, clone)
    proposal_id, idea_id = prep_trial(clone, needs_eval)

    env = dict(os.environ)
    env["EROCK_DATABASE_URL"] = "sqlite:///" + clone.resolve().as_posix()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.app:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=open(ROOT / f".p1_tmp/p1_12_{label}_{trial_no}_api.log", "w"),
        stderr=subprocess.STDOUT,
    )
    record = {"trial": f"{label}#{trial_no}", "family": family}

    def health(deadline=120.0):
        end = time.time() + deadline
        while time.time() < end:
            try:
                with urllib.request.urlopen(BASE + "/health",
                                            timeout=5) as r:
                    if r.status == 200:
                        return True
            except Exception:
                time.sleep(2)
        return False

    try:
        if not health():
            record["error"] = "API failed to start"
            return record
        t0 = time.time()
        status, _, body = http("POST",
                               f"/api/v1/ideas/{idea_id}/paper/repair")
        record["latency_s"] = round(time.time() - t0, 1)
        record["http"] = status
        resp = json.loads(body)
        record["promoted"] = resp.get("repair", {}).get("promoted")
        record["repair"] = resp.get("repair", {})
        gates = (resp.get("evaluation") or {}).get("gates") or []
        record["gates"] = gates
        record["eval_status"] = (resp.get("evaluation") or {}).get("status")

        # Post-diagnosis: unchanged validator on the trial clone.
        conn = sqlite3.connect(clone)
        rev1 = conn.execute(
            "select paper_md from paper_revisions where proposal_id=?"
            " and revision_number=1", (proposal_id,)
        ).fetchone()
        record["revision_lineage"] = [
            list(r) for r in conn.execute(
                "select revision_number, eval_status, source,"
                " substr(paper_hash,1,12) from paper_revisions"
                " where proposal_id=? order by revision_number",
                (proposal_id,))
        ]
        if rev1:
            _, markers = rebuild_markers(conn, proposal_id)
            from backend.pipeline.evaluation.claim_result_validator import (
                validate_claim_result_alignment,
            )
            mism = [m for m in validate_claim_result_alignment(
                rev1[0], marker_objects(markers))
                if m.section == "numeric_fidelity"]
            record["rev1_numeric_mismatch_count"] = len(mism)
            record["rev1_numeric_mismatches"] = [
                {"marker": m.marker, "claim": m.claim_text} for m in mism
            ]

        # On ready: normal freeze + release + four-authority equality.
        if record.get("eval_status") == "ready":
            fs, _, fb = http(
                "POST", f"/api/v1/ideas/{idea_id}/paper/freeze", 120.0)
            release = json.loads(fb).get("release", {})
            record["freeze"] = {
                "http": fs, "state": release.get("state"),
                "frozen_revision_id": release.get("frozen_revision_id"),
            }
            if release.get("state") == "frozen":
                rs, headers, rb = http(
                    "GET",
                    f"/api/v1/export/paper/release/markdown/{idea_id}",
                    120.0)
                H = (headers.get("x-erlab-paper-hash")
                     or next((v for k, v in headers.items()
                              if k.lower() == "x-erlab-paper-hash"), ""))
                meta = json.loads(conn.execute(
                    "select paper_meta_json from proposals where id=?",
                    (proposal_id,),
                ).fetchone()[0])
                E = (meta.get("paper_evaluation") or {}).get(
                    "paper_hash", "")
                F = conn.execute(
                    "select paper_hash from paper_revisions where id=?",
                    (release.get("frozen_revision_id"),),
                ).fetchone()[0]
                R = hashlib.sha256(rb).hexdigest()
                record["release_identity"] = {
                    "E": E, "F": F, "R": R, "H": H,
                    "equality": E == F == R == H and bool(E),
                }
        conn.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except Exception:
            server.kill()
    return record


def negative_control():
    """Unsupported numeric transform must remain blocked (no promotion
    path even reachable) under the UNCHANGED validator."""
    from backend.pipeline.evaluation.claim_result_validator import (
        validate_claim_result_alignment,
    )
    markers = marker_objects([
        {"marker": "RESULT-1", "metric_name": "iris.accuracy",
         "observed_value": 0.515625, "role": "comparison",
         "experiment_result_id": 1, "artifact_path": "p",
         "artifact_sha256": "s"},
    ])
    paper = "The method achieves 51.5625 [RESULT-1] (percent form)."
    mism = [m for m in validate_claim_result_alignment(paper, markers)
            if m.section == "numeric_fidelity"]
    return {"blocked": len(mism) >= 1, "mismatches": len(mism)}


if __name__ == "__main__":
    results = []
    for label, family, source, needs_eval in STATES:
        for trial_no in (1, 2):
            r = run_trial(label, family, source, needs_eval, trial_no)
            results.append(r)
            eq = (r.get("release_identity") or {}).get("equality")
            print(f"[{r['trial']}] promoted={r.get('promoted')}"
                  f" eval={r.get('eval_status')}"
                  f" mismatches={r.get('rev1_numeric_mismatch_count')}"
                  f" equality={eq}", flush=True)
    nc = negative_control()
    by_family = {}
    for r in results:
        by_family.setdefault(r["family"], []).append(
            1 if r.get("eval_status") == "ready" else 0)
    overall = sum(sum(v) for v in by_family.values())
    verdict = {
        "overall_success": overall,
        "overall_required": 7,
        "per_family": {k: {"success": sum(v), "of": len(v)}
                       for k, v in by_family.items()},
        "negative_control": nc,
        "pass": (overall >= 7
                 and all(sum(v) >= 3 for v in by_family.values())
                 and nc["blocked"]),
    }
    out = {"trials": results, "adjudication": verdict}
    Path("evidence/productive1/p1_12_qualification.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("VERDICT:", json.dumps(verdict["pass"]), "|",
          json.dumps(verdict["per_family"]), "| overall",
          f"{overall}/8")

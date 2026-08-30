"""Productive-1 R3 frozen 8-trial qualification.

Execution-only harness. Four frozen blocked starting states (2 calibration,
2 robust-regression) x two byte-identical restores. Each trial starts a
fresh API process, invokes the governed /paper/repair route exactly once,
records the persisted directive target set and authoritative gate outcome,
post-diagnoses numeric fidelity with the unchanged validator, and on ready
performs the normal freeze + release and verifies E == F == R == H.

This file adds no product behavior, gate, threshold, retry, or provider
semantics. The frozen candidate under test is fc6cc8dc31a3ec0155d50d16807942e11de1dc54.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

INPUT = ROOT / ".r3_qual_inputs"
TMP = ROOT / ".r3_qual_tmp"
TMP.mkdir(exist_ok=True)
OUT = ROOT / "evidence/productive1_r3/p1_r3_qualification.json"

STATES = [
    ("calib-A", "calibration", INPUT / "calib-A_runfail3.db", False),
    ("calib-B", "calibration", INPUT / "calib-B_runfail2.db", True),
    ("regr-A", "regression", INPUT / "regr-A_case3a.db", True),
    ("regr-B", "regression", INPUT / "regr-B_3E_era.db", True),
]
PORT = 8772
BASE = f"http://127.0.0.1:{PORT}"


def http(method: str, path: str, timeout: float = 900.0):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def rebuild_markers(conn: sqlite3.Connection, proposal_id: int):
    meta = json.loads(
        conn.execute(
            "select paper_meta_json from proposals where id=?", (proposal_id,)
        ).fetchone()[0]
    )
    design = meta["autonomous_experiment_design"]
    exps = conn.execute(
        "select id, manifest_json from experiment_results where success=1 order by id asc"
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
            art = next(
                (
                    a
                    for a in arts
                    if isinstance(a, dict) and a.get("artifact_type") == "metrics"
                ),
                arts[0] if arts else None,
            )
            objs.append(
                {
                    "marker": f"RESULT-{idx}",
                    "metric_name": f"{ds}.{metric_name}",
                    "observed_value": value,
                    "role": (
                        "baseline" if metric_name.startswith("baseline_") else "comparison"
                    ),
                    "experiment_result_id": eid,
                    "artifact_path": (
                        f"{ds}/{art.get('filename', '')}" if isinstance(art, dict) else ""
                    ),
                    "artifact_sha256": (
                        art.get("sha256", "") if isinstance(art, dict) else ""
                    ),
                }
            )
    return meta, objs


def marker_objects(dicts: list[dict]):
    from backend.pipeline.experiment.manifest import ResultMarker

    return [
        ResultMarker(
            marker_index=int(d["marker"].split("-")[1]),
            marker=d["marker"],
            metric_name=d["metric_name"],
            observed_value=d["observed_value"],
            artifact_path=d.get("artifact_path", ""),
            artifact_sha256=d.get("artifact_sha256", ""),
            experiment_result_id=d.get("experiment_result_id"),
            direction="",
            role=d.get("role", ""),
        )
        for d in dicts
    ]


def prep_trial(clone: Path, recompute_blocked_eval: bool):
    conn = sqlite3.connect(clone)
    rows = conn.execute(
        "select id from proposals where paper_md is not null order by id"
    ).fetchall()
    proposal_id = None
    for (pid,) in rows:
        mj = conn.execute(
            "select paper_meta_json from proposals where id=?", (pid,)
        ).fetchone()[0]
        if mj and "autonomous_experiment_design" in mj:
            proposal_id = pid
            break
    if proposal_id is None:
        raise RuntimeError(f"no autonomous proposal in {clone}")

    rev0_row = conn.execute(
        "select paper_md from paper_revisions where proposal_id=? and revision_number=0",
        (proposal_id,),
    ).fetchone()
    if not rev0_row:
        raise RuntimeError(f"no revision 0 for proposal {proposal_id} in {clone}")
    rev0 = rev0_row[0]

    conn.execute(
        "delete from paper_revisions where proposal_id=? and revision_number>=1",
        (proposal_id,),
    )
    idea_id = conn.execute(
        "select idea_id from proposals where id=?", (proposal_id,)
    ).fetchone()[0]

    if recompute_blocked_eval:
        conn.execute("update proposals set paper_md=? where id=?", (rev0, proposal_id))
        meta, markers = rebuild_markers(conn, proposal_id)
        from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates

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
        ev_data = getattr(
            ev,
            "to_dict",
            lambda: {
                "status": ev.status,
                "gates": getattr(ev, "gates", []),
                "paper_hash": hashlib.sha256(rev0.encode()).hexdigest(),
            },
        )()
        if isinstance(ev_data, dict) and "paper_hash" not in ev_data:
            ev_data["paper_hash"] = hashlib.sha256(rev0.encode()).hexdigest()
        meta["paper_evaluation"] = ev_data
        conn.execute(
            "update proposals set paper_meta_json=? where id=?",
            (json.dumps(meta), proposal_id),
        )

    conn.commit()
    conn.close()
    return proposal_id, idea_id


def health(deadline: float = 120.0) -> bool:
    end = time.time() + deadline
    while time.time() < end:
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(2)
    return False


def run_trial(label: str, family: str, source: Path, needs_eval: bool, trial_no: int):
    clone = TMP / f"p1_r3_{label}_{trial_no}.db"
    if clone.exists():
        clone.unlink()
    shutil.copyfile(source, clone)
    proposal_id, idea_id = prep_trial(clone, needs_eval)

    env = dict(os.environ)
    env["EROCK_DATABASE_URL"] = "sqlite:///" + clone.resolve().as_posix()
    log_path = TMP / f"p1_r3_{label}_{trial_no}_api.log"
    log_handle = open(log_path, "w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    record = {
        "trial": f"{label}#{trial_no}",
        "family": family,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    try:
        if not health():
            record["error"] = "API failed to start"
            return record

        t0 = time.time()
        status, _, body = http("POST", f"/api/v1/ideas/{idea_id}/paper/repair")
        record["latency_s"] = round(time.time() - t0, 1)
        record["http"] = status
        try:
            resp = json.loads(body)
        except Exception:
            record["error"] = f"non-JSON repair response: {body[:1000]!r}"
            return record
        if status != 200:
            record["error"] = resp
            return record

        repair = resp.get("repair", {}) or {}
        evaluation = resp.get("evaluation", {}) or {}
        record["promoted"] = repair.get("promoted")
        record["repair"] = repair
        record["gates"] = evaluation.get("gates") or []
        record["eval_status"] = evaluation.get("status")

        conn = sqlite3.connect(clone)
        rev1 = conn.execute(
            "select paper_md, directive_json, trigger_detail_json from paper_revisions "
            "where proposal_id=? and revision_number=1",
            (proposal_id,),
        ).fetchone()
        record["revision_lineage"] = [
            list(r)
            for r in conn.execute(
                "select revision_number, eval_status, source, substr(paper_hash,1,12) "
                "from paper_revisions where proposal_id=? order by revision_number",
                (proposal_id,),
            )
        ]

        if rev1:
            try:
                directive = json.loads(rev1[1]) if rev1[1] else {}
            except Exception:
                directive = {}
            record["directive_target_set"] = directive.get("numeric_repair_targets", [])
            record["directive_target_count"] = len(record["directive_target_set"])
            try:
                detail = json.loads(rev1[2]) if rev1[2] else {}
            except Exception:
                detail = {}
            record["authoritative_stamp"] = detail.get("authoritative")

            _, markers = rebuild_markers(conn, proposal_id)
            from backend.pipeline.evaluation.claim_result_validator import (
                validate_claim_result_alignment,
            )

            mism = [
                m
                for m in validate_claim_result_alignment(
                    rev1[0], marker_objects(markers)
                )
                if m.section == "numeric_fidelity"
            ]
            record["rev1_numeric_mismatch_count"] = len(mism)
            record["rev1_numeric_mismatches"] = [
                {"marker": m.marker, "claim": m.claim_text, "metric": m.marker_metric}
                for m in mism
            ]

        if record.get("eval_status") == "ready":
            fs, _, fb = http(
                "POST", f"/api/v1/ideas/{idea_id}/paper/freeze", timeout=120.0
            )
            try:
                freeze_payload = json.loads(fb)
            except Exception:
                freeze_payload = {}
            release = freeze_payload.get("release", {}) or {}
            record["freeze"] = {
                "http": fs,
                "state": release.get("state"),
                "frozen_revision_id": release.get("frozen_revision_id"),
            }
            if fs == 200 and release.get("state") == "frozen":
                rs, headers, rb = http(
                    "GET",
                    f"/api/v1/export/paper/release/markdown/{idea_id}",
                    timeout=120.0,
                )
                H = headers.get("x-erlab-paper-hash") or next(
                    (v for k, v in headers.items() if k.lower() == "x-erlab-paper-hash"),
                    "",
                )
                meta = json.loads(
                    conn.execute(
                        "select paper_meta_json from proposals where id=?", (proposal_id,)
                    ).fetchone()[0]
                )
                E = (meta.get("paper_evaluation") or {}).get("paper_hash", "")
                frozen_id = release.get("frozen_revision_id")
                F = ""
                if frozen_id:
                    frow = conn.execute(
                        "select paper_hash from paper_revisions where id=?", (frozen_id,)
                    ).fetchone()
                    F = frow[0] if frow else ""
                R = hashlib.sha256(rb).hexdigest() if rs == 200 else ""
                record["release_identity"] = {
                    "E": E,
                    "F": F,
                    "R": R,
                    "H": H,
                    "equality": E == F == R == H and bool(E),
                    "http": rs,
                }
        conn.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except Exception:
            server.kill()
            server.wait(timeout=5)
        log_handle.close()
        time.sleep(1)
    return record


def negative_control():
    """The frozen unsupported numeric transform remains rejected."""
    from backend.pipeline.evaluation.claim_result_validator import (
        validate_claim_result_alignment,
    )

    markers = marker_objects(
        [
            {
                "marker": "RESULT-1",
                "metric_name": "iris.accuracy",
                "observed_value": 0.515625,
                "role": "comparison",
                "experiment_result_id": 1,
                "artifact_path": "p",
                "artifact_sha256": "s",
            }
        ]
    )
    paper = "The method achieves 51.5625 [RESULT-1] (percent form)."
    mism = [
        m
        for m in validate_claim_result_alignment(paper, markers)
        if m.section == "numeric_fidelity"
    ]
    return {"blocked": len(mism) >= 1, "mismatches": len(mism)}


def main():
    missing = [str(path) for _, _, path, _ in STATES if not path.exists()]
    if missing:
        raise SystemExit("missing frozen inputs: " + ", ".join(missing))

    results = []
    for label, family, source, needs_eval in STATES:
        for trial_no in (1, 2):
            r = run_trial(label, family, source, needs_eval, trial_no)
            results.append(r)
            eq = (r.get("release_identity") or {}).get("equality")
            print(
                f"[{r['trial']}] http={r.get('http')} promoted={r.get('promoted')} "
                f"eval={r.get('eval_status')} mismatches={r.get('rev1_numeric_mismatch_count')} "
                f"targets={r.get('directive_target_count')} equality={eq} error={bool(r.get('error'))}",
                flush=True,
            )

    nc = negative_control()
    by_family: dict[str, list[int]] = {}
    for r in results:
        by_family.setdefault(r["family"], []).append(
            1 if r.get("eval_status") == "ready" else 0
        )
    overall = sum(sum(values) for values in by_family.values())
    ready_trials = [r for r in results if r.get("eval_status") == "ready"]
    release_identity_ok = all(
        (r.get("release_identity") or {}).get("equality") is True for r in ready_trials
    )
    ready_promotions_consistent = all(r.get("promoted") is True for r in ready_trials)
    no_runtime_errors = all(not r.get("error") for r in results)

    verdict = {
        "candidate_sha": "fc6cc8dc31a3ec0155d50d16807942e11de1dc54",
        "overall_success": overall,
        "overall_required": 7,
        "per_family": {
            key: {"success": sum(values), "of": len(values)}
            for key, values in by_family.items()
        },
        "per_family_required": 3,
        "negative_control": nc,
        "release_identity_on_ready": release_identity_ok,
        "ready_promotions_consistent": ready_promotions_consistent,
        "operator_edits_or_continuation_decisions": 0,
        "runtime_errors": [r["trial"] for r in results if r.get("error")],
        "pass": (
            overall >= 7
            and all(sum(values) >= 3 for values in by_family.values())
            and nc["blocked"]
            and release_identity_ok
            and ready_promotions_consistent
            and no_runtime_errors
        ),
    }
    OUT.write_text(
        json.dumps({"trials": results, "adjudication": verdict}, indent=2),
        encoding="utf-8",
    )
    print("VERDICT:", json.dumps(verdict, indent=2), flush=True)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""P1-2: baseline the unchanged one-shot cold-repair path.

Prepares a byte-identical pre-repair blocked state (specimen clone with
the failed revision-1 row removed, so the route performs a fresh
governed repair rather than returning the cached blocked result),
starts a fresh API process against the clone, invokes the real
/api/v1/ideas/1/paper/repair once, and captures the revision, numeric
mismatches, gate results, latency, and response. Read-only toward the
preserved specimen and the live research DB.
"""
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
CLONE = ROOT / ".p1_tmp/p1_9_clone.db"
BASE = "http://127.0.0.1:8770"

shutil.copyfile(ROOT / ".p1_tmp/r1_specimen.db", CLONE)
conn = sqlite3.connect(CLONE)
conn.execute("delete from paper_revisions where revision_number = 1")
conn.commit()
n = conn.execute("select count(*) from paper_revisions").fetchone()[0]
conn.close()
print(f"clone prepared: revision rows after strip = {n} (expect 1: rev0)")

env = dict(os.environ)
env["EROCK_DATABASE_URL"] = "sqlite:///" + CLONE.resolve().as_posix()
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.api.app:app",
     "--host", "127.0.0.1", "--port", "8770"],
    cwd=str(ROOT), env=env,
    stdout=open(ROOT / ".p1_tmp/p1_9_api.log", "w"),
    stderr=subprocess.STDOUT,
)

def health(deadline=120.0):
    end = time.time() + deadline
    while time.time() < end:
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(2)
    return False

OUT = sys.argv[1] if len(sys.argv) > 1 else "evidence/productive1/p1_2_baseline.json"
record = {"phase": OUT}
try:
    if not health():
        record["error"] = "API failed to start"
        raise SystemExit(1)
    req = urllib.request.Request(
        BASE + "/api/v1/ideas/1/paper/repair", method="POST",
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = json.loads(resp.read())
        record["http"] = resp.status
    record["latency_s"] = round(time.time() - t0, 1)
    record["repair"] = body.get("repair", {})
    record["evaluation"] = body.get("evaluation", {})
finally:
    server.terminate()
    try:
        server.wait(timeout=15)
    except Exception:
        server.kill()

# Post-diagnosis on the clone with the unchanged validator.
conn = sqlite3.connect(CLONE)
rows = conn.execute(
    "select revision_number, eval_status, source, length(paper_md),"
    " substr(paper_hash,1,16) from paper_revisions order by id"
).fetchall()
record["revision_lineage"] = [list(r) for r in rows]
rev1 = conn.execute(
    "select paper_md from paper_revisions where revision_number=1"
).fetchone()
conn.close()

if rev1:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from backend.pipeline.experiment.manifest import ResultMarker
    from backend.pipeline.evaluation.claim_result_validator import (
        validate_claim_result_alignment,
    )
    markers = json.loads(
        Path("evidence/productive1/p1_1_discrepancies.json").read_text(
            encoding="utf-8"
        )
    )
    # Rebuild marker objects from the P1-1 record (same reconstruction).
    mrec = json.loads(Path(".p1_tmp/p1_1_markers.json").read_text()) if Path(".p1_tmp/p1_1_markers.json").exists() else None
    # Fall back: rerun the P1-1 reconstruction inline.
    c2 = sqlite3.connect("file:" + str(CLONE) + "?mode=ro", uri=True)
    meta = json.loads(c2.execute(
        "select paper_meta_json from proposals where id=1"
    ).fetchone()[0])
    exps = c2.execute(
        "select id, manifest_json from experiment_results where success=1"
        " order by id"
    ).fetchall()
    c2.close()
    idx = 0
    objs = []
    by_sid = {
        (json.loads(mj) or {}).get("experiment_spec_id", ""): (eid, json.loads(mj))
        for eid, mj in exps
        if (json.loads(mj) or {}).get("status") == "succeeded"
    }
    for spec_dict in meta["autonomous_experiment_design"]["specs"]:
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
            objs.append(ResultMarker(
                marker_index=idx, marker=f"RESULT-{idx}",
                metric_name=f"{ds}.{metric_name}",
                observed_value=value,
                artifact_path=f"{ds}/{art.get('filename','')}" if isinstance(art, dict) else "",
                artifact_sha256=art.get("sha256","") if isinstance(art, dict) else "",
                experiment_result_id=eid, direction="",
                role="baseline" if metric_name.startswith("baseline_") else "comparison",
            ))
    mism = [m for m in validate_claim_result_alignment(rev1[0], objs)
            if m.section == "numeric_fidelity"]
    record["rev1_numeric_mismatches"] = [
        {"marker": m.marker, "claim": m.claim_text, "metric": m.marker_metric}
        for m in mism
    ]
    record["rev1_mismatch_count"] = len(mism)

Path(OUT).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({k: record.get(k) for k in (
    "http", "latency_s", "repair", "evaluation_status",
    "rev1_mismatch_count", "revision_lineage")}, indent=1)[:800])
print("repair:", json.dumps(record.get("repair"))[:200])
print("evaluation.status:", (record.get("evaluation") or {}).get("status"))
print("rev1 numeric mismatches:", record.get("rev1_mismatch_count"))

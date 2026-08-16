"""Case 2D: Repeatability qualification — fully automated lifecycle harness.

Pre-registered continuation policy (frozen in this file BEFORE launch;
no human decision occurs between launch and verdict):

  1. Run PipelineOrchestrator with the frozen Case-2 input
     (domain + question + autonomous_experiment_enabled=True only).
  2. From persisted DB state, locate the proposal carrying the paper
     and the autonomous design.
  3. If its evaluation is already ready  -> skip remediation (Path A).
     If its evaluation is blocked        -> invoke the production
     cold-repair route EXACTLY ONCE (the route is itself single-shot
     bounded). No retries, no deletions, no edits.
  4. If the paper is ready after step 3  -> invoke freeze, then fetch
     the release export. Otherwise record FAIL and stop.
  5. Verify E == F == R == H from four independent authorities and
     that the release bytes equal the current paper bytes.
  6. Write evidence/case2d_result.json; exit 0 on acceptance, 1 on
     defined failure.

Frozen head: 1cb8fe048300b5813395eb637feb38b77f52ff8a (main). No
production code is changed by this harness; it drives only existing
production entry points.
"""
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ["EROCK_EMBEDDING_MODEL"] = "text-embedding-qwen3-embedding-0.6b"
os.environ["EROCK_EMBEDDING_DIMENSION"] = "1024"
os.environ["EROCK_EMBEDDING_PROVIDER"] = "lmstudio"

sys.path.insert(0, ".")

DB = "data/elephant_rock.db"
BASE = "http://127.0.0.1:8767"
RESULT_PATH = "evidence/case2d_result.json"
LOG_LINES: list[str] = []


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()[11:19]}Z] {msg}"
    LOG_LINES.append(line)
    print(line, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http(method: str, path: str, body: dict | None = None, timeout: float = 900.0):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
        return resp.status, dict(resp.headers), payload


def wait_health(deadline_s: float = 120.0) -> bool:
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            status, _, _ = http("GET", "/health", timeout=5)
            if status == 200:
                return True
        except Exception:
            time.sleep(2)
    return False


def find_paper_proposal() -> dict | None:
    """Locate the run's paper proposal from persisted state (read-only)."""
    conn = sqlite3.connect(DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        run_id = row[0]
        cur.execute(
            "SELECT id FROM ideas WHERE pipeline_run_id=?", (run_id,)
        )
        idea_ids = [r[0] for r in cur.fetchall()]
        if not idea_ids:
            return None
        q = (
            f"SELECT id, idea_id, paper_md, paper_meta_json"
            f" FROM proposals WHERE idea_id IN"
            f" ({','.join(map(str, idea_ids))}) ORDER BY id"
        )
        for pid, iid, paper_md, meta in cur.execute(q).fetchall():
            m = json.loads(meta) if meta else {}
            if paper_md and paper_md.strip() and "autonomous_experiment_design" in m:
                return {
                    "proposal_id": pid,
                    "idea_id": iid,
                    "run_id": run_id,
                    "paper_md": paper_md,
                    "meta": m,
                }
        return None
    finally:
        conn.close()


def evaluate_acceptance(result: dict) -> dict:
    """Verify E == F == R == H and byte identity from persisted state."""
    conn = sqlite3.connect(DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_md, paper_meta_json FROM proposals WHERE id=?",
            (result["proposal_id"],),
        )
        paper_md, meta = cur.fetchone()
        m = json.loads(meta)
        E = (m.get("paper_evaluation") or {}).get("paper_hash", "")
        cur.execute(
            "SELECT paper_hash, eval_status FROM paper_revisions WHERE id=?",
            (result["frozen_revision_id"],),
        )
        F, frozen_eval = cur.fetchone()
        R = hashlib.sha256(result["release_bytes"]).hexdigest()
        H = result["release_header_hash"]
        return {
            "E": E, "F": F, "R": R, "H": H,
            "equality": E == F == R == H,
            "frozen_eval_status": frozen_eval,
            "release_equals_current_bytes": (
                result["release_bytes"].decode("utf-8").strip()
                == paper_md.strip()
            ),
        }
    finally:
        conn.close()


async def run_orchestrator() -> dict:
    from backend.pipeline.orchestrator._orchestrator import (
        PipelineOrchestrator,
    )

    orchestrator = PipelineOrchestrator(strategy="deep_research")
    start = time.time()
    result = await orchestrator.run(
        domain="Robust confidence estimation under dataset shift",
        research_question=(
            "Are calibration-method rankings stable as"
            " covariate-shift severity increases, or do rank"
            " reversals occur in accuracy, positive-class"
            " expected calibration error, and selective AURC"
            " across tabular classification datasets?"
        ),
        max_gaps=3,
        generation_rounds=1,
        ideas_per_round=1,
        autonomous_experiment_enabled=True,
    )
    return {
        "run_id": result.run_id,
        "outcome": result.outcome,
        "elapsed_s": round(time.time() - start, 1),
        "auto_design_status": (
            (result.params_used.get("autonomous_experiment_design") or {}).get("status")
        ),
    }


def main() -> int:
    result: dict = {
        "case": "Case 2D — zero-intervention qualification (automated continuation harness)",
        "frozen_head": "1cb8fe048300b5813395eb637feb38b77f52ff8a",
        "started_at": now(),
        "steps": [],
    }
    accepted = False
    server = None
    try:
        # Step 1: autonomous run (no human input; frozen input only)
        log("STEP1 orchestrator launch (frozen input)")
        orch = asyncio.run(run_orchestrator())
        result["steps"].append({"step": 1, "orchestrator": orch})
        log(f"STEP1 done: {orch}")
        if orch["auto_design_status"] != "designed":
            result["failure"] = "autonomous design did not complete"
            return finish(result, accepted=False)

        # Step 2: locate paper proposal from persisted state
        prop = find_paper_proposal()
        if prop is None:
            result["failure"] = "no paper proposal with autonomous design found"
            return finish(result, accepted=False)
        result["proposal_id"] = prop["proposal_id"]
        result["idea_id"] = prop["idea_id"]
        result["pipeline_run_id"] = prop["run_id"]
        eval_state = (prop["meta"].get("paper_evaluation") or {}).get("status")
        log(f"STEP2 proposal={prop['proposal_id']} idea={prop['idea_id']} eval={eval_state}")

        # Step 3: production server for the native routes
        log("STEP3 starting production API process")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.api.app:app",
             "--host", "127.0.0.1", "--port", "8767"],
            stdout=open("evidence/case2d_api.log", "w"),
            stderr=subprocess.STDOUT,
        )
        if not wait_health():
            result["failure"] = "API server failed to start"
            return finish(result, accepted=False)
        log("STEP3 API healthy")

        # Step 4: single bounded remediation if blocked (policy, not judgment)
        remediation = {"invoked": False}
        if eval_state == "blocked":
            log("STEP4 policy: blocked -> invoke cold repair ONCE")
            status, _, payload = http(
                "POST", f"/api/v1/ideas/{prop['idea_id']}/paper/repair"
            )
            body = json.loads(payload)
            remediation = {
                "invoked": True,
                "http": status,
                "promoted": body.get("repair", {}).get("promoted"),
                "revision_number": body.get("repair", {}).get("revision_number"),
                "eval_status": body.get("evaluation", {}).get("status"),
                "gates": [
                    {g.get("gate") or g.get("name"): str(g.get("passed", g.get("classification")))}
                    for g in body.get("evaluation", {}).get("gates", [])
                    if isinstance(g, dict)
                ],
            }
            log(f"STEP4 repair: {json.dumps(remediation)[:220]}")
        else:
            log("STEP4 policy: paper ready -> no remediation (Path A)")
        result["steps"].append({"step": 4, "remediation": remediation})

        # Step 5: re-read final evaluation from persisted state
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_meta_json FROM proposals WHERE id=?",
            (prop["proposal_id"],),
        )
        final_eval = (json.loads(cur.fetchone()[0]).get("paper_evaluation") or {})
        final_status = final_eval.get("status")
        conn.close()
        result["final_eval_status"] = final_status
        log(f"STEP5 final evaluation status: {final_status}")
        if final_status != "ready":
            result["failure"] = (
                "paper not ready after bounded remediation policy; "
                "no retries permitted"
            )
            return finish(result, accepted=False)
        result["final_gates"] = [
            {g.get("gate") or g.get("name"): str(g.get("passed", g.get("classification")))}
            for g in final_eval.get("gates", []) if isinstance(g, dict)
        ]

        # Step 6: freeze (native route)
        log("STEP6 freeze")
        status, _, payload = http(
            "POST", f"/api/v1/ideas/{prop['idea_id']}/paper/freeze", timeout=120
        )
        freeze_body = json.loads(payload)
        release = freeze_body.get("release", {})
        result["freeze"] = {
            "http": status, "state": release.get("state"),
            "frozen_revision_id": release.get("frozen_revision_id"),
            "release_eligible": release.get("release_eligible"),
            "current_matches_frozen": release.get("current_matches_frozen"),
        }
        if release.get("state") != "frozen":
            result["failure"] = f"freeze did not produce frozen state: {release.get('state')}"
            return finish(result, accepted=False)
        log(f"STEP6 frozen rev={release.get('frozen_revision_id')}")

        # Step 7: release export + four-authority verification
        log("STEP7 release export + E==F==R==H")
        status, headers, payload = http(
            "GET",
            f"/api/v1/export/paper/release/markdown/{prop['idea_id']}",
            timeout=120,
        )
        result["release_header_hash"] = headers.get("x-erlab-paper-hash", "")
        result["frozen_revision_id"] = release.get("frozen_revision_id")
        result["release_bytes"] = payload
        Path("evidence/case2d_release.md").write_bytes(payload)
        verification = evaluate_acceptance(result)
        result["verification"] = verification
        log(f"STEP7 equality={verification['equality']} "
            f"bytes_match={verification['release_equals_current_bytes']}")

        accepted = bool(
            verification["equality"]
            and verification["release_equals_current_bytes"]
            and verification["frozen_eval_status"] == "ready"
        )
        if not accepted:
            result["failure"] = "release identity verification failed"
        Path("evidence/case2d_release.md").write_bytes(
            result.pop("release_bytes")
        )
        return finish(result, accepted=accepted)
    except Exception as exc:
        result["failure"] = f"harness exception: {exc!r}"
        return finish(result, accepted=False)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except Exception:
                server.kill()


def finish(result: dict, accepted: bool) -> int:
    result["finished_at"] = now()
    result["decision"] = "ACCEPTED" if accepted else "FAIL"
    result["operator_interventions"] = 0 if accepted else result.get("operator_interventions", 0)
    result["log"] = LOG_LINES
    if "release_bytes" in result:
        Path("evidence/case2d_release.md").write_bytes(result.pop("release_bytes"))
    Path(RESULT_PATH).write_text(json.dumps(result, indent=2))
    print(f"\n[CASE2D] DECISION: {result['decision']}", flush=True)
    if not accepted:
        print(f"[CASE2D] FAILURE: {result.get('failure')}", flush=True)
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
